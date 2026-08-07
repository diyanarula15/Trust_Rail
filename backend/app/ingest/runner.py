"""Wiring: which feeds exist, and what happens when they are polled.

Feeds are declared here and configured by environment. Out of the box they
point at the sample files in fixtures/feeds/ so the path is demonstrable
with no external dependency; set EXCHANGE_FEED_URL / DLT_SMS_FEED_URL and
the same code polls a real endpoint instead.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ingest.adapters import ADAPTERS
from app.ingest.publisher import PublishOutcome, publish_item
from app.ingest.sources import FeedItem, HttpJsonSource, JsonFileSource

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
FEED_DIR = REPO_ROOT / "fixtures" / "feeds"


class FeedRun(BaseModel):
    source: str
    adapter: str
    origin: str                 # file path or URL actually polled
    fetched: int = 0
    published: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: int = 0
    outcomes: list[PublishOutcome] = []
    ran_at: datetime


class IngestReport(BaseModel):
    runs: list[FeedRun] = []

    @property
    def published(self) -> int:
        return sum(r.published for r in self.runs)


def configured_feeds() -> list[tuple[str, str, object]]:
    """(source name, adapter name, source object).

    Environment overrides the sample files, which is the entire difference
    between the demo and a live deployment.
    """
    exchange_url = os.environ.get("EXCHANGE_FEED_URL", "").strip()
    dlt_url = os.environ.get("DLT_SMS_FEED_URL", "").strip()

    exchange = (
        HttpJsonSource("exchange_filings", exchange_url)
        if exchange_url
        else JsonFileSource("exchange_filings", FEED_DIR / "exchange_filings.json")
    )
    dlt = (
        HttpJsonSource("dlt_sms", dlt_url)
        if dlt_url
        else JsonFileSource("dlt_sms", FEED_DIR / "dlt_sms.json")
    )
    return [
        ("exchange_filings", "exchange_filings", exchange),
        ("dlt_sms", "dlt_sms", dlt),
    ]


def run_once(db: Session) -> IngestReport:
    report = IngestReport()
    for source_name, adapter_name, source in configured_feeds():
        adapt = ADAPTERS[adapter_name]
        origin = getattr(source, "url", None) or str(getattr(source, "path", "—"))
        run = FeedRun(source=source_name, adapter=adapter_name, origin=origin,
                      ran_at=datetime.now(UTC))
        try:
            raw_items = source.fetch()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("ingest: %s fetch failed: %s", source_name, exc)
            run.errors += 1
            report.runs.append(run)
            continue

        run.fetched = len(raw_items)
        for raw in raw_items:
            item: FeedItem | None = adapt(raw)
            if item is None:
                run.skipped += 1
                continue
            try:
                outcome = publish_item(db, item, source_name, REPO_ROOT)
            except Exception as exc:  # one bad row must not stop the feed
                db.rollback()
                logger.exception("ingest: %s item %s failed", source_name, raw)
                outcome = PublishOutcome(
                    external_id=str(raw.get("id", "?")), status="error", detail=str(exc)[:200]
                )
            run.outcomes.append(outcome)
            if outcome.status == "published":
                run.published += 1
            elif outcome.status == "duplicate":
                run.duplicates += 1
            elif outcome.status == "error":
                run.errors += 1
            else:
                run.skipped += 1
        report.runs.append(run)
    return report
