"""Seed the demo world (spec §15). Idempotent: wipe + rebuild.

Implemented: §15.1 trust material, §15.2 entities, §15.3 published
communications (needs owner media in assets_input/ — FAILS LOUDLY when
missing, by design; set SEED_ALLOW_MISSING_ASSETS=1 to seed a partial
world during development), §15.4 blacklist fixtures (domain + phrase —
the phash/"RECYCLED-CREATIVE" campaign fixture needs a purpose-built edited
image and isn't built yet, see PROGRESS.md), §15.5 telemetry history +
cheat sheet.
"""
import os
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Artifact,
    Communication,
    DomainKind,
    Entity,
    EntityDomain,
    EntityKind,
    EntitySmsHeader,
    InputKind,
    Key,
    KeyRole,
    LogEntry,
    ScamBlacklist,
    BlacklistKind,
    Verdict,
    Verification,
    VerifyChannel,
    ViewToken,
)
from app.trust.ca import ensure_trust_material, generate_ed25519_keypair


@dataclass(frozen=True)
class EntityFixture:
    name: str
    kind: EntityKind
    reg_no: str
    domain: str
    sms_header: str
    featured: bool = False  # featured entities get separate maker+checker keys


ENTITIES: list[EntityFixture] = [
    EntityFixture("Demo Securities Board", EntityKind.regulator, "DEMO-REG-000001", "demosecboard.example", "DSBRD"),
    EntityFixture("National Demo Exchange (NDX)", EntityKind.exchange, "DEMO-EXC-000010", "ndx.example", "NDXIN"),
    EntityFixture("Bharat Demo Exchange (BDX)", EntityKind.exchange, "DEMO-EXC-000011", "bdx.example", "BDXIN"),
    EntityFixture("Meridian Broking Ltd", EntityKind.broker, "DEMO-INZ-000123", "meridianbroking.example", "MERIDN", featured=True),
    EntityFixture("Alpha Capital Services", EntityKind.broker, "DEMO-INZ-000124", "alphacapital.example", "ALPHCP"),
    EntityFixture("Suraksha Securities", EntityKind.broker, "DEMO-INZ-000125", "surakshasec.example", "SURKSH"),
    EntityFixture("Lotus Investmart", EntityKind.broker, "DEMO-INZ-000126", "lotusinvest.example", "LOTUSI"),
    EntityFixture("Kumaon Metals Ltd", EntityKind.listed_company, "DEMO-INE-000451", "kumaonmetals.example", "KUMAON", featured=True),
    EntityFixture("Vasudha Agrotech Ltd", EntityKind.listed_company, "DEMO-INE-000452", "vasudhaagro.example", "VASUDH"),
    EntityFixture("Nivara Housing Finance", EntityKind.listed_company, "DEMO-INE-000453", "nivarahf.example", "NIVARA"),
    EntityFixture("Suvarna Mutual Fund", EntityKind.mutual_fund, "DEMO-MF-000021", "suvarnamf.example", "SUVRNA", featured=True),
    EntityFixture("Aranya Asset Management", EntityKind.mutual_fund, "DEMO-MF-000022", "aranyaamc.example", "ARANYA"),
]


def wipe(db) -> None:
    """Delete all demo rows in FK-safe order."""
    for model in (
        ViewToken,
        Verification,
        Communication,
        LogEntry,
        Artifact,
        Key,
        EntitySmsHeader,
        EntityDomain,
        ScamBlacklist,
        Entity,
    ):
        db.execute(delete(model))


def _make_key(entity: Entity, role: KeyRole, label: str) -> Key:
    kp = generate_ed25519_keypair()
    return Key(
        entity_id=entity.id,
        label=label,
        role=role,
        public_key_ed25519=kp.public_key_b64,
        private_key_ed25519=kp.private_key_b64,  # DEMO ONLY — TODO(prod): HSM
    )


def seed_entities(db) -> list[Entity]:
    entities: list[Entity] = []
    for fx in ENTITIES:
        entity = Entity(name=fx.name, kind=fx.kind, sebi_reg_no=fx.reg_no)
        db.add(entity)
        db.flush()
        db.add(EntityDomain(entity_id=entity.id, domain=fx.domain, kind=DomainKind.web))
        db.add(EntitySmsHeader(entity_id=entity.id, header=fx.sms_header))
        if fx.featured:
            db.add(_make_key(entity, KeyRole.maker, f"{fx.name} — maker"))
            db.add(_make_key(entity, KeyRole.checker, f"{fx.name} — checker"))
        else:
            db.add(_make_key(entity, KeyRole.entity, f"{fx.name} — entity key"))
        entities.append(entity)
    return entities


# §15.3 published communications: (entity, title, channel, impact, source)
# source: filename in assets_input/ or ("text", body) for text-born comms.
ASSET_DIR_NAME = "assets_input"
# Media now comes from fixtures/generated/ (committed, produced by
# `python -m scripts.gen_fixtures`) rather than owner-supplied files in
# assets_input/. The originals there were real BSE/NSE filings from real
# listed companies, which contradicted the project's own "no real companies"
# claim and meant DEMO.md step 4 instructed doctoring a real issuer's
# published financials. Generated fixtures are fictional end to end, and a
# fresh clone can now seed and run the acceptance suite with no owner media.
GENERATED_DIR_NAME = "fixtures/generated"
EXPECTED_FILES = [
    "filing_kumaon_q1.pdf", "filing_kumaon_capex.pdf", "filing_nivara_annual.pdf",
    "notice_meridian_margin.jpg", "notice_suvarna_nav.jpg", "notice_ndx_calendar.jpg",
]

PUBLISH_PLAN: list[tuple[str, str, str, str, str | tuple[str, str]]] = [
    ("Kumaon Metals Ltd", "Q1 FY27 results filing", "filing", "standard", "filing_kumaon_q1.pdf"),
    ("Kumaon Metals Ltd", "Board approval — capacity expansion", "filing", "market_moving", "filing_kumaon_capex.pdf"),
    ("Nivara Housing Finance", "Annual disclosure filing", "filing", "standard", "filing_nivara_annual.pdf"),
    ("Meridian Broking Ltd", "New margin rules infographic", "image", "standard", "notice_meridian_margin.jpg"),
    ("Suvarna Mutual Fund", "Scheme performance summary", "image", "standard", "notice_suvarna_nav.jpg"),
    ("National Demo Exchange (NDX)", "Trading calendar notice", "image", "standard", "notice_ndx_calendar.jpg"),
    # NOTE: the CEO announcement video is deliberately NOT auto-published here.
    # DEMO.md step 1 publishes it live (draft -> sign -> co-sign) so the
    # judges watch the log root update in real time — publishing it twice
    # (once here, once live) would leave two candidates with the identical
    # artifact hash and an ambiguous match on which log entry is "the" one.
    ("Meridian Broking Ltd", "Margin shortfall notice", "sms", "standard",
     ("text", "MERIDN: Margin shortfall in your account. Add funds by T+1 via the official app. Never share OTPs. — Meridian Broking Ltd, SEBI reg DEMO-INZ-000123")),
    ("Suvarna Mutual Fund", "NAV update", "sms", "standard",
     ("text", "SUVRNA: NAV for Suvarna Bluechip Fund as on 10 Jul 2026: ₹84.31. Statement at suvarnamf.example. — Suvarna Mutual Fund")),
    ("National Demo Exchange (NDX)", "Settlement holiday notice", "sms", "standard",
     ("text", "NDXIN: Settlement holiday on 17 Jul 2026. Pay-in/pay-out shifts to next working day. — National Demo Exchange")),
    ("Suvarna Mutual Fund", "Folio statement notice", "email", "standard",
     ("text", "Dear investor, your July folio statement for Suvarna Mutual Fund is available at suvarnamf.example/statements. We never ask for OTPs or payments over email. — Suvarna Mutual Fund, SEBI reg DEMO-MF-000021")),
]


def _persona_key(db, entity_name: str, role: KeyRole) -> Key:
    entity = db.execute(select(Entity).where(Entity.name == entity_name)).scalar_one()
    key = db.execute(
        select(Key).where(Key.entity_id == entity.id, Key.role == role)
    ).scalars().first()
    if key is None:  # non-featured entities sign with their single entity key
        key = db.execute(
            select(Key).where(Key.entity_id == entity.id, Key.role == KeyRole.entity)
        ).scalars().first()
    assert key is not None, f"no signing key for {entity_name}"
    return key


def seed_communications(db, repo_root: Path) -> int:
    """§15.3 — publish through the real API surface (TestClient) so seed
    exercises the exact maker → checker → log path."""
    from fastapi.testclient import TestClient

    from app.main import app

    asset_dir = repo_root / GENERATED_DIR_NAME
    missing = [f for f in EXPECTED_FILES if not (asset_dir / f).exists()]
    if missing:
        print("\n" + "!" * 72, file=sys.stderr)
        print("SEED §15.3 FAILED — generated fixtures are missing:", file=sys.stderr)
        for f in missing:
            print(f"  MISSING  {asset_dir / f}", file=sys.stderr)
        print("\nRun this first, it takes a second and needs no owner media:", file=sys.stderr)
        print("    python -m scripts.gen_fixtures", file=sys.stderr)
        print("!" * 72 + "\n", file=sys.stderr)
        if os.environ.get("SEED_ALLOW_MISSING_ASSETS") == "1":
            print("SEED_ALLOW_MISSING_ASSETS=1 → continuing with a partial world (dev only).")
            return 0
        sys.exit(2)

    client = TestClient(app)
    published = 0
    for entity_name, title, channel, impact, source in PUBLISH_PLAN:
        entity = db.execute(select(Entity).where(Entity.name == entity_name)).scalar_one()
        maker = _persona_key(db, entity_name, KeyRole.maker)

        form = {"entity_id": str(entity.id), "title": title, "channel": channel, "impact": impact}
        files = None
        if isinstance(source, tuple):
            form["canonical_text"] = source[1]
        else:
            path = asset_dir / source
            mime = {"pdf": "application/pdf", "jpg": "image/jpeg", "mp4": "video/mp4"}[path.suffix[1:]]
            files = {"file": (source, path.read_bytes(), mime)}

        r = client.post("/api/issuer/communications", data=form, files=files,
                        headers={"X-Demo-Persona": str(maker.id)})
        assert r.status_code == 200 and r.json()["ok"], f"draft failed: {title}: {r.text}"
        comm_id = r.json()["data"]["id"]

        r = client.post(f"/api/issuer/communications/{comm_id}/sign",
                        headers={"X-Demo-Persona": str(maker.id)})
        assert r.json()["ok"], f"sign failed: {title}: {r.text}"

        cosigner = (
            _persona_key(db, entity_name, KeyRole.checker)
            if impact == "market_moving"
            else maker
        )
        r = client.post(f"/api/issuer/communications/{comm_id}/cosign",
                        headers={"X-Demo-Persona": str(cosigner.id)})
        assert r.json()["ok"], f"publish failed: {title}: {r.text}"
        published += 1
    return published


# §15.4 scam fixtures — domain + phrase only (see module docstring)
BLACKLIST_FIXTURES: list[tuple[BlacklistKind, str, str, str]] = [
    (BlacklistKind.domain, "rneridianbroking-refunds.top", "FXROAD-DEMO", "seed"),
    (BlacklistKind.domain, "demosecboard-verify.xyz", "FXROAD-DEMO", "seed"),
    (BlacklistKind.phrase, "guaranteed 3% daily returns", "FXROAD-DEMO", "seed"),
]


def seed_blacklist(db) -> int:
    n = 0
    for kind, value, campaign, source in BLACKLIST_FIXTURES:
        db.add(ScamBlacklist(kind=kind, value=value, campaign=campaign, source=source, active=True))
        n += 1
    return n


# §15.5 telemetry history: 60 rows over 14 days, ≥12 states, mix of verdicts.
HISTORY_STATES = ["IN-MH", "IN-KA", "IN-RJ", "IN-DL", "IN-UP", "IN-GJ",
                   "IN-TN", "IN-TS", "IN-WB", "IN-MP", "IN-HR", "IN-PB"]
HISTORY_VERDICT_WEIGHTS: list[tuple[Verdict, int]] = [
    (Verdict.INFORMATIONAL, 26),
    (Verdict.VERIFIED, 16),
    (Verdict.OFFICIAL_CLAIM_UNVERIFIED, 8),
    (Verdict.LIKELY_FAKE, 9),
    (Verdict.VERIFIED_NOTICE, 1),
]
HISTORY_CLAIMED_ENTITIES = [
    "Meridian Broking Ltd", "Kumaon Metals Ltd", "Suvarna Mutual Fund",
    "Demo Securities Board", "National Demo Exchange (NDX)",
]
_REASON_BY_VERDICT: dict[Verdict, list[str]] = {
    Verdict.VERIFIED: ["SIG_CHAIN_VALID"],
    Verdict.VERIFIED_NOTICE: ["KEY_REVOKED_AFTER_SIGNING"],
    Verdict.OFFICIAL_CLAIM_UNVERIFIED: ["ENTITY_CLAIM_STRONG"],
    Verdict.LIKELY_FAKE: ["LOOKALIKE_DOMAIN", "BLACKLIST_MATCH", "PAYMENT_ASK"],
    Verdict.INFORMATIONAL: ["NO_OFFICIAL_CLAIM"],
}


def seed_history(db, n: int = 60) -> int:
    rng = random.Random(20260712)  # fixed seed: reproducible demo history
    verdicts = [v for v, _ in HISTORY_VERDICT_WEIGHTS]
    weights = [w for _, w in HISTORY_VERDICT_WEIGHTS]
    now = datetime.now(UTC)

    for _ in range(n):
        verdict = rng.choices(verdicts, weights=weights)[0]
        flagged = verdict in (Verdict.LIKELY_FAKE, Verdict.OFFICIAL_CLAIM_UNVERIFIED)
        campaign = "FXROAD-DEMO" if verdict == Verdict.LIKELY_FAKE and rng.random() < 0.6 else None
        claimed = (
            rng.choice(HISTORY_CLAIMED_ENTITIES)
            if verdict in (Verdict.OFFICIAL_CLAIM_UNVERIFIED, Verdict.LIKELY_FAKE)
            else None
        )
        created_at = now - timedelta(
            days=rng.uniform(0, 14), hours=rng.uniform(0, 23), minutes=rng.uniform(0, 59)
        )
        db.add(
            Verification(
                channel=rng.choices([VerifyChannel.sim, VerifyChannel.whatsapp], weights=[85, 15])[0],
                input_kind=rng.choice(list(InputKind)),
                verdict=verdict,
                reasons=_REASON_BY_VERDICT[verdict],
                signals={"seeded": True},
                claimed_entity_text=claimed,
                campaign=campaign,
                state_code=rng.choice(HISTORY_STATES) if flagged or rng.random() < 0.5 else None,
                latency_ms=rng.randint(80, 2400),
                created_at=created_at,
            )
        )
    return n


def print_cheat_sheet(entities: list[Entity]) -> None:
    by_name = {e.name: e for e in entities}
    print("\n" + "=" * 72)
    print("DEMO CHEAT SHEET")
    print("=" * 72)
    print("Forward these from fixtures/generated/ in the /verify simulator:")
    print("  filing_kumaon_q1.pdf        -> Kumaon Metals Q1 results (has the revenue figure to tamper with)")
    print("  notice_*.jpg                -> Meridian / Suvarna / NDX notices")
    print("  assets_input/ceo_announcement.mp4 -> CEO announcement (published live in DEMO.md step 1)")
    print("Personas (X-Demo-Persona = key id, see /api/registry/entities):")
    for name in ("Meridian Broking Ltd", "Kumaon Metals Ltd", "Suvarna Mutual Fund"):
        e = by_name.get(name)
        if e:
            print(f"  {name}: entity_id={e.id}")
    print("Supervision dashboard: http://localhost:3000/supervision")
    print("=" * 72 + "\n")


def main() -> None:
    settings = get_settings()
    repo_root = settings.trust_dir.parent.parent

    # §15.1 trust material (create-or-load; persists across reseeds)
    material = ensure_trust_material(settings.trust_dir)
    print(f"trust material: root + registry STH keys under {settings.trust_dir}")

    with SessionLocal() as db:
        wipe(db)
        entities = seed_entities(db)
        n_blacklist = seed_blacklist(db)
        db.commit()

        featured = [fx.name for fx in ENTITIES if fx.featured]
        print(f"seeded {len(entities)} entities ({len(featured)} featured: {', '.join(featured)})")
        n_keys = sum(2 if fx.featured else 1 for fx in ENTITIES)
        print(f"seeded {n_keys} signing keys")
        print(f"seeded {n_blacklist} blacklist fixtures")
        print(f"registry STH public key: {material.registry_sth.public_key_b64}")

        n_published = seed_communications(db, repo_root)
        if n_published:
            db.expire_all()
            tree_size = len(db.execute(select(LogEntry.seq)).scalars().all())
            print(f"published {n_published} communications; transparency log has {tree_size} leaves")

        n_history = seed_history(db)
        db.commit()
        print(f"seeded {n_history} historical verification rows over 14 days")

        print_cheat_sheet(entities)


if __name__ == "__main__":
    main()
