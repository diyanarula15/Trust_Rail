"""spec §12.1 — THE ONLY place verdict -> human-readable copy happens.
The verify API and the (flag-gated) WhatsApp adapter both consume this;
card strings never get invented in the frontend or in a channel adapter.
"""
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.pipeline.evidence import MatchEvidence
from app.pipeline.verdict import Decision, ReasonCode, Verdict

_I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
_CACHE: dict[str, dict[str, Any]] = {}

_VERDICT_KEY = {
    Verdict.VERIFIED: "verified",
    Verdict.VERIFIED_NOTICE: "verified_notice",
    Verdict.OFFICIAL_CLAIM_UNVERIFIED: "official_claim_unverified",
    Verdict.LIKELY_FAKE: "likely_fake",
    Verdict.INFORMATIONAL: "informational",
}

# Priority order for picking LIKELY_FAKE's {top_reason} — most alarming first.
_TOP_REASON_PRIORITY = [
    ReasonCode.BLACKLIST_MATCH,
    ReasonCode.LOOKALIKE_DOMAIN,
    ReasonCode.TAMPERED_SIGNATURE,
    ReasonCode.TAMPERED_CONTENT,
    ReasonCode.HOMOGLYPH_ENTITY,
    ReasonCode.PAYMENT_ASK,
    ReasonCode.RISK_PHRASES,
    ReasonCode.URL_RISK,
    ReasonCode.ENTITY_CLAIM_STRONG,
    ReasonCode.ENTITY_CLAIM_WEAK,
]


def _load(locale: str) -> dict[str, Any]:
    if locale not in _CACHE:
        path = _I18N_DIR / f"{locale}.json"
        if not path.exists():
            path = _I18N_DIR / "en.json"
        _CACHE[locale] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[locale]


class EntityRef(BaseModel):
    id: str
    name: str
    sebi_reg_no: str


class CommunicationRef(BaseModel):
    id: str
    title: str
    published_at: str | None = None
    log_seq: int | None = None
    channel: str | None = None


class Button(BaseModel):
    kind: str
    label: str
    url: str


class EvidenceCopy(BaseModel):
    """Localized sentences for the match-evidence panel. The numbers are
    already interpolated here so the frontend renders strings and shapes,
    never wording of its own (spec §12.1)."""

    title: str
    submitted_label: str
    registered_label: str
    sha_label: str
    sha_summary: str
    fingerprint_label: str
    fingerprint_summary: str
    scale_summary: str | None = None
    frames_summary: str | None = None

    # plain register — the two-line headline a non-specialist reads first,
    # worded for whatever they actually sent (picture / wording / footage)
    plain_title: str = ""
    plain_file_label: str = ""
    plain_content_label: str = ""
    plain_file_line: str = ""
    plain_content_line: str = ""
    plain_explain: str = ""
    technical_toggle: str = ""


class WhyPayload(BaseModel):
    """The reasoning behind the verdict: which rule fired, and what escalated
    it. Strictness is only defensible if it can be read back."""

    label: str
    rule: str  # machine code, for the technical view
    explanation: str
    escalated_by_label: str = ""
    escalated_by: list[str] = []  # plain strings for the signals that escalated
    strict_note: str = ""


class CardPayload(BaseModel):
    verification_id: str
    verdict: str
    headline: str
    body: str
    why: WhyPayload | None = None
    # Plain-language register for a non-specialist reader. Same verdict, same
    # facts, no jargon — the card leads with these and keeps the formal
    # strings above for the technical view (spec §12.1: both come from i18n,
    # neither is invented in the frontend).
    plain_headline: str = ""
    plain_body: str = ""
    plain_reason_strings: list[str] = []
    reasons: list[str]
    reason_strings: list[str]
    advice: list[str]
    buttons: list[Button]
    matched_entity: EntityRef | None = None
    matched_communication: CommunicationRef | None = None
    claimed_entity_text: str | None = None
    pipeline_trace: list[dict[str, Any]]
    match_evidence: MatchEvidence | None = None
    evidence_copy: EvidenceCopy | None = None
    locale: str


class RenderContext(BaseModel):
    """Everything render_verdict needs beyond the raw Decision, resolved by
    the caller (verify.py) via DB lookups — this module stays DB-free so it
    can be shared by the simulator and the WhatsApp adapter unchanged."""

    verification_id: str
    decision: Decision
    locale: str = "en"
    matched_entity: EntityRef | None = None
    matched_communication: CommunicationRef | None = None
    claimed_entity_text: str | None = None
    revoked_date: str | None = None
    certificate_url: str | None = None
    sebi_check_url: str = "#"
    match_evidence: MatchEvidence | None = None


class _Defaulting(dict):
    """Missing placeholders render as an em dash rather than raising."""

    def __missing__(self, key: str) -> str:
        return "—"


def _reason_string(strings: dict[str, Any], code: str) -> str:
    return strings.get("reasons", {}).get(code, code)


# Codes that carry nothing for a lay reader and are dropped from the plain
# list (never from `reasons`/`reason_strings`, which stay complete for the
# technical view and for any downstream consumer).
#   C2PA_MISSING     — an absence of an optional feature, true on essentially
#                      every forwarded file, and it led every card.
#   NO_OFFICIAL_CLAIM — the plain body already says exactly this.
_PLAIN_SUPPRESSED = {ReasonCode.C2PA_MISSING, ReasonCode.NO_OFFICIAL_CLAIM}


# Reading order for the plain list. Distinct from _TOP_REASON_PRIORITY, which
# ranks by alarm to pick LIKELY_FAKE's {top_reason}: here a caveat the reader
# must act on (a revoked key) has to outrank the match that proved authenticity,
# even though the match is the more "positive" finding.
_PLAIN_REASON_ORDER = [
    ReasonCode.BLACKLIST_MATCH,
    ReasonCode.LOOKALIKE_DOMAIN,
    ReasonCode.HOMOGLYPH_ENTITY,
    ReasonCode.TAMPERED_SIGNATURE,
    ReasonCode.TAMPERED_CONTENT,
    ReasonCode.KEY_REVOKED_AFTER_SIGNING,
    ReasonCode.COMM_WITHDRAWN,
    ReasonCode.PAYMENT_ASK,
    ReasonCode.RISK_PHRASES,
    ReasonCode.URL_RISK,
    ReasonCode.SIG_CHAIN_VALID,
    ReasonCode.HASH_EXACT_MATCH,
    ReasonCode.PHASH_MATCH,
    ReasonCode.PDQ_MATCH,
    ReasonCode.SIMHASH_MATCH,
    ReasonCode.VIDEO_MATCH,
    ReasonCode.PHASH_NEAR,
]


def _plain_reasons(strings: dict[str, Any], codes: list[str]) -> list[str]:
    """Plain reason lines, most significant first, noise removed."""
    suppressed = {r.value for r in _PLAIN_SUPPRESSED}
    priority = {code.value: i for i, code in enumerate(_PLAIN_REASON_ORDER)}
    kept = sorted(
        (c for c in codes if c not in suppressed),
        key=lambda c: priority.get(c, len(priority)),
    )
    return [_plain_reason_string(strings, c) for c in kept]


def _plain_reason_string(strings: dict[str, Any], code: str) -> str:
    """Plain wording, falling back to the formal string, then the bare code —
    so a locale that hasn't translated a code yet degrades instead of leaking
    an enum name."""
    plain = strings.get("plain", {}).get("reasons", {}).get(code)
    return plain if plain else _reason_string(strings, code)


def _why(strings: dict[str, Any], d: Decision) -> WhyPayload | None:
    block = strings.get("why")
    if not block:
        return None
    escalated = [_plain_reason_string(strings, c.value) for c in d.escalating_reasons]
    return WhyPayload(
        label=block["label"],
        rule=d.rule.value,
        explanation=block.get("rules", {}).get(d.rule.value, ""),
        escalated_by_label=block.get("escalated_by", "") if escalated else "",
        escalated_by=escalated,
        strict_note=block.get("strict_note", "") if escalated else "",
    )


def stage_copy(locale: str, stage: str, detail_key: str | None = None, **fmt: Any) -> tuple[str, str]:
    """Localized (label, detail) for one live-check stage. Lives here because
    §12.1 makes this module the only place machine outcomes become words."""
    live = _load(locale).get("live", {})
    label = live.get("stages", {}).get(stage, stage)
    detail = live.get("details", {}).get(detail_key or "", "")
    if detail and fmt:
        detail = detail.format_map(_Defaulting(fmt))
    return label, detail


def _evidence_copy(strings: dict[str, Any], ev: MatchEvidence) -> EvidenceCopy | None:
    """Localized sentences describing `ev`, with the real numbers filled in."""
    block = strings.get("evidence")
    if not block:
        return None

    sha_summary = block["sha_identical"] if ev.sha256_identical else block["sha_differs"]

    fingerprint_summary = block["fingerprint_none"]
    scale_summary = None
    if ev.hash_comparison is not None:
        hc = ev.hash_comparison
        fingerprint_summary = block["fingerprint_summary"].format_map(
            _Defaulting({"distance": hc.distance, "bits": hc.bits})
        )
        key = {"match": "scale_match", "near": "scale_near", "miss": "scale_miss"}[ev.outcome]
        scale_summary = block[key].format_map(
            _Defaulting({"threshold": hc.threshold_match, "near": hc.threshold_near or ""})
        )

    frames_summary = None
    if ev.video_comparison is not None:
        vc = ev.video_comparison
        frames_summary = block["frames_summary"].format_map(
            _Defaulting({
                "matched": vc.matched_frames,
                "total": vc.total_frames,
                "percent": round(vc.ratio * 100),
                "threshold": round(vc.threshold_ratio * 100),
            })
        )
        if ev.hash_comparison is None:
            fingerprint_summary = block["fingerprint_video"]

    # The plain register reduces the whole comparison to one contrast: the
    # bytes changed, the content didn't. How that is worded depends on what
    # the reader actually sent — describing a forwarded SMS in terms of "the
    # picture" is nonsense, so the copy is chosen per content kind.
    kinds = block.get("kinds", {})
    k = kinds.get(ev.content_kind) or kinds.get("image") or {}

    content_line = {
        "match": k.get("content_same", ""),
        "near": k.get("content_close", ""),
        "miss": k.get("content_different", ""),
    }[ev.outcome]
    plain_explain = {
        "match": k.get("explain_match", ""),
        "near": k.get("explain_near", ""),
        "miss": k.get("explain_miss", ""),
    }[ev.outcome]

    return EvidenceCopy(
        title=block["title"],
        submitted_label=block["submitted_label"],
        registered_label=block["registered_label"],
        sha_label=block["sha_label"],
        sha_summary=sha_summary,
        fingerprint_label=block["fingerprint_label"],
        fingerprint_summary=fingerprint_summary,
        scale_summary=scale_summary,
        frames_summary=frames_summary,
        plain_title=block["plain_title"],
        plain_file_label=k.get("file_label", ""),
        plain_content_label=k.get("content_label", ""),
        plain_file_line=(
            k.get("file_same", "") if ev.sha256_identical else k.get("file_changed", "")
        ),
        plain_content_line=content_line,
        plain_explain=plain_explain,
        technical_toggle=block["technical_toggle"],
    )


def render_verdict(ctx: RenderContext) -> CardPayload:
    strings = _load(ctx.locale)
    d: Decision = ctx.decision
    reason_values = [r.value for r in d.reasons]
    reason_strings = [_reason_string(strings, code) for code in reason_values]

    v = strings["verdict"][_VERDICT_KEY[d.verdict]]
    plain_v = strings.get("plain", {}).get("verdict", {}).get(_VERDICT_KEY[d.verdict], {})

    fmt: dict[str, Any] = {}
    if ctx.matched_entity is not None:
        fmt["entity"] = ctx.matched_entity.name
        fmt["reg"] = ctx.matched_entity.sebi_reg_no
    if ctx.matched_communication is not None:
        # date only — the raw ISO timestamp reads as machine output on a card
        fmt["date"] = (ctx.matched_communication.published_at or "")[:10]
        fmt["channel"] = ctx.matched_communication.channel or ""
        fmt["seq"] = ctx.matched_communication.log_seq
    if ctx.claimed_entity_text:
        fmt["claimed"] = ctx.claimed_entity_text
    elif d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED:
        fmt["claimed"] = "an official source"
    if ctx.revoked_date:
        fmt["revoked_date"] = ctx.revoked_date

    top_code = next((c for c in _TOP_REASON_PRIORITY if c in d.reasons), None)
    top_reason = _reason_string(strings, top_code.value) if top_code else ""
    if not top_reason and reason_strings:
        top_reason = reason_strings[0]
    fmt["top_reason"] = top_reason

    # the plain body interpolates the plain wording of the same top reason
    plain_fmt = dict(fmt)
    plain_top = _plain_reason_string(strings, top_code.value) if top_code else ""
    plain_fmt["top_reason"] = plain_top or top_reason

    # format_map over a defaulting dict, not .format(**fmt): a placeholder the
    # caller didn't populate used to raise KeyError and fall back to the RAW
    # template, printing literal "{entity}"/"{revoked_date}" braces at the
    # user. Degrade one placeholder instead of wrecking the whole sentence.
    body = v["body"].format_map(_Defaulting(fmt))

    advice: list[str] = []
    buttons: list[Button] = []
    if d.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_NOTICE):
        advice.append(strings["advice"]["sebi_check"])
        if ctx.certificate_url:
            buttons.append(
                Button(kind="certificate", label=strings["button"]["view_certificate"],
                       url=ctx.certificate_url)
            )
        buttons.append(
            Button(kind="sebi_check", label=strings["button"]["sebi_check"], url=ctx.sebi_check_url)
        )
    elif d.verdict in (Verdict.OFFICIAL_CLAIM_UNVERIFIED, Verdict.LIKELY_FAKE):
        advice.append(strings["advice"]["sebi_check"])
        if d.verdict == Verdict.LIKELY_FAKE:
            advice.append(strings["advice"]["radar_added"])
        buttons.append(
            Button(kind="sebi_check", label=strings["button"]["sebi_check"], url=ctx.sebi_check_url)
        )
    buttons.append(Button(kind="expand_trace", label=strings["button"]["expand_trace"], url=""))

    return CardPayload(
        verification_id=ctx.verification_id,
        verdict=d.verdict.value,
        headline=v["title"],
        body=body,
        why=_why(strings, d),
        plain_headline=plain_v.get("title", v["title"]),
        plain_body=(
            plain_v["body"].format_map(_Defaulting(plain_fmt)) if plain_v.get("body") else body
        ),
        plain_reason_strings=_plain_reasons(strings, reason_values),
        reasons=reason_values,
        reason_strings=reason_strings,
        advice=advice,
        buttons=buttons[:3],
        matched_entity=ctx.matched_entity,
        matched_communication=ctx.matched_communication,
        claimed_entity_text=ctx.claimed_entity_text,
        pipeline_trace=[t.model_dump() for t in d.trace],
        match_evidence=ctx.match_evidence,
        evidence_copy=(
            _evidence_copy(strings, ctx.match_evidence)
            if ctx.match_evidence is not None
            else None
        ),
        locale=ctx.locale,
    )
