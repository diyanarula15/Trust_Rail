"""Issuer console API (spec §9): draft → maker sign → checker co-sign &
publish → transparency log. Demo persona via `X-Demo-Persona: <key_id>`
header — no real auth. TODO(prod): proper issuer authn/z.
"""
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, get_redis
from app.models import (
    Artifact,
    CommChannel,
    CommImpact,
    CommStatus,
    Communication,
    Entity,
    Key,
    KeyRole,
    KeyStatus,
)
from app.pipeline import hashing, media
from app.schemas import err, ok
from app.trust import c2pa_embed, merkle, revocation
from app.trust.ca import ensure_trust_material, sign_bytes
from app.trust.envelope import Envelope, build_envelope, envelope_digest, signing_bytes

router = APIRouter(prefix="/api", tags=["issuer"])


class CommOut(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    title: str
    channel: str
    impact: str
    status: str
    published_at: datetime | None
    log_seq: int | None
    artifact_sha256: str | None


def _comm_out(comm: Communication) -> CommOut:
    return CommOut(
        id=comm.id,
        entity_id=comm.entity_id,
        title=comm.title,
        channel=comm.channel.value,
        impact=comm.impact.value,
        status=comm.status.value,
        published_at=comm.published_at,
        log_seq=comm.log_seq,
        artifact_sha256=comm.artifact.sha256 if comm.artifact else None,
    )


def _persona(db: Session, x_demo_persona: str | None) -> Key | None:
    if not x_demo_persona:
        return None
    try:
        return db.get(Key, uuid.UUID(x_demo_persona))
    except ValueError:
        return None


def _bad(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=err(code, message))


def _make_artifact(
    data: bytes, mime: str, channel: CommChannel, canonical_text: str | None
) -> Artifact:
    """Hash at draft time (spec §9): sha256 always; perceptual by kind.

    Content is sniffed rather than inferred from `channel`. A "filing" is not
    necessarily a PDF — plenty of exchange announcements are plain text
    (trading-window intimations, settlement notices), and feeding those bytes
    to PdfReader because the channel said "filing" raised
    `PdfStreamError: Stream has ended unexpectedly`. Found by the feed
    ingester; the issuer console could always hit it too by picking channel
    "filing" and uploading anything that isn't a PDF.
    """
    settings = get_settings()
    sha = hashing.sha256_hex(data)
    art_dir = settings.artifact_dir
    art_dir.mkdir(parents=True, exist_ok=True)

    is_pdf = data[:5] == b"%PDF-"
    if channel == CommChannel.image:
        ext = ".jpg"
    elif channel == CommChannel.video:
        ext = ".mp4"
    elif is_pdf:
        ext = ".pdf"
    else:
        ext = ".txt"
    storage = art_dir / f"{sha}{ext}"
    storage.write_bytes(data)

    phash64 = pdq256 = simhash64 = None
    video_frames = None
    if channel == CommChannel.image:
        phash64 = hashing.phash64_hex(data)
        pdq256 = hashing.pdq256_hex(data)
    elif channel == CommChannel.video:
        video_frames = media.extract_frame_phashes(storage)
    elif is_pdf:
        try:
            text = "".join(page.extract_text() or "" for page in PdfReader(storage).pages)
        except Exception:  # a malformed PDF must not take the publish down
            text = ""
        if text.strip():
            simhash64 = hashing.simhash64_hex(text)
    elif channel in (CommChannel.pdf, CommChannel.filing, CommChannel.email, CommChannel.social):
        # text-bodied filing or notice: fingerprint the words directly
        body = data.decode("utf-8", errors="replace")
        if body.strip():
            simhash64 = hashing.simhash64_hex(body)
    if canonical_text:
        simhash64 = hashing.simhash64_hex(canonical_text)

    return Artifact(
        sha256=sha,
        mime=mime,
        bytes_size=len(data),
        storage_path=str(storage),
        phash64=phash64,
        pdq256=pdq256,
        video_frame_hashes=video_frames,
        simhash64=simhash64,
        c2pa_embedded=False,
    )


@router.get("/issuer/communications")
def list_communications(entity_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    comms = (
        db.execute(
            select(Communication)
            .where(Communication.entity_id == entity_id)
            .order_by(Communication.created_at.desc())
        )
        .scalars()
        .all()
    )
    return ok([_comm_out(c) for c in comms])


@router.post("/issuer/communications")
async def create_communication(
    entity_id: uuid.UUID = Form(...),
    title: str = Form(...),
    channel: CommChannel = Form(...),
    impact: CommImpact = Form(CommImpact.standard),
    canonical_text: str | None = Form(None),
    file: UploadFile | None = None,
    x_demo_persona: str | None = Header(None),
    db: Session = Depends(get_db),
):
    entity = db.get(Entity, entity_id)
    if entity is None:
        return _bad(404, "not_found", "No such entity.")
    persona = _persona(db, x_demo_persona)
    if persona is None or persona.entity_id != entity.id:
        return _bad(403, "bad_persona", "X-Demo-Persona must be a key of this entity.")
    if (file is None) == (canonical_text is None):
        return _bad(422, "bad_input", "Provide exactly one of file or canonical_text.")

    if file is not None:
        data = await file.read()
        mime = file.content_type or "application/octet-stream"
    else:
        assert canonical_text is not None
        data = canonical_text.encode("utf-8")
        mime = "text/plain"

    artifact = _make_artifact(data, mime, channel, canonical_text)
    db.add(artifact)
    db.flush()
    comm = Communication(
        entity_id=entity.id,
        title=title,
        channel=channel,
        impact=impact,
        status=CommStatus.draft,
        canonical_text=canonical_text,
        artifact_id=artifact.id,
        maker_key_id=persona.id,
    )
    db.add(comm)
    db.commit()
    return ok(_comm_out(comm))


def _active_checker(db: Session, entity_id: uuid.UUID) -> Key | None:
    return db.execute(
        select(Key).where(
            Key.entity_id == entity_id,
            Key.role == KeyRole.checker,
            Key.status == KeyStatus.active,
        )
    ).scalars().first()


@router.post("/issuer/communications/{comm_id}/sign")
def maker_sign(
    comm_id: uuid.UUID,
    x_demo_persona: str | None = Header(None),
    db: Session = Depends(get_db),
):
    comm = db.get(Communication, comm_id)
    if comm is None:
        return _bad(404, "not_found", "No such communication.")
    if comm.status != CommStatus.draft:
        return _bad(409, "bad_state", f"Cannot maker-sign a {comm.status.value} communication.")
    persona = _persona(db, x_demo_persona)
    if (
        persona is None
        or persona.entity_id != comm.entity_id
        or persona.role not in (KeyRole.maker, KeyRole.entity)
        or persona.status != KeyStatus.active
    ):
        return _bad(403, "bad_persona", "Signing requires an active maker (or entity) key of this entity.")

    checker_key = None
    if comm.impact == CommImpact.market_moving:
        checker_key = _active_checker(db, comm.entity_id)
        if checker_key is None:
            return _bad(409, "no_checker", "market_moving needs an active checker key; none exists.")

    env = build_envelope(
        artifact_sha256=comm.artifact.sha256,
        entity_id=str(comm.entity_id),
        sebi_reg_no=comm.entity.sebi_reg_no,
        communication_id=str(comm.id),
        channel=comm.channel.value,
        impact=comm.impact.value,
        issued_at=datetime.now(UTC),
        maker_key_id=str(persona.id),
        checker_key_id=str(checker_key.id) if checker_key else None,
    )
    env.maker.sig = sign_bytes(persona.private_key_ed25519, signing_bytes(env))
    comm.maker_key_id = persona.id
    comm.maker_sig = env.maker.sig
    comm.checker_key_id = checker_key.id if checker_key else None
    comm.status = CommStatus.maker_signed
    comm.artifact.envelope = env.to_wire()
    db.commit()
    return ok(_comm_out(comm))


@router.post("/issuer/communications/{comm_id}/cosign")
def cosign_and_publish(
    comm_id: uuid.UUID,
    x_demo_persona: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Checker co-sign (required for market_moving) → publish: finalize
    envelope, optional C2PA embed, append log entry."""
    comm = db.get(Communication, comm_id)
    if comm is None:
        return _bad(404, "not_found", "No such communication.")
    if comm.status != CommStatus.maker_signed:
        return _bad(409, "bad_state", f"Cannot publish a {comm.status.value} communication.")

    env = Envelope.model_validate(comm.artifact.envelope)

    if comm.impact == CommImpact.market_moving:
        persona = _persona(db, x_demo_persona)
        if (
            persona is None
            or persona.entity_id != comm.entity_id
            or persona.role != KeyRole.checker
            or persona.status != KeyStatus.active
        ):
            return _bad(403, "bad_persona", "Co-signing requires this entity's active checker key.")
        if str(persona.id) != (env.checker.key_id if env.checker else None):
            return _bad(409, "checker_mismatch", "Envelope names a different checker key.")
        env.checker.sig = sign_bytes(persona.private_key_ed25519, signing_bytes(env))
        comm.checker_sig = env.checker.sig

    now = datetime.now(UTC)
    material = ensure_trust_material(get_settings().trust_dir)

    old_leaves = merkle.load_leaves(db)
    old_root = merkle.root_hash(old_leaves).hex()

    comm.artifact.envelope = env.to_wire()
    if c2pa_embed.HAS_C2PA:
        maker_key = db.get(Key, comm.maker_key_id)
        if maker_key and maker_key.cert_pem:
            comm.artifact.c2pa_embedded = c2pa_embed.embed(
                Path(comm.artifact.storage_path), comm.entity.name, maker_key.cert_pem, ""
            )

    entry_row = merkle.append_entry(
        db,
        {
            "kind": "publish",
            "communication_id": str(comm.id),
            "artifact_sha256": comm.artifact.sha256,
            "entity_id": str(comm.entity_id),
            "published_at": now.isoformat(),
            "envelope_digest": envelope_digest(env),
        },
        material.registry_sth.private_key_b64,
    )
    comm.status = CommStatus.published
    comm.published_at = now
    db.flush()
    comm.log_seq = entry_row.seq
    db.commit()
    try:
        get_redis().delete(merkle.LATEST_ROOT_CACHE_KEY)
    except Exception:
        pass  # cache invalidation is best-effort; reads recompute anyway

    return ok(
        {
            **_comm_out(comm).model_dump(mode="json"),
            "log_seq": entry_row.seq,
            "old_root": old_root,
            "new_root": entry_row.root_hash,
        }
    )


@router.post("/issuer/communications/{comm_id}/revoke")
def revoke_communication(
    comm_id: uuid.UUID,
    x_demo_persona: str | None = Header(None),
    db: Session = Depends(get_db),
):
    comm = db.get(Communication, comm_id)
    if comm is None:
        return _bad(404, "not_found", "No such communication.")
    if comm.status != CommStatus.published:
        return _bad(409, "bad_state", "Only published communications can be withdrawn.")
    persona = _persona(db, x_demo_persona)
    if persona is None or persona.entity_id != comm.entity_id:
        return _bad(403, "bad_persona", "Withdrawal requires a key of this entity.")
    material = ensure_trust_material(get_settings().trust_dir)
    entry = revocation.revoke_communication(db, comm, material.registry_sth.private_key_b64)
    db.commit()
    try:
        get_redis().delete(merkle.LATEST_ROOT_CACHE_KEY)
    except Exception:
        pass
    return ok({**_comm_out(comm).model_dump(mode="json"), "revocation_log_seq": entry.seq})


class RevokeKeyIn(BaseModel):
    reason: str


@router.post("/admin/keys/{key_id}/revoke")
def admin_revoke_key(key_id: uuid.UUID, body: RevokeKeyIn, db: Session = Depends(get_db)):
    key = db.get(Key, key_id)
    if key is None:
        return _bad(404, "not_found", "No such key.")
    if key.status == KeyStatus.revoked:
        return _bad(409, "bad_state", "Key is already revoked.")
    material = ensure_trust_material(get_settings().trust_dir)
    entry = revocation.revoke_key(db, key, body.reason, material.registry_sth.private_key_b64)
    db.commit()
    try:
        get_redis().delete(merkle.LATEST_ROOT_CACHE_KEY)
    except Exception:
        pass
    return ok(
        {
            "key_id": str(key.id),
            "status": key.status.value,
            "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
            "revocation_log_seq": entry.seq,
        }
    )
