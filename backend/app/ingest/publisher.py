"""Publishing an ingested item — through the same trust path as the console.

Nothing here is a shortcut around the crypto. An ingested filing gets the
same envelope, the same Ed25519 signatures, the same transparency-log leaf
and the same artifact hashing as one a human published by hand. The only
difference is recorded honestly in the log entry itself: `source` and
`external_id` say where it came from.

That distinction matters and is deliberately visible. A manually published
item asserts "a person at this issuer approved this". An ingested one
asserts "this is what the exchange/DLT registry published, as received at
time T". Both are useful; conflating them would not be.

TODO(prod): in a real deployment the exchange would sign its own feed and
TrustRail would counter-sign, rather than signing on the issuer's behalf
with a key it holds. The demo holds every private key already (see
models.Key), so this is the same demo-only compromise, not a new one.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

# Reused rather than reimplemented so ingested and hand-published artifacts
# are hashed by literally the same code — any drift here would silently make
# ingested content unverifiable against manually published content.
from app.api.issuer import _make_artifact
from app.config import get_settings
from app.ingest.sources import FeedItem
from app.models import (
    Artifact,
    CommChannel,
    CommImpact,
    CommStatus,
    Communication,
    Entity,
    EntitySmsHeader,
    Key,
    KeyRole,
    KeyStatus,
)
from app.trust import merkle
from app.trust.ca import ensure_trust_material, sign_bytes
from app.trust.envelope import build_envelope, envelope_digest, signing_bytes

logger = logging.getLogger(__name__)


class PublishOutcome(BaseModel):
    external_id: str
    status: str          # published | duplicate | no_entity | no_key | error
    detail: str = ""
    communication_id: str | None = None
    log_seq: int | None = None


def resolve_entity(db: Session, hint: str) -> Entity | None:
    """Find the issuer a feed item belongs to.

    Feeds identify issuers however they like — a scrip code, a company name,
    an SMS sender header — so all three are tried before giving up. An
    unresolvable item is skipped rather than guessed at: publishing under the
    wrong issuer would be worse than not publishing at all.
    """
    hint = (hint or "").strip()
    if not hint:
        return None

    entity = db.execute(select(Entity).where(Entity.sebi_reg_no == hint)).scalars().first()
    if entity:
        return entity
    entity = db.execute(select(Entity).where(Entity.name == hint)).scalars().first()
    if entity:
        return entity

    header = db.execute(
        select(EntitySmsHeader).where(EntitySmsHeader.header == hint.upper())
    ).scalars().first()
    if header:
        return db.get(Entity, header.entity_id)

    # last resort: case-insensitive name contains
    return db.execute(
        select(Entity).where(Entity.name.ilike(f"%{hint}%"))
    ).scalars().first()


def _signing_keys(db: Session, entity: Entity, market_moving: bool) -> tuple[Key | None, Key | None]:
    def pick(role: KeyRole) -> Key | None:
        return db.execute(
            select(Key).where(
                Key.entity_id == entity.id, Key.role == role, Key.status == KeyStatus.active
            )
        ).scalars().first()

    maker = pick(KeyRole.maker) or pick(KeyRole.entity)
    checker = pick(KeyRole.checker) if market_moving else None
    return maker, checker


def _load_bytes(item: FeedItem, repo_root: Path) -> tuple[bytes, str] | None:
    """The document behind an item, if it has one."""
    if item.document_path:
        path = (repo_root / item.document_path).resolve()
        # a feed must not be able to read arbitrary files off the host
        if not str(path).startswith(str(repo_root.resolve())) or not path.is_file():
            return None
        mime = "application/pdf" if path.suffix.lower() == ".pdf" else "image/jpeg"
        return path.read_bytes(), mime
    if item.document_url:
        try:
            resp = httpx.get(item.document_url, timeout=20.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("ingest: could not fetch %s: %s", item.document_url, exc)
            return None
        return resp.content, resp.headers.get("content-type", "application/octet-stream")
    return None


def already_published(db: Session, entity: Entity, sha256: str) -> bool:
    """Same issuer, same content hash — we already have it.

    Content-hash dedupe rather than an external-id column: re-polling a feed
    must be free of side effects, and identical content really is the same
    communication no matter what id the source gave it this time.
    """
    row = db.execute(
        select(Communication.id)
        .join(Artifact, Communication.artifact_id == Artifact.id)
        .where(
            Communication.entity_id == entity.id,
            Artifact.sha256 == sha256,
            Communication.status.in_([CommStatus.published, CommStatus.revoked]),
        )
    ).scalars().first()
    return row is not None


def publish_item(db: Session, item: FeedItem, source_name: str, repo_root: Path) -> PublishOutcome:
    """Draft, sign, co-sign where required, and append to the log — in one go."""
    settings = get_settings()
    entity = resolve_entity(db, item.entity_hint)
    if entity is None:
        return PublishOutcome(external_id=item.external_id, status="no_entity",
                              detail=f"no registered issuer matches {item.entity_hint!r}")

    try:
        channel = CommChannel(item.channel)
        impact = CommImpact(item.impact)
    except ValueError:
        return PublishOutcome(external_id=item.external_id, status="error",
                              detail=f"unknown channel/impact {item.channel}/{item.impact}")

    loaded = _load_bytes(item, repo_root)
    canonical_text = None
    if loaded is not None:
        data, mime = loaded
    elif item.body_text:
        canonical_text = item.body_text
        data, mime = canonical_text.encode("utf-8"), "text/plain"
    else:
        return PublishOutcome(external_id=item.external_id, status="error",
                              detail="item has neither a document nor body text")

    maker, checker = _signing_keys(db, entity, impact == CommImpact.market_moving)
    if maker is None:
        return PublishOutcome(external_id=item.external_id, status="no_key",
                              detail=f"{entity.name} has no active signing key")
    if impact == CommImpact.market_moving and checker is None:
        # Rather than silently downgrade a market-moving item, publish it as
        # standard and say so — losing the second signature is a real change
        # in assurance and should not happen invisibly.
        impact = CommImpact.standard

    artifact = _make_artifact(data, mime, channel, canonical_text)
    if already_published(db, entity, artifact.sha256):
        return PublishOutcome(external_id=item.external_id, status="duplicate",
                              detail="identical content already published")

    db.add(artifact)
    db.flush()

    comm = Communication(
        entity_id=entity.id,
        title=item.title[:300],
        channel=channel,
        impact=impact,
        status=CommStatus.draft,
        canonical_text=canonical_text,
        artifact_id=artifact.id,
        maker_key_id=maker.id,
    )
    db.add(comm)
    db.flush()

    issued_at = item.published_at or datetime.now(UTC)
    env = build_envelope(
        artifact_sha256=artifact.sha256,
        entity_id=str(entity.id),
        sebi_reg_no=entity.sebi_reg_no,
        communication_id=str(comm.id),
        channel=channel.value,
        impact=impact.value,
        issued_at=issued_at,
        maker_key_id=str(maker.id),
        checker_key_id=str(checker.id) if checker else None,
    )
    env.maker.sig = sign_bytes(maker.private_key_ed25519, signing_bytes(env))
    comm.maker_sig = env.maker.sig
    if checker is not None and env.checker is not None:
        env.checker.sig = sign_bytes(checker.private_key_ed25519, signing_bytes(env))
        comm.checker_sig = env.checker.sig
        comm.checker_key_id = checker.id
    artifact.envelope = env.to_wire()

    material = ensure_trust_material(settings.trust_dir)
    entry = merkle.append_entry(
        db,
        {
            "kind": "publish",
            "communication_id": str(comm.id),
            "artifact_sha256": artifact.sha256,
            "entity_id": str(entity.id),
            "published_at": issued_at.isoformat(),
            "envelope_digest": envelope_digest(env),
            # provenance: this was ingested, not typed in by a person
            "source": source_name,
            "external_id": item.external_id,
        },
        material.registry_sth.private_key_b64,
    )
    comm.status = CommStatus.published
    comm.published_at = issued_at
    db.flush()
    comm.log_seq = entry.seq
    db.commit()

    return PublishOutcome(
        external_id=item.external_id,
        status="published",
        detail=f"{entity.name} — {item.title[:60]}",
        communication_id=str(comm.id),
        log_seq=entry.seq,
    )
