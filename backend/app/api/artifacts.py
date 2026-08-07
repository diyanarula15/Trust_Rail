"""Artifact previews for the match-evidence panel.

Serves the *registered* side of a side-by-side comparison. Deliberately
narrow: published (or withdrawn) communications only, images only, looked
up by content hash. Draft and maker-signed artifacts are not public yet and
must not leak out through here — that check is the whole point of the
endpoint existing rather than serving `var/artifacts/` statically.

The submitted side is never served from here: `/api/verify` doesn't persist
what a user forwards, and the browser already holds the file it just
uploaded.
"""
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Artifact, CommStatus, Communication
from app.schemas import err, ok

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

_PREVIEWABLE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_PUBLIC_STATUSES = (CommStatus.published, CommStatus.revoked)


def _not_found() -> JSONResponse:
    # One shape for "no such artifact", "not public yet" and "not an image":
    # a caller poking at hashes shouldn't be able to tell drafts apart from
    # things that don't exist.
    return JSONResponse(status_code=404, content=err("not_found", "No preview for that artifact."))


@router.get("/samples")
def list_sample_artifacts(limit: int = 3, db: Session = Depends(get_db)) -> dict:
    """Published images the UI can offer as one-click examples.

    Returned by content hash rather than hardcoded in the frontend so the
    samples always track whatever the current seed actually published — a
    pinned hash would silently 404 after every reseed.
    """
    rows = db.execute(
        select(Communication, Artifact)
        .join(Artifact, Communication.artifact_id == Artifact.id)
        .where(
            Communication.status == CommStatus.published,
            Artifact.mime.in_(_PREVIEWABLE_MIMES),
        )
        .order_by(Communication.published_at)
        .limit(min(limit, 10))
    ).all()
    return ok(
        [
            {
                "sha256": artifact.sha256,
                "title": comm.title,
                "channel": comm.channel.value,
            }
            for comm, artifact in rows
        ]
    )


@router.get("/{sha256}/preview")
def get_artifact_preview(sha256: str, db: Session = Depends(get_db)):
    artifact = db.execute(
        select(Artifact).where(Artifact.sha256 == sha256)
    ).scalars().first()
    if artifact is None or artifact.mime not in _PREVIEWABLE_MIMES:
        return _not_found()

    published = db.execute(
        select(Communication.id).where(
            Communication.artifact_id == artifact.id,
            Communication.status.in_(_PUBLIC_STATUSES),
        )
    ).scalars().first()
    if published is None:
        return _not_found()

    # storage_path is written by the issuer flow, not by a caller, but resolve
    # it against ARTIFACT_DIR anyway so a bad row can't reach outside it.
    path = Path(artifact.storage_path).resolve()
    artifact_dir = get_settings().artifact_dir.resolve()
    if not path.is_file() or not path.is_relative_to(artifact_dir):
        return _not_found()

    return FileResponse(path, media_type=artifact.mime, headers={"Cache-Control": "private, max-age=300"})
