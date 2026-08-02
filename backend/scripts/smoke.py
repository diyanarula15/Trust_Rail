"""End-to-end smoke (spec layout): seed world → publish via API → log/STH
checks → revocations. Uses a generated PDF so it never depends on owner
media. Exits non-zero on any failure.
"""
import io
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Entity, Key, KeyRole
from app.trust import merkle
from app.trust.ca import ensure_trust_material
from scripts.seed import seed_entities, wipe


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def check(cond: bool, label: str) -> None:
    print(("  ok    " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def main() -> None:
    client = TestClient(app)
    settings = get_settings()
    material = ensure_trust_material(settings.trust_dir)

    print("smoke: reseed base world")
    with SessionLocal() as db:
        wipe(db)
        seed_entities(db)
        db.commit()

        kumaon = db.execute(select(Entity).where(Entity.name == "Kumaon Metals Ltd")).scalar_one()
        maker = db.execute(select(Key).where(Key.entity_id == kumaon.id, Key.role == KeyRole.maker)).scalar_one()
        checker = db.execute(select(Key).where(Key.entity_id == kumaon.id, Key.role == KeyRole.checker)).scalar_one()

    h = client.get("/healthz").json()
    check(h["db"] and h["redis"], "healthz db+redis")

    print("smoke: draft → maker sign → checker co-sign & publish (market_moving PDF)")
    r = client.post(
        "/api/issuer/communications",
        data={"entity_id": str(kumaon.id), "title": "Smoke filing", "channel": "filing", "impact": "market_moving"},
        files={"file": ("smoke.pdf", _pdf_bytes(), "application/pdf")},
        headers={"X-Demo-Persona": str(maker.id)},
    ).json()
    check(r["ok"] and r["data"]["status"] == "draft", "draft created with artifact sha256")
    comm_id = r["data"]["id"]

    r = client.post(f"/api/issuer/communications/{comm_id}/cosign", headers={"X-Demo-Persona": str(checker.id)}).json()
    check(not r["ok"], "publish before maker-sign rejected")

    r = client.post(f"/api/issuer/communications/{comm_id}/sign", headers={"X-Demo-Persona": str(checker.id)}).json()
    check(not r["ok"], "maker-sign with checker persona rejected")

    r = client.post(f"/api/issuer/communications/{comm_id}/sign", headers={"X-Demo-Persona": str(maker.id)}).json()
    check(r["ok"] and r["data"]["status"] == "maker_signed", "maker signed")

    r = client.post(f"/api/issuer/communications/{comm_id}/cosign", headers={"X-Demo-Persona": str(maker.id)}).json()
    check(not r["ok"], "co-sign with maker persona rejected (checker required)")

    r = client.post(f"/api/issuer/communications/{comm_id}/cosign", headers={"X-Demo-Persona": str(checker.id)}).json()
    check(r["ok"] and r["data"]["status"] == "published", "published")
    seq1, old_root, new_root = r["data"]["log_seq"], r["data"]["old_root"], r["data"]["new_root"]
    check(old_root != new_root, f"log root changed on publish (seq {seq1})")

    print("smoke: log root, STH signature, inclusion proof")
    root = client.get("/api/log/root").json()["data"]
    check(root["tree_size"] == seq1 + 1 and root["root_hash"] == new_root, "log root matches publish response")
    check(root["registry_public_key"] == material.registry_sth.public_key_b64, "root exposes registry public key")
    check(
        merkle.verify_sth(root["tree_size"], root["root_hash"], datetime.fromisoformat(root["timestamp"]),
                          root["sth_sig"], root["registry_public_key"]),
        "STH signature verifies",
    )
    proof = client.get(f"/api/log/entries/{seq1}/proof").json()["data"]
    check(
        merkle.verify_inclusion(proof["leaf_hash"], proof["leaf_index"], proof["audit_path"],
                                proof["tree_size"], proof["root_hash"]),
        "inclusion proof verifies",
    )

    print("smoke: publish a second comm — seq increments")
    r = client.post(
        "/api/issuer/communications",
        data={"entity_id": str(kumaon.id), "title": "Smoke filing 2", "channel": "filing", "impact": "standard"},
        files={"file": ("smoke2.pdf", _pdf_bytes() + b" ", "application/pdf")},
        headers={"X-Demo-Persona": str(maker.id)},
    ).json()
    comm2 = r["data"]["id"]
    client.post(f"/api/issuer/communications/{comm2}/sign", headers={"X-Demo-Persona": str(maker.id)})
    r = client.post(f"/api/issuer/communications/{comm2}/cosign", headers={"X-Demo-Persona": str(maker.id)}).json()
    check(r["ok"] and r["data"]["log_seq"] == seq1 + 1, "standard comm publishes without checker; seq incremented")

    print("smoke: revocations are logged events")
    r = client.post(f"/api/issuer/communications/{comm2}/revoke", headers={"X-Demo-Persona": str(maker.id)}).json()
    check(r["ok"] and r["data"]["status"] == "revoked" and r["data"]["revocation_log_seq"] == seq1 + 2,
          "communication withdrawn + logged")
    r = client.post(f"/api/admin/keys/{maker.id}/revoke", json={"reason": "smoke: simulated compromise"}).json()
    check(r["ok"] and r["data"]["status"] == "revoked" and r["data"]["revocation_log_seq"] == seq1 + 3,
          "key revoked + logged")

    root = client.get("/api/log/root").json()["data"]
    check(root["tree_size"] == seq1 + 4, "final tree size accounts for every event")
    proof = client.get(f"/api/log/entries/{seq1}/proof").json()["data"]
    check(
        merkle.verify_inclusion(proof["leaf_hash"], proof["leaf_index"], proof["audit_path"],
                                proof["tree_size"], proof["root_hash"]),
        "original publish still provable after revocations (log intact)",
    )

    print("SMOKE PASS")
    # This script wipes the demo world to build its own fixtures, and leaves
    # those behind. Silently doing so has cost real debugging time more than
    # once (see PROGRESS.md, Epic 5 and the match-evidence entry): the next
    # /verify against a wiped registry honestly returns "no match", which
    # reads exactly like a broken matcher. Say so loudly instead.
    print()
    print("!" * 72)
    print("The demo world has been REPLACED by smoke fixtures.")
    print("Before demoing or checking /verify by hand, restore it:")
    print("    python -m scripts.seed          (or: make demo-reset)")
    print("!" * 72)


if __name__ == "__main__":
    main()
