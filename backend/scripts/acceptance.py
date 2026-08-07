"""Acceptance suite: does the system give the RIGHT answer, case by case?

Different question from scripts/evaluate.py. That one measures matching
precision/recall over many transforms. This one asserts the *verdict* a
human would expect for a named, realistic scenario — including the awkward
ones (a genuine notice from an issuer we don't know, a real contact email
that must not read as a payment demand, a message that names a real company
but matches nothing).

Runs against the live API so it exercises the same path the UI does:

    python -m scripts.acceptance                 # against localhost:8000
    python -m scripts.acceptance --url http://…  # somewhere else

Exits non-zero if any case gives the wrong answer.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED = REPO_ROOT / "fixtures" / "generated"


@dataclass
class Case:
    name: str
    expect: str                      # expected verdict
    why: str                         # what the case is actually testing
    text: str | None = None
    file: Path | None = None
    transform: str | None = None     # applied to file bytes before sending
    claimed_sender: str | None = None
    expect_reasons: list[str] = field(default_factory=list)   # must all appear
    forbid_reasons: list[str] = field(default_factory=list)   # must not appear


# --- transforms a forward really performs -------------------------------

def jpeg(data: bytes, q: int) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=q)
        return buf.getvalue()


def resize(data: bytes, factor: float) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        out = im.resize((max(1, int(im.width * factor)), max(1, int(im.height * factor))), Image.LANCZOS)
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=85)
        return buf.getvalue()


def crop(data: bytes, pct: float) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        w, h = im.size
        dx, dy = int(w * pct), int(h * pct)
        buf = io.BytesIO()
        im.crop((dx, dy, w - dx, h - dy)).save(buf, "JPEG", quality=80)
        return buf.getvalue()


def repaint(data: bytes) -> bytes:
    """A heavily edited copy — should NOT pass as the original."""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB").rotate(8, expand=True, fillcolor=(255, 255, 255))
        w, h = im.size
        im = im.crop((int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=60)
        return buf.getvalue()


TRANSFORMS = {
    "none": lambda d: d,
    "jpeg50": lambda d: jpeg(d, 50),
    "jpeg30": lambda d: jpeg(d, 30),
    "resize50": lambda d: resize(d, 0.5),
    "crop": lambda d: crop(d, 0.025),
    "repaint": repaint,
}

# --- the demo world's published wording (mirrors seed.py PUBLISH_PLAN) ---
SMS_MERIDIAN = ("MERIDN: Margin shortfall in your account. Add funds by T+1 via the official app. "
                "Never share OTPs. — Meridian Broking Ltd, SEBI reg DEMO-INZ-000123")
SMS_NDX = ("NDXIN: Settlement holiday on 17 Jul 2026. Pay-in/pay-out shifts to next working day. "
           "— National Demo Exchange")

NOTICE = GENERATED / "notice_meridian_margin.jpg"
NOTICE2 = GENERATED / "notice_suvarna_nav.jpg"


def build_cases() -> list[Case]:
    return [
        # ---- genuine content must verify, through realistic mangling ----
        Case("image: untouched published notice", "VERIFIED",
             "byte-identical to what the issuer published",
             file=NOTICE, transform="none", expect_reasons=["HASH_EXACT_MATCH"]),
        Case("image: re-saved at JPEG q50 (WhatsApp forward)", "VERIFIED",
             "every byte changes, the picture does not",
             file=NOTICE, transform="jpeg50", expect_reasons=["PHASH_MATCH"]),
        Case("image: re-saved hard at JPEG q30", "VERIFIED",
             "heavier compression still preserves the picture",
             file=NOTICE, transform="jpeg30", expect_reasons=["PHASH_MATCH"]),
        Case("image: halved in size", "VERIFIED",
             "resizing is the other thing chat apps do",
             file=NOTICE, transform="resize50", expect_reasons=["PHASH_MATCH"]),
        Case("image: screenshot-style 2.5% crop", "VERIFIED",
             "a screenshot of a forward loses the edges",
             file=NOTICE, transform="crop", expect_reasons=["PHASH_MATCH"]),
        Case("image: second published notice, forwarded", "VERIFIED",
             "matching is not keyed to one lucky fixture",
             file=NOTICE2, transform="jpeg50", expect_reasons=["PHASH_MATCH"]),
        Case("text: exact published SMS", "VERIFIED",
             "the message as the issuer sent it",
             text=SMS_MERIDIAN, expect_reasons=["HASH_EXACT_MATCH"]),
        Case("text: published SMS + emoji and double spaces", "VERIFIED",
             "forwarding injects noise that must not break the match",
             text="MERIDN: Margin shortfall  in your account. 😊 Add funds by T+1  via the official "
                  "app. Never share OTPs. — Meridian Broking Ltd, SEBI reg DEMO-INZ-000123",
             expect_reasons=["SIMHASH_MATCH"]),
        Case("text: a different published SMS", "VERIFIED",
             "not keyed to one message either",
             text=SMS_NDX),

        # ---- official documents ----
        Case("document: published filing, untouched", "VERIFIED",
             "the filing exactly as submitted",
             file=GENERATED / "filing_kumaon_q1.pdf", transform="none",
             expect_reasons=["HASH_EXACT_MATCH"]),
        Case("document: second published filing", "VERIFIED",
             "not keyed to one document",
             file=GENERATED / "filing_nivara_annual.pdf", transform="none"),
        Case("document: filing with the revenue figure altered", "LIKELY_FAKE",
             "DEMO.md step 4. Wording matches a real filing but the figures do not — that is "
             "positive evidence of tampering, not merely an absent match, so it escalates. "
             "This case failed as VERIFIED before the numeric guard existed.",
             file=GENERATED / "filing_kumaon_q1_TAMPERED.pdf", transform="none",
             claimed_sender="Kumaon Metals Ltd",
             expect_reasons=["TAMPERED_CONTENT"],
             forbid_reasons=["HASH_EXACT_MATCH", "SIMHASH_MATCH"]),

        # ---- altered content must NOT verify ----
        Case("text: published SMS with the deadline changed", "OFFICIAL_CLAIM_UNVERIFIED",
             "one altered word is the classic scam edit — must not pass",
             text=SMS_MERIDIAN.replace("T+1", "T+9"),
             forbid_reasons=["HASH_EXACT_MATCH", "SIMHASH_MATCH"]),
        Case("text: published SMS with a payment line spliced in", "LIKELY_FAKE",
             "real notice plus a demand for money",
             text=SMS_MERIDIAN + " Pay the shortfall now via UPI meridian.recovery@okpay",
             expect_reasons=["PAYMENT_ASK"]),
        Case("image: heavily edited copy of a real notice", "INFORMATIONAL",
             "rotated, cropped hard and recompressed — beyond recognition, so no false VERIFIED",
             file=NOTICE, transform="repaint",
             forbid_reasons=["HASH_EXACT_MATCH", "PHASH_MATCH", "PDQ_MATCH"]),

        # ---- outright scams ----
        Case("scam: lookalike domain + payment demand", "LIKELY_FAKE",
             "the headline demo scam",
             text="MERIDN IPO allotment confirmed! Pay allotment fee now to "
                  "http://rneridianbroking-refunds.top/claim. Last 2 hours only. "
                  "Pay via UPI meridianrefund@okpay",
             expect_reasons=["LOOKALIKE_DOMAIN", "BLACKLIST_MATCH"]),
        Case("scam: homoglyph company name", "LIKELY_FAKE",
             "Cyrillic letters imitating a registered name",
             text="Notice from Mеridiаn Broking Ltd: verify your account at "
                  "http://meridian-verify.xyz to avoid suspension.",
             expect_reasons=["HOMOGLYPH_ENTITY"]),
        Case("scam: guaranteed returns + urgency", "LIKELY_FAKE",
             "blacklisted phrase plus pressure",
             text="Join our group for guaranteed 3% daily returns. Limited slots. "
                  "Pay via UPI quickprofit@okaxis today only.",
             expect_reasons=["BLACKLIST_MATCH"]),
        Case("scam: phishing AGM notice", "LIKELY_FAKE",
             "official-shaped message carrying a hostile link",
             text="Dear Shareholder, 18th AGM of Kumaon Metals Ltd is today. Login at "
                  "http://kumaon-agm-verify.top/claim to receive your dividend before it expires today.",
             expect_reasons=["URL_RISK"]),

        # ---- claims we cannot confirm (must NOT be called fake) ----
        Case("genuine notice from an UNREGISTERED issuer", "OFFICIAL_CLAIM_UNVERIFIED",
             "the real-world AGM case: correct answer is 'cannot confirm', never 'fake'",
             text="Dear Shareholder, 18th AGM of Northwind Housing Finance Ltd is scheduled today "
                  "at 3:45 PM (IST) through virtual mode. Please login to "
                  "https://emeetings.northwind-registrar.example/ to participate in the meeting.",
             forbid_reasons=["BLACKLIST_MATCH", "LOOKALIKE_DOMAIN"]),
        Case("claims a registered company, matches nothing", "OFFICIAL_CLAIM_UNVERIFIED",
             "names a real demo issuer but is not anything they published",
             text="Important circular from Kumaon Metals Ltd regarding a revised allotment schedule."),
        Case("corporate mail carrying a contact address", "OFFICIAL_CLAIM_UNVERIFIED",
             "an email address is not a UPI handle and must not read as a payment demand",
             text="Dear Shareholder, for queries about the postal ballot please write to "
                  "investor.relations@northwind.example or call the registrar.",
             forbid_reasons=["PAYMENT_ASK"]),

        # ---- benign ----
        Case("plain market news", "INFORMATIONAL",
             "the base rate: most forwards claim nothing",
             text="Benchmark indices ended higher today led by banking and IT stocks."),
        Case("news mentioning dividends", "INFORMATIONAL",
             "must not be dragged into 'official claim' by the corporate-action markers",
             text="Several companies announced dividends this quarter, analysts said."),
        Case("unrelated photo", "INFORMATIONAL",
             "an image that matches nothing is not an accusation",
             file=GENERATED / "unrelated.jpg", transform="none",
             forbid_reasons=["PHASH_MATCH", "HASH_EXACT_MATCH"]),
    ]


def _unrelated_photo() -> Path:
    """A synthetic photo that matches nothing in the registry."""
    p = GENERATED / "unrelated.jpg"
    if not p.exists():
        import random
        rng = random.Random(20260806)
        im = Image.new("RGB", (900, 600))
        d = im.load()
        for y in range(600):
            for x in range(900):
                d[x, y] = ((x * 7 + y * 3) % 256, (y * 5) % 256, rng.randrange(256))
        im.save(p, "JPEG", quality=88)
    return p


def run(base_url: str) -> int:
    _unrelated_photo()
    cases = build_cases()
    client = httpx.Client(base_url=base_url, timeout=120.0)

    passed = failed = 0
    failures: list[str] = []
    print(f"\nAcceptance suite — {len(cases)} cases against {base_url}\n" + "=" * 78)

    for case in cases:
        files = data = None
        if case.file is not None:
            if not case.file.exists():
                print(f"  SKIP  {case.name}: missing {case.file.name}")
                continue
            raw = case.file.read_bytes()
            is_pdf = case.file.suffix.lower() == ".pdf"
            payload = raw if is_pdf else TRANSFORMS[case.transform or "none"](raw)
            mime = "application/pdf" if is_pdf else "image/jpeg"
            files = {"file": (case.file.name, payload, mime)}
            data = {}
        else:
            data = {"text": case.text}
        if case.claimed_sender:
            data["claimed_sender_text"] = case.claimed_sender

        # /api/verify is rate limited at 30/min/IP for external traffic. A full
        # run plus a rerun trips it, so back off and retry rather than report
        # a limiter hit as a wrong answer.
        for attempt in range(6):
            r = client.post("/api/verify", data=data, files=files)
            if r.status_code != 429:
                break
            time.sleep(float(r.headers.get("Retry-After", 2)) + 1.0)
        body = r.json()
        if not body.get("ok"):
            failed += 1
            failures.append(f"{case.name}: API error {body.get('error')}")
            print(f"  FAIL  {case.name}\n        API error: {body.get('error')}")
            continue

        d = body["data"]
        got, reasons = d["verdict"], d["reasons"]
        problems = []
        if got != case.expect:
            problems.append(f"expected {case.expect}, got {got}")
        for code in case.expect_reasons:
            if code not in reasons:
                problems.append(f"missing reason {code}")
        for code in case.forbid_reasons:
            if code in reasons:
                problems.append(f"forbidden reason {code} present")

        if problems:
            failed += 1
            failures.append(f"{case.name}: " + "; ".join(problems))
            print(f"  FAIL  {case.name}")
            print(f"        {case.why}")
            for p in problems:
                print(f"        -> {p}")
            print(f"        reasons: {reasons}")
        else:
            passed += 1
            rule = (d.get("why") or {}).get("rule", "-")
            print(f"  ok    {case.name}")
            print(f"        {got}  ({rule})")

    print("=" * 78)
    print(f"{passed} passed, {failed} failed, {len(cases)} total")
    if failures:
        print("\nWrong answers:")
        for f in failures:
            print(f"  - {f}")
    return 1 if failed else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()
    sys.exit(run(args.url))


if __name__ == "__main__":
    main()
