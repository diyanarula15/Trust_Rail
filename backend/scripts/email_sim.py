"""Local email simulator — no mailbox, no network calls. Reads a real .eml
file and drives it through `channels/email_channel.handle_raw_message` — the
same function the real IMAP poller (`scripts/email_poll.py`) would call. The
verification pipeline (including the real DKIM/domain-lookalike checks in
pipeline/emailcheck.py) runs for real against the real seeded registry; only
the mailbox transport (fetching the message, sending the SMTP reply) is
faked.

Usage:
    python -m scripts.email_sim
    python -m scripts.email_sim --file ../../fixtures/eml_samples/lookalike_scam.eml
"""
import argparse
from pathlib import Path

from app.channels import email_channel
from app.config import REPO_ROOT
from app.db import SessionLocal

_DEFAULT_FIXTURES = [
    REPO_ROOT / "fixtures/eml_samples/forwarded_legit.eml",
    REPO_ROOT / "fixtures/eml_samples/lookalike_scam.eml",
]


def _run_one(path: Path) -> None:
    print(f"\n{'=' * 72}\n{path.name}\n{'=' * 72}")
    raw = path.read_bytes()
    with SessionLocal() as db:
        result = email_channel.handle_raw_message(raw, db)
    if result is None:
        print("(skipped: auto-generated / self-sent / bounce)")
        return
    print(f"To: {result['To']}")
    print(f"Subject: {result['Subject']}")
    print()
    print(result.get_content())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Path to a .eml file (default: cycle both fixture samples)")
    args = parser.parse_args()

    if email_channel.is_live():
        print("EMAIL_IMAP_HOST/EMAIL_USERNAME are set — this would send for real over SMTP. "
              "Unset them (or use scripts.email_poll) to go live.")

    paths = [Path(args.file)] if args.file else _DEFAULT_FIXTURES
    for path in paths:
        _run_one(path)


if __name__ == "__main__":
    main()
