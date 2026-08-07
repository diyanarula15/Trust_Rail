"""Poll the configured feeds and publish anything new.

    python -m scripts.ingest_feeds            # one pass
    python -m scripts.ingest_feeds --watch    # keep polling
    python -m scripts.ingest_feeds --interval 60 --watch

Points at fixtures/feeds/*.json unless EXCHANGE_FEED_URL / DLT_SMS_FEED_URL
are set, in which case it polls those instead. Re-running is safe: identical
content is recognised and skipped rather than republished.
"""
from __future__ import annotations

import argparse
import time

from app.db import SessionLocal
from app.ingest.runner import run_once

STATUS_MARK = {
    "published": "+",
    "duplicate": "=",
    "no_entity": "?",
    "no_key": "!",
    "error": "x",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="keep polling")
    ap.add_argument("--interval", type=int, default=30, help="seconds between polls")
    ap.add_argument("--quiet", action="store_true", help="totals only")
    args = ap.parse_args()

    while True:
        with SessionLocal() as db:
            report = run_once(db)

        for run in report.runs:
            print(f"\n{run.source}  <-  {run.origin}")
            print(f"  fetched {run.fetched}  published {run.published}  "
                  f"duplicate {run.duplicates}  skipped {run.skipped}  errors {run.errors}")
            if not args.quiet:
                for o in run.outcomes:
                    mark = STATUS_MARK.get(o.status, " ")
                    seq = f"  log #{o.log_seq}" if o.log_seq is not None else ""
                    print(f"    {mark} {o.external_id:<26} {o.status:<10} {o.detail[:60]}{seq}")

        total = report.published
        print(f"\npublished {total} new communication(s)")
        if not args.watch:
            return
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
