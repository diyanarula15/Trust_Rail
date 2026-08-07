"""Entity-claim extraction (spec §8.4). Rule-based is the required baseline;
the optional LLM path (flag-gated) returns the same schema and falls back
here on any error. OCR is out of scope — captions/bodies only.
"""
import re
import unicodedata
import uuid
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import Entity
from app.pipeline.hashing import normalize_text

# Common visual confusables → latin skeleton (covers the demo's homoglyph
# cases; confusable_homoglyphs detects, this maps). TODO(prod): full UTS#39.
_CONFUSABLE_MAP = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
        "і": "i", "ѕ": "s", "ԁ": "d", "ɡ": "g", "ⅼ": "l", "ο": "o", "α": "a",
        "ν": "v", "τ": "t", "ϲ": "c", "𝗆": "m", "1": "l", "0": "o",
    }
)

_CLAIM_MARKERS = [
    "circular", "registered intermediary", "official", "reg no", "reg. no",
    "sebi registration", "exchange approved", "regulator", "authorised by",
    "authorized by", "compliance notice",
    # Corporate actions and direct investor communications. These are the
    # most common shapes an official market message actually takes in India,
    # and their absence was a real gap: a genuine AGM notice scored "no claim
    # at all", and so would a phishing copy of one. Deliberately phrases that
    # address the reader as a holder or name a specific corporate action —
    # bare words like "dividend" or "board meeting" also appear in ordinary
    # news copy and would drag market reporting into OFFICIAL_CLAIM_UNVERIFIED.
    "dear shareholder", "dear shareholders", "dear investor", "dear investors",
    "dear member", "dear members", "dear unitholder", "dear unitholders",
    "annual general meeting", "extraordinary general meeting", "agm", "egm",
    "postal ballot", "e-voting", "evoting", "remote e-voting",
    "outcome of the board meeting", "record date", "book closure",
    "rights issue", "bonus issue", "buyback offer", "scheme of arrangement",
]


class ClaimEvidence(BaseModel):
    span: str
    matched: str
    score: float


class ClaimResult(BaseModel):
    claimed_entity_id: uuid.UUID | None = None
    claimed_entity_text: str | None = None
    claim_strength: Literal["none", "weak", "strong"] = "none"
    homoglyph_hit: bool = False
    evidence: list[ClaimEvidence] = []


class EntityRef(BaseModel):
    """Pure-matching view of an entity, detached from the DB session."""

    id: uuid.UUID
    name: str
    kind: str
    sebi_reg_no: str
    domains: list[str] = []
    sms_headers: list[str] = []

    @property
    def aliases(self) -> list[str]:
        base = self.name.lower()
        out = [base]
        if base.endswith(" ltd"):
            out.append(base[:-4] + " limited")
        elif base.endswith(" limited"):
            out.append(base[:-8] + " ltd")
        stripped = re.sub(r"\s+(ltd|limited|services|fund|management|finance)\.?$", "", base)
        if stripped != base:
            out.append(stripped)
        paren = re.search(r"\(([^)]+)\)", self.name)
        if paren:
            out.append(paren.group(1).lower())
        return out


def load_entity_refs(db: Session) -> list[EntityRef]:
    entities = (
        db.execute(
            select(Entity).options(
                selectinload(Entity.domains), selectinload(Entity.sms_headers)
            )
        )
        .scalars()
        .all()
    )
    return [
        EntityRef(
            id=e.id,
            name=e.name,
            kind=e.kind.value,
            sebi_reg_no=e.sebi_reg_no,
            domains=[d.domain for d in e.domains],
            sms_headers=[h.header for h in e.sms_headers],
        )
        for e in entities
    ]


def skeleton(text: str) -> str:
    """Homoglyph-normalized lowercase skeleton."""
    text = unicodedata.normalize("NFKC", text).translate(_CONFUSABLE_MAP)
    return normalize_text(text)


def _windowed_fuzzy(needle: str, haystack: str) -> float:
    """token_sort_ratio against sliding token windows the size of the needle.
    Whole-message scoring dilutes single-token typos; token_SET_ratio is out
    because it scores 100 for any token subset (bare "ltd" would strong-claim
    every Ltd entity) — deviation from §8.3's named function, for precision."""
    hay_tokens = haystack.split()
    n = len(needle.split())
    best = 0.0
    for w in {n, n + 1}:
        for i in range(max(1, len(hay_tokens) - w + 1)):
            window = " ".join(hay_tokens[i : i + w])
            best = max(best, fuzz.token_sort_ratio(needle, window))
    return best


def extract_claim(raw_text: str, entities: list[EntityRef]) -> ClaimResult:
    """Rule-based claim extraction (spec §8.4)."""
    if not raw_text or not raw_text.strip():
        return ClaimResult()

    plain = normalize_text(raw_text)
    skel = skeleton(raw_text)
    homoglyph_relevant = plain != skel
    min_score = get_settings().fuzzy_entity_min_score

    best: tuple[float, EntityRef, str, bool] | None = None  # score, ent, span, via_skeleton
    for ent in entities:
        needles: list[str] = [*ent.aliases, ent.sebi_reg_no.lower()]
        needles += [d.lower() for d in ent.domains]
        needles += [h.lower() for h in ent.sms_headers]
        for needle in needles:
            for haystack, via_skel in ((plain, False), (skel, True)):
                if needle in haystack:
                    score = 100.0
                elif len(needle) > 6:
                    score = _windowed_fuzzy(needle, haystack)
                else:
                    continue  # short codes match exactly or not at all
                if score >= min_score and (best is None or score > best[0]):
                    best = (score, ent, needle, via_skel)

    if best is not None:
        score, ent, span, via_skel = best
        return ClaimResult(
            claimed_entity_id=ent.id,
            claimed_entity_text=ent.name,
            claim_strength="strong",
            homoglyph_hit=via_skel and homoglyph_relevant,
            evidence=[ClaimEvidence(span=span, matched=ent.name, score=score)],
        )

    for marker in _CLAIM_MARKERS:
        if marker in plain:
            return ClaimResult(
                claimed_entity_text=None,
                claim_strength="weak",
                evidence=[ClaimEvidence(span=marker, matched="official-claim marker", score=100.0)],
            )
    return ClaimResult()


def extract_claim_llm(raw_text: str, entities: list[EntityRef]) -> ClaimResult:
    """Optional Anthropic path (LLM_ENABLED). Same schema; rule-based on ANY
    failure. Result cached by text sha in Redis."""
    settings = get_settings()
    if not settings.llm_enabled or not settings.anthropic_api_key:
        return extract_claim(raw_text, entities)
    try:
        import hashlib
        import json

        import httpx

        from app.db import get_redis

        cache_key = f"trustrail:claim:{hashlib.sha256(raw_text.encode()).hexdigest()}"
        redis = get_redis()
        cached = redis.get(cache_key)
        if cached:
            return ClaimResult.model_validate_json(cached)

        catalog = [{"id": str(e.id), "name": e.name, "reg_no": e.sebi_reg_no} for e in entities]
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            timeout=5.0,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Extract any claim that this text was issued by one of these "
                            f"registered entities: {json.dumps(catalog)}\n\nText:\n{raw_text[:4000]}\n\n"
                            'Reply ONLY with JSON: {"claimed_entity_id": "<id or null>", '
                            '"claimed_entity_text": "<verbatim span or null>", '
                            '"claim_strength": "none|weak|strong"}'
                        ),
                    }
                ],
            },
        )
        resp.raise_for_status()
        payload = json.loads(resp.json()["content"][0]["text"])
        result = ClaimResult.model_validate(payload)
        redis.set(cache_key, result.model_dump_json(), ex=3600)
        return result
    except Exception:
        return extract_claim(raw_text, entities)
