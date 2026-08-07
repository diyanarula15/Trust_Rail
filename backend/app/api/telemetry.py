"""Telemetry aggregates for the supervision dashboard (spec §14).

Historical demo rows (§15.5 — 60 verifications over 14 days) aren't seeded
yet; that lands with Epic 8 when the dashboard becomes the consumer. This
endpoint is correct today against whatever real verifications exist —
empty aggregates, honestly, until then.
"""
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Verdict, Verification
from app.schemas import ok

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

_WINDOW_RE = re.compile(r"^(\d+)d$")
_FLAGGED_VERDICTS = {Verdict.LIKELY_FAKE.value, Verdict.OFFICIAL_CLAIM_UNVERIFIED.value}


def _parse_window_days(window: str) -> int:
    m = _WINDOW_RE.match(window)
    return int(m.group(1)) if m else 14


@router.get("/recent")
def telemetry_recent(limit: int = 12, db: Session = Depends(get_db)) -> dict:
    """The last few checks, for the dashboard's live feed.

    Aggregate-shaped on purpose: verdict, input kind, campaign and timing
    only. What a user actually submitted is never persisted by /api/verify
    and must not appear here either.
    """
    rows = (
        db.execute(
            select(Verification).order_by(Verification.created_at.desc()).limit(min(limit, 50))
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": str(v.id),
                "verdict": v.verdict.value,
                "input_kind": v.input_kind.value,
                "channel": v.channel.value,
                "campaign": v.campaign,
                "state_code": v.state_code,
                "latency_ms": v.latency_ms,
                "created_at": v.created_at.isoformat(),
            }
            for v in rows
        ]
    )


@router.get("/summary")
def telemetry_summary(window: str = "14d", db: Session = Depends(get_db)) -> dict:
    since = datetime.now(UTC) - timedelta(days=_parse_window_days(window))
    rows = db.execute(select(Verification).where(Verification.created_at >= since)).scalars().all()

    totals_by_verdict: Counter[str] = Counter()
    daily: defaultdict[str, Counter[str]] = defaultdict(Counter)
    by_state: Counter[str] = Counter()
    claimed_counts: Counter[str] = Counter()
    campaigns: dict[str, dict] = {}

    for v in rows:
        verdict_val = v.verdict.value
        totals_by_verdict[verdict_val] += 1
        daily[v.created_at.date().isoformat()][verdict_val] += 1
        if v.state_code and verdict_val in _FLAGGED_VERDICTS:
            by_state[v.state_code] += 1
        if v.claimed_entity_text:
            claimed_counts[v.claimed_entity_text] += 1
        if v.campaign:
            c = campaigns.setdefault(
                v.campaign,
                {"campaign": v.campaign, "count": 0, "last_seen": v.created_at, "channels": set()},
            )
            c["count"] += 1
            c["last_seen"] = max(c["last_seen"], v.created_at)
            c["channels"].add(v.channel.value)

    series_daily = [{"date": day, **counts} for day, counts in sorted(daily.items())]
    by_state_out = [{"state_code": s, "count_flagged": n} for s, n in by_state.most_common()]
    top_impersonated = [{"entity": e, "count": n} for e, n in claimed_counts.most_common(10)]
    campaigns_out = [
        {
            "campaign": c["campaign"],
            "count": c["count"],
            "last_seen": c["last_seen"].isoformat(),
            "channels": sorted(c["channels"]),
        }
        for c in sorted(campaigns.values(), key=lambda x: x["count"], reverse=True)
    ]

    return ok(
        {
            "totals_by_verdict": dict(totals_by_verdict),
            "series_daily": series_daily,
            "by_state": by_state_out,
            "top_impersonated": top_impersonated,
            "campaigns": campaigns_out,
        }
    )
