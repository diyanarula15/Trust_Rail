"""Evaluation harness (spec §16.2). Runs positives (every registered
image/video/text under every §16.1 transform) and negatives (generated
noise images + unrelated text snippets) through the real pipeline, records
stage outcomes + latency, writes docs/METRICS.md.

Calls the pipeline functions directly rather than through POST /api/verify
— this is trusted internal tooling, not simulated attacker traffic, and
the HTTP endpoint's 30/min rate limit would otherwise block a run of this
size. Every function called here is the exact same one api/verify.py uses.
"""
import io
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image
from sqlalchemy import select

from app.api.verify import _blacklist_refs, _downgrade_if_key_revoked, _load_candidates
from app.config import get_settings
from app.db import SessionLocal
from app.models import Communication, CommStatus
from app.pipeline import hashing, media
from app.pipeline.claims import extract_claim, load_entity_refs
from app.pipeline.ingest import ingest_file, ingest_text
from app.pipeline.risk import analyze_risk
from app.pipeline.verdict import (
    Decision,
    DecisionInput,
    MatchThresholds,
    QueryHashes,
    Verdict,
    decide,
    match_registry,
)
from scripts.wa_sim_transform import IMAGE_PRESETS, TEXT_PRESETS, VIDEO_PRESETS

REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_PATH = REPO_ROOT / "docs" / "METRICS.md"
PRECISION_TARGET = 0.95
RECALL_TARGET = 0.70

_UNRELATED_TEXTS = [
    "Benchmark indices ended higher today led by banking and IT stocks.",
    "The monsoon session of parliament is expected to take up several bills.",
    "Global oil prices eased slightly after last week's supply data.",
    "A new expressway connecting two major cities opened to traffic today.",
    "The central bank's monetary policy committee meets again next month.",
    "Local weather forecasters predict above-average rainfall this week.",
    "A popular smartphone maker unveiled its latest device at a launch event.",
    "The cricket board announced the schedule for the upcoming home series.",
    "Researchers published a study on urban air quality trends.",
    "A regional airline added two new domestic routes starting next quarter.",
    "The city council approved funding for a new public library branch.",
    "Farmers in the region reported a healthy wheat harvest this season.",
    "A startup incubator opened applications for its next cohort.",
    "The state government launched a skill-development program for youth.",
    "An art exhibition featuring regional painters opens this weekend.",
    "The railway ministry announced additional coaches for festival travel.",
    "A university research team developed a low-cost water filter.",
    "Local authorities completed repairs on the old town bridge.",
    "A documentary about coastal ecosystems premieres on streaming platforms.",
    "The tourism board reported a rise in visitors during the long weekend.",
]


class Row:
    def __init__(
        self, group: str, transform: str, case: str, expected_positive: bool,
        matched: bool, verdict: str, reasons: list[str], latency_ms: float,
        trace: list[dict],
    ) -> None:
        self.group = group
        self.transform = transform
        self.case = case
        self.expected_positive = expected_positive
        self.matched = matched
        self.verdict = verdict
        self.reasons = reasons
        self.latency_ms = latency_ms
        self.trace = trace


def _ensure_video_published(repo_root: Path) -> None:
    """DEMO.md step 1 publishes the CEO announcement video live, so
    scripts/seed.py deliberately doesn't auto-publish it (see the note in
    PUBLISH_PLAN) — publish an eval-only fixture copy here instead if
    nothing's published yet, so `make eval` works standalone. Any
    `make demo-reset` before a live demo wipes this fixture along with
    everything else, so it never lingers into the actual presentation."""
    from fastapi.testclient import TestClient
    from sqlalchemy import select as _select

    from app.main import app
    from app.models import Entity, Key, KeyRole

    with SessionLocal() as db:
        has_video = db.execute(
            _select(Communication).where(
                Communication.channel == "video", Communication.status == CommStatus.published
            )
        ).scalars().first()
        if has_video:
            return
        entity = db.execute(_select(Entity).where(Entity.name == "Kumaon Metals Ltd")).scalar_one()
        maker = db.execute(
            _select(Key).where(Key.entity_id == entity.id, Key.role == KeyRole.maker)
        ).scalar_one()
        checker = db.execute(
            _select(Key).where(Key.entity_id == entity.id, Key.role == KeyRole.checker)
        ).scalar_one()

    video_path = repo_root / "assets_input" / "ceo_announcement.mp4"
    if not video_path.exists():
        return  # no owner media yet — video positives just won't run this pass

    client = TestClient(app)
    r = client.post(
        "/api/issuer/communications",
        data={"entity_id": str(entity.id), "title": "Eval fixture — video (not part of the live demo)",
              "channel": "video", "impact": "market_moving"},
        files={"file": ("ceo_announcement.mp4", video_path.read_bytes(), "video/mp4")},
        headers={"X-Demo-Persona": str(maker.id)},
    ).json()
    comm_id = r["data"]["id"]
    client.post(f"/api/issuer/communications/{comm_id}/sign", headers={"X-Demo-Persona": str(maker.id)})
    client.post(f"/api/issuer/communications/{comm_id}/cosign", headers={"X-Demo-Persona": str(checker.id)})


def _registered_media(db) -> tuple[list, list, list]:
    comms = db.execute(
        select(Communication).where(Communication.status == CommStatus.published)
    ).scalars().all()
    images, videos, texts = [], [], []
    for c in comms:
        if c.channel.value == "image" and c.artifact:
            images.append((c.title, Path(c.artifact.storage_path).read_bytes()))
        elif c.channel.value == "video" and c.artifact:
            videos.append((c.title, Path(c.artifact.storage_path).read_bytes()))
        elif c.canonical_text:
            texts.append((c.title, c.canonical_text))
    return images, videos, texts


def _noise_images(n: int, seed: int = 20261010) -> list[bytes]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        im = Image.new("RGB", (400, 300))
        px = im.load()
        for y in range(300):
            for x in range(400):
                px[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        out.append(buf.getvalue())
    return out


def _run_pipeline(
    db, settings, *, image_bytes: bytes | None = None, video_bytes: bytes | None = None,
    text: str | None = None,
) -> tuple[Decision, list[str], float, list[dict]]:
    """Same steps as POST /api/verify, minus rate limiting and persistence."""
    t0 = time.monotonic()
    if image_bytes is not None:
        ir = ingest_file(image_bytes, "eval.jpg")
        qh = QueryHashes(
            sha256=hashing.sha256_hex(image_bytes),
            phash64=hashing.phash64_hex(image_bytes),
            pdq256=hashing.pdq256_hex(image_bytes),
        )
        body_text = ""
    elif video_bytes is not None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = Path(tmp.name)
        try:
            frames = media.extract_frame_phashes(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
        qh = QueryHashes(sha256=hashing.sha256_hex(video_bytes), video_frame_hashes=frames)
        body_text = ""
    else:
        assert text is not None
        ir = ingest_text(text)
        qh = QueryHashes(
            sha256=hashing.sha256_hex(text.encode("utf-8")),
            simhash64=hashing.simhash64_hex(text),
        )
        body_text = text

    entities = load_entity_refs(db)
    claims = extract_claim(body_text, entities)
    registered_domains = [d for e in entities for d in e.domains]
    risk = analyze_risk(
        body_text, registered_domains, _blacklist_refs(db),
        phash64=qh.phash64, phash_match_max_dist=settings.phash_match_max_dist,
    )
    thresholds = MatchThresholds(
        phash_match_max_dist=settings.phash_match_max_dist,
        phash_near_max_dist=settings.phash_near_max_dist,
        pdq_match_max_dist=settings.pdq_match_max_dist,
        video_frame_match_ratio=settings.video_frame_match_ratio,
        simhash_match_max_dist=settings.simhash_match_max_dist,
    )
    registry_match = match_registry(qh, _load_candidates(db), thresholds)
    decision = decide(DecisionInput(registry_match=registry_match, claims=claims, risk=risk,
                                     query_sha256=qh.sha256))
    decision = _downgrade_if_key_revoked(db, decision)
    latency_ms = (time.monotonic() - t0) * 1000
    trace = [t.model_dump() for t in decision.trace]
    return decision, [r.value for r in decision.reasons], latency_ms, trace  # type: ignore[return-value]


def run() -> list[Row]:
    settings = get_settings()
    _ensure_video_published(REPO_ROOT)
    rows: list[Row] = []
    with SessionLocal() as db:
        images, videos, texts = _registered_media(db)
        if not images or not texts:
            print("No published registered image/text media found — run `python -m scripts.seed` first.",
                  file=sys.stderr)
            sys.exit(2)
        if not videos:
            print("No published video and no assets_input/ceo_announcement.mp4 to fixture one — "
                  "video positives will be skipped for this run.", file=sys.stderr)

        for title, data in images:
            for preset_name, fn in IMAGE_PRESETS.items():
                mangled = fn(data)
                decision, reasons, latency, trace = _run_pipeline(db, settings, image_bytes=mangled)
                matched = any(r in ("HASH_EXACT_MATCH", "PHASH_MATCH", "PDQ_MATCH") for r in reasons)
                rows.append(Row("image", preset_name, title, True, matched, decision.verdict.value,
                                 reasons, latency, trace))

        for title, data in videos:
            for preset_name, fn in VIDEO_PRESETS.items():
                mangled = fn(data)
                decision, reasons, latency, trace = _run_pipeline(db, settings, video_bytes=mangled)
                matched = "VIDEO_MATCH" in reasons
                rows.append(Row("video", preset_name, title, True, matched, decision.verdict.value,
                                 reasons, latency, trace))

        for title, text in texts:
            for preset_name, fn in TEXT_PRESETS.items():
                mangled = fn(text)
                decision, reasons, latency, trace = _run_pipeline(db, settings, text=mangled)
                matched = "SIMHASH_MATCH" in reasons
                rows.append(Row("text", preset_name, title, True, matched, decision.verdict.value,
                                 reasons, latency, trace))

        for i, data in enumerate(_noise_images(30)):
            decision, reasons, latency, trace = _run_pipeline(db, settings, image_bytes=data)
            matched = any(r in ("HASH_EXACT_MATCH", "PHASH_MATCH", "PDQ_MATCH") for r in reasons)
            rows.append(Row("negative_image", "n/a", f"noise{i}", False, matched,
                             decision.verdict.value, reasons, latency, trace))

        for i, text in enumerate(_UNRELATED_TEXTS):
            decision, reasons, latency, trace = _run_pipeline(db, settings, text=text)
            matched = "SIMHASH_MATCH" in reasons
            rows.append(Row("negative_text", "n/a", f"text{i}", False, matched,
                             decision.verdict.value, reasons, latency, trace))

    return rows


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def write_metrics(rows: list[Row]) -> bool:
    """Returns True if precision/recall targets were met on every transform."""
    positives = [r for r in rows if r.expected_positive]
    negatives = [r for r in rows if not r.expected_positive]
    fp_total = sum(1 for r in negatives if r.matched)

    lines: list[str] = []
    lines.append("# TrustRail: Evaluation Metrics (spec §16.2)\n")
    n_image_transforms = len({r.transform for r in positives if r.group == "image"})
    n_video_transforms = len({r.transform for r in positives if r.group == "video"})
    n_text_transforms = len({r.transform for r in positives if r.group == "text"})
    lines.append(f"Generated by `python -m scripts.evaluate`. {len(positives)} positive cases "
                 f"({n_image_transforms} image transforms x images, {n_video_transforms} video "
                 f"transforms x videos, {n_text_transforms} text transforms x texts), "
                 f"{len(negatives)} negative cases "
                 f"({sum(1 for r in negatives if r.group == 'negative_image')} generated noise images, "
                 f"{sum(1 for r in negatives if r.group == 'negative_text')} unrelated text snippets).\n")

    # --- Table 1: hard-binding survival ---
    lines.append("## Table 1: Hard-binding survival per transform\n")
    lines.append(
        "This build's `/verify` contract has no sidecar-envelope input field (see PROGRESS.md "
        "Epic 5), so hard binding is always `no_manifest` here, by design, for every transform "
        "including the untransformed original. **This is exactly why soft (registry) binding "
        "exists**: it's the only path that survives WhatsApp-style re-encoding, and Table 2 is "
        "the number that actually matters.\n"
    )
    lines.append("| Transform | Hard-binding survived |")
    lines.append("|---|---|")
    for transform in sorted({r.transform for r in positives}):
        lines.append(f"| {transform} | 0% (0/{sum(1 for r in positives if r.transform == transform)}) |")
    lines.append("")

    # --- Table 2: soft-match precision/recall/F1 ---
    lines.append("## Table 2: Registry soft-match precision, recall, and F1\n")
    lines.append("| Group | Transform | Recall | Cases |")
    lines.append("|---|---|---|---|")
    by_group_transform: dict[tuple[str, str], list[Row]] = defaultdict(list)
    for r in positives:
        by_group_transform[(r.group, r.transform)].append(r)
    worst_recall = 1.0
    worst_key = None
    for (group, transform), grp_rows in sorted(by_group_transform.items()):
        matched = sum(1 for r in grp_rows if r.matched)
        recall = matched / len(grp_rows)
        if recall < worst_recall:
            worst_recall = recall
            worst_key = (group, transform)
        lines.append(f"| {group} | {transform} | {recall:.2f} | {matched}/{len(grp_rows)} |")

    tp_total = sum(1 for r in positives if r.matched)
    fn_total = len(positives) - tp_total
    precision, recall, f1 = _prf(tp_total, fp_total, fn_total)
    lines.append(f"| **TOTAL** | **overall** | **{recall:.2f}** | **{tp_total}/{len(positives)}** |")
    lines.append("")
    lines.append(f"Overall: precision **{precision:.3f}**, recall **{recall:.3f}**, F1 **{f1:.3f}** "
                 f"({fp_total} false positives out of {len(negatives)} negatives).\n")

    targets_met = precision >= PRECISION_TARGET and worst_recall >= RECALL_TARGET
    lines.append(f"**Targets:** precision ≥ {PRECISION_TARGET}, recall ≥ {RECALL_TARGET} "
                 f"(worst single transform, not just overall).\n")
    if not targets_met:
        lines.append(
            f"**TARGET MISSED**: worst transform `{worst_key}` recall {worst_recall:.2f} is below "
            f"{RECALL_TARGET}, or overall precision {precision:.3f} is below {PRECISION_TARGET}. "
            f"**§16.2 documented fallback applies: lean the demo on the exact-hash & envelope "
            f"path rather than soft-match for the affected transform(s).** Not softened, "
            f"stated plainly per the master-go instruction.\n"
        )
    else:
        lines.append("**Targets met** on every transform, so no fallback is needed.\n")

    # --- Table 3: latency + confusion matrix ---
    lines.append("## Table 3: Latency (ms) per stage, and verdict confusion\n")
    stage_ms: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for step in r.trace:
            stage_ms[step["stage"]].append(step["ms"])
    lines.append("| Stage | p50 | p95 |")
    lines.append("|---|---|---|")
    for stage, values in sorted(stage_ms.items()):
        values_sorted = sorted(values)
        p50 = statistics.median(values_sorted)
        p95_idx = min(len(values_sorted) - 1, int(len(values_sorted) * 0.95))
        lines.append(f"| {stage} | {p50:.1f} | {values_sorted[p95_idx]:.1f} |")
    total_latencies = sorted(r.latency_ms for r in rows)
    p50_total = statistics.median(total_latencies)
    p95_idx = min(len(total_latencies) - 1, int(len(total_latencies) * 0.95))
    lines.append(f"| **end-to-end** | **{p50_total:.1f}** | **{total_latencies[p95_idx]:.1f}** |")
    lines.append("")

    lines.append("### Verdict confusion (expected vs. actual)\n")
    lines.append("| Expected | VERIFIED | VERIFIED_NOTICE | OFFICIAL_CLAIM_UNVERIFIED | LIKELY_FAKE | INFORMATIONAL |")
    lines.append("|---|---|---|---|---|---|")
    for expected_label, subset in (("positive (should match)", positives), ("negative (should not match)", negatives)):
        counts = {v.value: 0 for v in Verdict}
        for r in subset:
            counts[r.verdict] = counts.get(r.verdict, 0) + 1
        lines.append(
            f"| {expected_label} | {counts.get('VERIFIED', 0)} | {counts.get('VERIFIED_NOTICE', 0)} | "
            f"{counts.get('OFFICIAL_CLAIM_UNVERIFIED', 0)} | {counts.get('LIKELY_FAKE', 0)} | "
            f"{counts.get('INFORMATIONAL', 0)} |"
        )
    lines.append("")

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {METRICS_PATH}")
    print(f"overall precision={precision:.3f} recall={recall:.3f} f1={f1:.3f} "
          f"worst_transform_recall={worst_recall:.2f} ({worst_key})")
    return targets_met


def main() -> None:
    rows = run()
    targets_met = write_metrics(rows)
    sys.exit(0 if targets_met else 1)


if __name__ == "__main__":
    main()
