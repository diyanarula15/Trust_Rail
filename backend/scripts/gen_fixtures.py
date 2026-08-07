"""Generate synthetic official documents and notice images for the demo world.

Why generated rather than sourced: the earlier `assets_input/` filings were
real BSE/NSE submissions from real listed companies, which contradicted
README/ARCHITECTURE's "no real companies, tickers, or persons anywhere" and
meant DEMO.md step 4 instructed doctoring a real issuer's published
financials. Everything here is invented, matches the fictional entities in
scripts/seed.py, and is safe to tamper with on stage.

The structure of a board-meeting outcome letter is public form, not
proprietary content — what makes the originals unusable is the real company
names, scrip codes, CINs and figures, none of which appear here.

Outputs land in fixtures/generated/ (committed, unlike assets_input/), so a
clone can run the acceptance suite without owner-supplied media.

    python -m scripts.gen_fixtures
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "fixtures" / "generated"

# Fictional issuers — these mirror scripts/seed.py's ENTITIES exactly.
FILINGS = [
    {
        "slug": "filing_kumaon_q1",
        "entity": "Kumaon Metals Ltd",
        "reg": "DEMO-INE-000451",
        "scrip": "DEMO-500101",
        "domain": "kumaonmetals.example",
        "date": "12 July 2026",
        "subject": "Outcome of Board Meeting — Unaudited Financial Results for the quarter ended 30 June 2026",
        # The tamper target for DEMO.md step 4. Invented figure, invented company.
        "rows": [
            ("Revenue from operations", "9,588.18"),
            ("Other income", "212.44"),
            ("Total income", "9,800.62"),
            ("Total expenses", "8,914.07"),
            ("Profit before tax", "886.55"),
            ("Profit after tax", "662.91"),
        ],
    },
    {
        "slug": "filing_kumaon_capex",
        "entity": "Kumaon Metals Ltd",
        "reg": "DEMO-INE-000451",
        "scrip": "DEMO-500101",
        "domain": "kumaonmetals.example",
        "date": "14 July 2026",
        "subject": "Outcome of Board Meeting — Approval of capacity expansion at the Haldwani unit",
        "rows": [
            ("Approved capital outlay", "4,250.00"),
            ("Funded through internal accruals", "2,900.00"),
            ("Funded through debt", "1,350.00"),
            ("Expected commissioning", "Q4 FY27"),
        ],
    },
    {
        "slug": "filing_nivara_annual",
        "entity": "Nivara Housing Finance",
        "reg": "DEMO-INE-000453",
        "scrip": "DEMO-500310",
        "domain": "nivarahf.example",
        "date": "09 July 2026",
        "subject": "Annual disclosure under Regulation 30 — related party transactions",
        "rows": [
            ("Loans to related parties", "0.00"),
            ("Guarantees issued", "0.00"),
            ("Related party revenue", "118.90"),
            ("Auditor qualification", "None"),
        ],
    },
]

# Notice images. `layout` matters more than colour here: a phash is computed
# on the grayscale DCT, so three cards with the same coarse structure land
# within a few bits of each other no matter how differently they are tinted.
# The first attempt did exactly that (worst pair 12 bits, inside the 16-bit
# near band). These three deliberately differ in *luminance composition* —
# dark-with-left-panel, light-on-cream, and dark-with-centre-band.
NOTICES = [
    {
        "slug": "notice_meridian_margin",
        "layout": "left_panel",
        "entity": "Meridian Broking Ltd",
        "reg": "DEMO-INZ-000123",
        "title": "Revised margin rules",
        "lines": [
            "Upfront margin applies from 20 July 2026.",
            "Peak margin reporting moves to four snapshots a day.",
            "Shortfall penalties are levied at T+1.",
            "We never ask for OTPs, passwords or UPI transfers.",
        ],
        "bg": (18, 42, 74),
        "accent": (214, 178, 74),
    },
    {
        "slug": "notice_suvarna_nav",
        "layout": "light",
        "entity": "Suvarna Mutual Fund",
        "reg": "DEMO-MF-000021",
        "title": "Scheme performance summary",
        "lines": [
            "Suvarna Bluechip Fund NAV as on 10 July 2026: 84.31.",
            "Suvarna Short Duration Fund NAV: 27.06.",
            "Past performance does not indicate future returns.",
            "Statements are available only at suvarnamf.example.",
        ],
        "bg": (246, 243, 234),
        "accent": (28, 74, 58),
    },
    {
        "slug": "notice_ndx_calendar",
        "layout": "centre_band",
        "entity": "National Demo Exchange (NDX)",
        "reg": "DEMO-EXC-000010",
        "title": "Trading calendar notice",
        "lines": [
            "Settlement holiday on 17 July 2026.",
            "Pay-in and pay-out shift to the next working day.",
            "Normal trading resumes 18 July 2026.",
            "Circulars are published only on ndx.example.",
        ],
        "bg": (46, 20, 18),
        "accent": (240, 226, 200),
    },
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (
        f"/System/Library/Fonts/Supplemental/Arial{' Bold' if bold else ''}.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_filing(spec: dict) -> Path:
    """A board-meeting outcome letter with genuinely extractable text —
    the PDF path fingerprints extracted text, not file bytes."""
    path = OUT_DIR / f"{spec['slug']}.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 25 * mm

    c.setFont("Helvetica-Bold", 15)
    c.drawString(22 * mm, y, spec["entity"])
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(22 * mm, y, f"SEBI registration {spec['reg']}  ·  Scrip code {spec['scrip']}  ·  {spec['domain']}")
    y -= 4 * mm
    c.line(22 * mm, y, w - 22 * mm, y)

    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(22 * mm, y, f"Date: {spec['date']}")
    y -= 6 * mm
    for line in ("To,", "The Manager — Listing", "National Demo Exchange (NDX) and Bharat Demo Exchange (BDX)"):
        c.drawString(22 * mm, y, line)
        y -= 5 * mm

    y -= 5 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(22 * mm, y, "Subject:")
    c.setFont("Helvetica", 10)
    for chunk in _wrap(spec["subject"], 78):
        c.drawString(40 * mm, y, chunk)
        y -= 5 * mm

    y -= 5 * mm
    c.setFont("Helvetica", 10)
    body = (
        "Dear Sir / Madam, pursuant to Regulation 30 of the Demo Listing Obligations and "
        "Disclosure Requirements, we wish to inform you that the Board of Directors of the "
        "Company, at their meeting held today, have inter alia considered and approved the "
        "matters set out below. The meeting commenced at 11:00 hours and concluded at 13:20 hours."
    )
    for chunk in _wrap(body, 92):
        c.drawString(22 * mm, y, chunk)
        y -= 5 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(22 * mm, y, "Particulars")
    c.drawRightString(w - 22 * mm, y, "Amount (INR lakh)")
    y -= 2 * mm
    c.line(22 * mm, y, w - 22 * mm, y)
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    for label, value in spec["rows"]:
        c.drawString(22 * mm, y, label)
        c.drawRightString(w - 22 * mm, y, value)
        y -= 5.5 * mm

    y -= 8 * mm
    c.setFont("Helvetica", 10)
    for line in (
        "This intimation is also being made available on the Company's website.",
        "You are requested to take the same on record.",
        "",
        "Yours faithfully,",
        f"For {spec['entity']}",
        "Company Secretary and Compliance Officer",
    ):
        c.drawString(22 * mm, y, line)
        y -= 5 * mm

    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(22 * mm, 14 * mm,
                 "FICTIONAL DOCUMENT — generated for the TrustRail prototype. Not a real filing; "
                 "the company, figures and codes do not exist.")
    c.showPage()
    c.save()
    return path


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def build_notice(spec: dict) -> Path:
    """A notice card of the kind an issuer posts to social or WhatsApp.

    Three distinct luminance compositions — see the NOTICES comment for why
    colour alone is not enough to separate perceptual hashes.
    """
    path = OUT_DIR / f"{spec['slug']}.jpg"
    W, H = 1080, 1080
    bg, accent, layout = spec["bg"], spec["accent"], spec["layout"]
    dark_bg = sum(bg) / 3 < 128
    body_fill = (238, 238, 238) if dark_bg else (24, 32, 44)
    head_fill = (255, 255, 255) if dark_bg else (16, 26, 40)

    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    text_x, y_top = 70, 70

    if layout == "left_panel":
        # bright slab down the left third
        d.rectangle([0, 0, 300, H], fill=accent)
        d.rectangle([300, 0, 316, H], fill=(255, 255, 255))
        text_x = 370
    elif layout == "light":
        # inverted luminance: dark type on cream, heavy footer band
        d.rectangle([0, H - 240, W, H], fill=accent)
        d.rectangle([70, 250, 250, 262], fill=accent)
    elif layout == "centre_band":
        # wide light band across the middle, dark above and below
        d.rectangle([0, 380, W, 760], fill=accent)

    d.text((text_x, y_top), spec["entity"], font=_font(44, bold=True), fill=head_fill)
    d.text((text_x, y_top + 56), f"SEBI reg {spec['reg']}",
           font=_font(24), fill=accent if dark_bg else (90, 100, 116))

    title_y = 430 if layout == "centre_band" else 300
    title_fill = (24, 32, 44) if layout == "centre_band" else head_fill
    d.text((text_x, title_y), spec["title"], font=_font(56, bold=True), fill=title_fill)

    y = title_y + 90
    for line in spec["lines"]:
        inside_band = layout == "centre_band" and 380 < y < 700
        for chunk in _wrap(line, 40):
            d.text((text_x, y), chunk, font=_font(30),
                   fill=(24, 32, 44) if inside_band else body_fill)
            y += 44
        y += 14

    footer_fill = (255, 255, 255) if layout == "light" else accent
    d.text((text_x, H - 110), "FICTIONAL — TrustRail prototype notice",
           font=_font(22), fill=footer_fill)

    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    path.write_bytes(buf.getvalue())
    return path


def build_tampered_filing() -> Path:
    """A doctored copy of the Q1 filing with the headline revenue figure
    altered — DEMO.md step 4, and the acceptance suite's document-tamper
    case. Same document in every other respect, which is the point: only the
    wording inside changed, so only a content comparison can catch it."""
    spec = dict(FILINGS[0])
    spec["slug"] = "filing_kumaon_q1_TAMPERED"
    spec["rows"] = [
        ("Revenue from operations", "19,588.18"),  # was 9,588.18
        *FILINGS[0]["rows"][1:],
    ]
    return build_filing(spec)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from app.pipeline.hashing import hamming_hex, phash64_hex

    print(f"writing to {OUT_DIR}")
    for spec in FILINGS:
        p = build_filing(spec)
        print(f"  {p.name:32} {p.stat().st_size:>8,} bytes")
    p = build_tampered_filing()
    print(f"  {p.name:32} {p.stat().st_size:>8,} bytes  (revenue figure altered)")

    hashes: dict[str, str] = {}
    for spec in NOTICES:
        p = build_notice(spec)
        hashes[p.name] = phash64_hex(p.read_bytes())
        print(f"  {p.name:32} {p.stat().st_size:>8,} bytes  phash={hashes[p.name]}")

    # A collision here would silently invalidate every matching test, so check.
    print("\npairwise perceptual distance (must be > 16, the near-match band):")
    names = list(hashes)
    worst = 64
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            dist = hamming_hex(hashes[names[i]], hashes[names[j]])
            worst = min(worst, dist)
            flag = "OK" if dist > 16 else "TOO CLOSE"
            print(f"  {names[i][:26]:28} vs {names[j][:26]:28} {dist:>3}  {flag}")
    print(f"\nworst pairwise distance: {worst} ({'safe' if worst > 16 else 'COLLISION RISK'})")


if __name__ == "__main__":
    main()
