"""Ingestion status and manual trigger.

Read-only status is what the dashboard uses to show that intake is a real
path rather than a diagram. The trigger exists so the flow can be
demonstrated live without dropping to a terminal.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingest.runner import configured_feeds, run_once
from app.models import CommStatus, Communication, LogEntry
from app.schemas import ok

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.get("/status")
def ingest_status(db: Session = Depends(get_db)) -> dict:
    """Which feeds are wired up, and how much of the record came from them.

    Counts come from the transparency log rather than a side table: every
    ingested publish records its `source` in the log entry, so this is
    derived from the same tamper-evident record everything else is.
    """
    entries = db.execute(select(LogEntry.entry)).scalars().all()
    by_source: dict[str, int] = {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("kind") == "publish":
            by_source[entry.get("source") or "issuer_console"] = (
                by_source.get(entry.get("source") or "issuer_console", 0) + 1
            )

    total_published = db.execute(
        select(func.count(Communication.id)).where(Communication.status == CommStatus.published)
    ).scalar() or 0

    feeds = [
        {
            "name": name,
            "adapter": adapter,
            "origin": getattr(source, "url", None) or str(getattr(source, "path", "N/A")),
            "live": hasattr(source, "url"),
            "ingested": by_source.get(name, 0),
        }
        for name, adapter, source in configured_feeds()
    ]

    return ok(
        {
            "feeds": feeds,
            "by_source": by_source,
            "total_published": total_published,
            "ingested_total": sum(f["ingested"] for f in feeds),
        }
    )


@router.post("/run")
def ingest_run(db: Session = Depends(get_db)) -> dict:
    """Poll every configured feed once. Safe to call repeatedly — identical
    content is recognised and skipped."""
    report = run_once(db)
    return ok(
        {
            "published": report.published,
            "runs": [
                {
                    "source": r.source,
                    "origin": r.origin,
                    "fetched": r.fetched,
                    "published": r.published,
                    "duplicates": r.duplicates,
                    "skipped": r.skipped,
                    "errors": r.errors,
                }
                for r in report.runs
            ],
        }
    )
