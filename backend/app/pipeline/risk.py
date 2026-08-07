"""Risk signal detectors (spec §8.5). Each returns (reason_code, weight,
evidence). LOOKALIKE_DOMAIN and BLACKLIST_MATCH are fraud-positives, not
mere risk notes.
"""
import re

from pydantic import BaseModel
from rapidfuzz.distance import Levenshtein

from app.pipeline.claims import skeleton
from app.pipeline.hashing import hamming_hex, normalize_text

# --- phrase clusters (en + hinglish) ---
_PHRASE_CLUSTERS: dict[str, re.Pattern[str]] = {
    "guaranteed_returns": re.compile(
        r"guarant\w+ (return|profit|income)|assured (return|profit)|pakka (profit|return)|fixed (daily|weekly|monthly) (profit|return)"
    ),
    "percent_period": re.compile(r"\d{1,3}\s?% (daily|weekly|monthly|per day|per week|har din|roz)"),
    "quota": re.compile(r"(fpi|fii|institutional|hni) (quota|allocation)|special quota"),
    "ipo_fee": re.compile(r"ipo (allotment|allocation) (fee|charge|guarantee)|pay .{0,20}allotment"),
    "unlock_withdrawal": re.compile(r"(pay|deposit|fee).{0,30}(unlock|release|process).{0,20}(withdrawal|payout|funds)"),
    "urgency": re.compile(r"last \d+ (hour|minute|din|ghante)|only today|abhi karo|turant|expires (today|tonight)|limited slots"),
    "secrecy": re.compile(r"(don'?t|do not|mat) (tell|share|batana)|confidential tip|secret (scheme|group|tip)"),
    "group_invite": re.compile(r"(telegram|whatsapp)[^.]{0,30}(group|channel|join)|t\.me/"),
    "apk_download": re.compile(r"\.apk\b|download .{0,20}(apk|app from link)"),
}

# A UPI VPA is handle@psp where the PSP has no dot (`name@okhdfcbank`,
# `name@ybl`). An email address always has one (`investor@company.com`), so
# the trailing-dot lookahead is what separates them. Without it this matched
# every email address in every message and reported it as a demand for money
# — harmless when PAYMENT_ASK was only advisory, actively wrong now that it
# can escalate a verdict.
_UPI_VPA = re.compile(r"\b[\w.\-]{2,}@[a-z]{2,}\b(?!\.)")
_BANK_ACCT = re.compile(r"\b\d{9,18}\b.{0,40}\b[A-Z]{4}0[A-Z0-9]{6}\b", re.S)
_WALLET = re.compile(r"\b(0x[0-9a-fA-F]{40}|[13][1-9A-HJ-NP-Za-km-z]{25,34})\b")

_URL = re.compile(r"(?:https?://)?(?:[a-z0-9\-]+\.)+[a-z]{2,}(?:/[^\s]*)?", re.I)
_IP_HOST = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "is.gd", "rb.gy", "tiny.cc"}
_RISKY_TLDS = {".top", ".xyz", ".icu", ".club", ".online", ".site"}


class RiskSignal(BaseModel):
    code: str
    weight: int
    evidence: str
    campaign: str | None = None


class BlacklistRef(BaseModel):
    kind: str  # domain | phash | phrase
    value: str
    campaign: str


class RiskResult(BaseModel):
    signals: list[RiskSignal] = []
    fraud_positive: bool = False
    risk_high: bool = False
    url_high: bool = False  # §8.6: no-claim + URL-high → LIKELY_FAKE
    campaign: str | None = None

    def codes(self) -> list[str]:
        return [s.code for s in self.signals]


def _extract_hosts(text: str) -> list[tuple[str, str]]:
    """(host, full_match) pairs for every URL-ish token."""
    out = []
    for m in _URL.finditer(text):
        raw = m.group(0)
        host = re.sub(r"^https?://", "", raw, flags=re.I).split("/")[0].lower()
        out.append((host, raw))
    return out


def domain_lookalike(host: str, registered: list[str]) -> str | None:
    """Levenshtein ≤ 2 or homoglyph-skeleton match against registered domains
    (checked per label-chunk so `rneridianbroking-refunds.top` still hits
    `meridianbroking.example`)."""
    if host in registered:
        return None
    host_base = host.rsplit(".", 1)[0]
    chunks = set(re.split(r"[.\-]", host_base)) | {host_base}
    for reg in registered:
        reg_base = reg.rsplit(".", 1)[0]  # meridianbroking
        for chunk in chunks:
            if len(chunk) < 5:
                continue
            if Levenshtein.distance(chunk, reg_base) <= 2:
                return reg
            if skeleton(chunk) == skeleton(reg_base):
                return reg
    return None


def analyze_risk(
    raw_text: str,
    registered_domains: list[str],
    blacklist: list[BlacklistRef],
    phash64: str | None = None,
    phash_match_max_dist: int = 10,
) -> RiskResult:
    text = normalize_text(raw_text or "")
    signals: list[RiskSignal] = []
    campaign: str | None = None

    phrase_hits = [name for name, rx in _PHRASE_CLUSTERS.items() if rx.search(text)]
    for name in phrase_hits:
        signals.append(RiskSignal(code="RISK_PHRASES", weight=2, evidence=name))

    payment_ask = False
    for rx, label in ((_UPI_VPA, "upi_vpa"), (_BANK_ACCT, "bank_account_ifsc"), (_WALLET, "wallet_address")):
        m = rx.search(raw_text or "")
        if m:
            payment_ask = True
            signals.append(RiskSignal(code="PAYMENT_ASK", weight=3, evidence=f"{label}: {m.group(0)[:60]}"))
            break

    lookalike = False
    url_high = False
    for host, raw in _extract_hosts(raw_text or ""):
        if host in registered_domains:
            signals.append(RiskSignal(code="DOMAIN_REGISTERED", weight=0, evidence=host))
            continue
        looked = domain_lookalike(host, registered_domains)
        if looked:
            lookalike = True
            signals.append(
                RiskSignal(code="LOOKALIKE_DOMAIN", weight=5, evidence=f"{host} imitates {looked}")
            )
            continue
        risky = []
        if host.startswith("xn--") or ".xn--" in host:
            risky.append("punycode")
        if _IP_HOST.match(host):
            risky.append("ip-literal host")
        if host in _SHORTENERS:
            risky.append("link shortener")
        if any(host.endswith(tld) for tld in _RISKY_TLDS):
            risky.append("risky TLD")
        if raw.lower().startswith("http://"):
            risky.append("no TLS")
        if risky:
            url_high = url_high or len(risky) >= 2 or "ip-literal host" in risky
            signals.append(RiskSignal(code="URL_RISK", weight=2, evidence=f"{host}: {', '.join(risky)}"))

    for item in blacklist:
        hit = None
        if item.kind == "domain" and any(h == item.value for h, _ in _extract_hosts(raw_text or "")):
            hit = f"domain {item.value}"
        elif item.kind == "phrase" and normalize_text(item.value) in text:
            hit = f"phrase “{item.value}”"
        elif item.kind == "phash" and phash64 and hamming_hex(phash64, item.value) <= phash_match_max_dist:
            hit = f"image matches blacklisted creative (dist {hamming_hex(phash64, item.value)})"
        if hit:
            campaign = campaign or item.campaign
            signals.append(
                RiskSignal(code="BLACKLIST_MATCH", weight=5, evidence=hit, campaign=item.campaign)
            )

    blacklist_hit = any(s.code == "BLACKLIST_MATCH" for s in signals)
    risk_high = lookalike or blacklist_hit or (payment_ask and len(phrase_hits) >= 2)
    fraud_positive = lookalike or blacklist_hit or risk_high
    return RiskResult(
        signals=signals,
        fraud_positive=fraud_positive,
        risk_high=risk_high,
        url_high=url_high,
        campaign=campaign,
    )
