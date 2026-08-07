"""THE verdict engine (spec §8.6) — ordered, short-circuiting, honest.

`decide()` is pure: it consumes prepared signals and returns a verdict with
reasons and a stage trace. A runtime guardrail asserts that VERIFIED can
only ever be emitted with cryptographic or registry proof in hand — the
spec §20 release blocker, enforced in code AND in tests.
"""
import enum
import time
import uuid
from typing import Literal

from pydantic import BaseModel

from app.pipeline.claims import ClaimResult
from app.pipeline.hashing import hamming_hex, video_match_ratio
from app.pipeline.risk import RiskResult
from app.trust.envelope import EnvelopeResult


class ReasonCode(str, enum.Enum):
    SIG_CHAIN_VALID = "SIG_CHAIN_VALID"
    C2PA_VALID = "C2PA_VALID"
    C2PA_MISSING = "C2PA_MISSING"
    C2PA_INVALID = "C2PA_INVALID"
    TAMPERED_SIGNATURE = "TAMPERED_SIGNATURE"
    TAMPERED_CONTENT = "TAMPERED_CONTENT"
    KEY_REVOKED_AFTER_SIGNING = "KEY_REVOKED_AFTER_SIGNING"
    HASH_EXACT_MATCH = "HASH_EXACT_MATCH"
    PHASH_MATCH = "PHASH_MATCH"
    PDQ_MATCH = "PDQ_MATCH"
    SIMHASH_MATCH = "SIMHASH_MATCH"
    VIDEO_MATCH = "VIDEO_MATCH"
    PHASH_NEAR = "PHASH_NEAR"
    COMM_WITHDRAWN = "COMM_WITHDRAWN"
    ENTITY_CLAIM_STRONG = "ENTITY_CLAIM_STRONG"
    ENTITY_CLAIM_WEAK = "ENTITY_CLAIM_WEAK"
    HOMOGLYPH_ENTITY = "HOMOGLYPH_ENTITY"
    LOOKALIKE_DOMAIN = "LOOKALIKE_DOMAIN"
    DOMAIN_REGISTERED = "DOMAIN_REGISTERED"
    DOMAIN_NOT_REGISTERED = "DOMAIN_NOT_REGISTERED"
    DKIM_ALIGN_PASS = "DKIM_ALIGN_PASS"
    DKIM_ALIGN_FAIL = "DKIM_ALIGN_FAIL"
    AUTH_HEADERS_UNAVAILABLE = "AUTH_HEADERS_UNAVAILABLE"
    BLACKLIST_MATCH = "BLACKLIST_MATCH"
    RISK_PHRASES = "RISK_PHRASES"
    PAYMENT_ASK = "PAYMENT_ASK"
    URL_RISK = "URL_RISK"
    NO_OFFICIAL_CLAIM = "NO_OFFICIAL_CLAIM"


class Verdict(str, enum.Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_NOTICE = "VERIFIED_NOTICE"
    OFFICIAL_CLAIM_UNVERIFIED = "OFFICIAL_CLAIM_UNVERIFIED"
    LIKELY_FAKE = "LIKELY_FAKE"
    INFORMATIONAL = "INFORMATIONAL"


class TraceStep(BaseModel):
    stage: str
    outcome: str
    ms: int


class QueryHashes(BaseModel):
    sha256: str | None = None
    phash64: str | None = None
    pdq256: str | None = None
    simhash64: str | None = None
    video_frame_hashes: list[str] | None = None


class Candidate(BaseModel):
    """A published (or revoked) communication's artifact hashes."""

    communication_id: uuid.UUID
    entity_id: uuid.UUID
    comm_status: Literal["published", "revoked"]
    sha256: str
    phash64: str | None = None
    pdq256: str | None = None
    simhash64: str | None = None
    video_frame_hashes: list[str] | None = None


class MatchThresholds(BaseModel):
    phash_match_max_dist: int = 10
    phash_near_max_dist: int = 16
    pdq_match_max_dist: int = 31
    video_frame_match_ratio: float = 0.55
    simhash_match_max_dist: int = 6


class RegistryMatch(BaseModel):
    kind: Literal["exact", "phash", "pdq", "simhash", "video", "near", "none"] = "none"
    candidate: Candidate | None = None
    detail: str = ""

    # --- explanation only, never read by decide() ---
    # The closest thing the sweep saw, even when nothing crossed a threshold,
    # so the UI can say "closest registered item was 31 of 64 bits away"
    # instead of a bare "no match". Populated on near/miss results; on a hit
    # the matched `candidate` above is the closest by definition.
    closest: Candidate | None = None
    closest_algorithm: str | None = None
    closest_distance: int | None = None
    closest_bits: int | None = None
    closest_video_ratio: float | None = None


class DecisionInput(BaseModel):
    envelope_result: EnvelopeResult | None = None
    envelope_entity_id: uuid.UUID | None = None  # from the envelope body
    c2pa_present: bool = False
    c2pa_valid: bool | None = None
    registry_match: RegistryMatch = RegistryMatch()
    claims: ClaimResult = ClaimResult()
    risk: RiskResult = RiskResult()
    referenced_comm_sha256: str | None = None  # for TAMPERED_CONTENT
    query_sha256: str | None = None
    extra_reasons: list[ReasonCode] = []  # e.g. email-path DKIM codes


class DecisionRule(str, enum.Enum):
    """Which branch of §8.6 produced the verdict.

    Recorded so the answer can explain *why* it is what it is, rather than
    only listing signals and leaving the reader to infer the rule. Strictness
    is only meaningful if it is legible.
    """

    SIGNATURE_VALID = "SIGNATURE_VALID"
    SIGNATURE_VALID_KEY_REVOKED = "SIGNATURE_VALID_KEY_REVOKED"
    REGISTRY_MATCH = "REGISTRY_MATCH"
    REGISTRY_MATCH_KEY_REVOKED = "REGISTRY_MATCH_KEY_REVOKED"
    MATCHED_WITHDRAWN = "MATCHED_WITHDRAWN"
    CLAIM_WITH_FRAUD_SIGNALS = "CLAIM_WITH_FRAUD_SIGNALS"
    CLAIM_WITHOUT_MATCH = "CLAIM_WITHOUT_MATCH"
    FRAUD_SIGNALS_NO_CLAIM = "FRAUD_SIGNALS_NO_CLAIM"
    NO_CLAIM = "NO_CLAIM"


# Signals that escalate to LIKELY_FAKE under the strict policy. Absence of
# proof is deliberately NOT in here: failing to match the registry means "we
# cannot confirm", never "this is a scam" — otherwise every genuine message
# from an issuer outside the registry gets called fraud.
_ESCALATING = {
    ReasonCode.BLACKLIST_MATCH,
    ReasonCode.LOOKALIKE_DOMAIN,
    ReasonCode.HOMOGLYPH_ENTITY,
    ReasonCode.TAMPERED_SIGNATURE,
    ReasonCode.TAMPERED_CONTENT,
    ReasonCode.URL_RISK,
    ReasonCode.PAYMENT_ASK,
}


class Decision(BaseModel):
    verdict: Verdict
    rule: DecisionRule = DecisionRule.NO_CLAIM
    # The specific signals that drove an escalation, so the card can name them
    # instead of asserting a conclusion.
    escalating_reasons: list[ReasonCode] = []
    reasons: list[ReasonCode]
    matched_communication_id: uuid.UUID | None = None
    matched_entity_id: uuid.UUID | None = None  # proven issuer only
    claimed_entity_id: uuid.UUID | None = None  # who the content SAYS it's from
    campaign: str | None = None
    trace: list[TraceStep] = []


def match_registry(
    q: QueryHashes, candidates: list[Candidate], t: MatchThresholds
) -> RegistryMatch:
    """Spec §8.3: exact sha256 first, then perceptual/simhash/video sweep.
    Full scan is fine at demo scale — TODO(prod): pgvector/BK-tree."""
    for c in candidates:
        if q.sha256 and q.sha256 == c.sha256:
            return RegistryMatch(kind="exact", candidate=c, detail="sha256 exact")

    best_near: RegistryMatch = RegistryMatch()
    # closest-seen tracking is explanation-only (see RegistryMatch) — it never
    # changes which branch below fires. Compared on normalized distance so a
    # pdq256 miss doesn't outrank a phash64 one purely on bit width.
    closest: tuple[float, int, int, str, Candidate] | None = None
    closest_video: tuple[float, Candidate] | None = None

    def note(dist: int, bits: int, algorithm: str, cand: Candidate) -> None:
        nonlocal closest
        if closest is None or dist / bits < closest[0]:
            closest = (dist / bits, dist, bits, algorithm, cand)

    for c in candidates:
        if q.phash64 and c.phash64:
            d = hamming_hex(q.phash64, c.phash64)
            note(d, 64, "phash64", c)
            if d <= t.phash_match_max_dist:
                return RegistryMatch(kind="phash", candidate=c, detail=f"phash dist {d}")
            if d <= t.phash_near_max_dist and best_near.kind == "none":
                best_near = RegistryMatch(kind="near", candidate=c, detail=f"phash near, dist {d}")
        if q.pdq256 and c.pdq256:
            d = hamming_hex(q.pdq256, c.pdq256)
            note(d, 256, "pdq256", c)
            if d <= t.pdq_match_max_dist:
                return RegistryMatch(kind="pdq", candidate=c, detail=f"pdq dist {d}")
        if q.simhash64 and c.simhash64:
            d = hamming_hex(q.simhash64, c.simhash64)
            note(d, 64, "simhash64", c)
            if d <= t.simhash_match_max_dist:
                return RegistryMatch(kind="simhash", candidate=c, detail=f"simhash dist {d}")
        if q.video_frame_hashes and c.video_frame_hashes:
            ratio = video_match_ratio(
                q.video_frame_hashes, c.video_frame_hashes, t.phash_match_max_dist
            )
            if closest_video is None or ratio > closest_video[0]:
                closest_video = (ratio, c)
            if ratio >= t.video_frame_match_ratio:
                return RegistryMatch(kind="video", candidate=c, detail=f"frame ratio {ratio:.2f}")

    if closest is not None:
        _, dist, bits, algorithm, cand = closest
        best_near.closest = cand
        best_near.closest_algorithm = algorithm
        best_near.closest_distance = dist
        best_near.closest_bits = bits
    if closest_video is not None:
        best_near.closest_video_ratio = closest_video[0]
        if best_near.closest is None:
            best_near.closest = closest_video[1]
    return best_near


_MATCH_REASON = {
    "exact": ReasonCode.HASH_EXACT_MATCH,
    "phash": ReasonCode.PHASH_MATCH,
    "pdq": ReasonCode.PDQ_MATCH,
    "simhash": ReasonCode.SIMHASH_MATCH,
    "video": ReasonCode.VIDEO_MATCH,
}

# §20 guardrail: VERIFIED requires one of these proof reasons. Enforced at
# runtime below and by tests/test_verdict.py — release blocker if violated.
_VERIFIED_PROOFS = {ReasonCode.SIG_CHAIN_VALID, ReasonCode.C2PA_VALID, *_MATCH_REASON.values()}


def _guard(verdict: Verdict, reasons: list[ReasonCode]) -> None:
    if verdict in (Verdict.VERIFIED, Verdict.VERIFIED_NOTICE) and not (
        set(reasons) & (_VERIFIED_PROOFS | {ReasonCode.KEY_REVOKED_AFTER_SIGNING})
    ):
        raise AssertionError(
            f"guardrail: {verdict} without cryptographic/registry proof — reasons {reasons}"
        )


def decide(inp: DecisionInput) -> Decision:
    reasons: list[ReasonCode] = list(inp.extra_reasons)
    trace: list[TraceStep] = []
    campaign = inp.risk.campaign

    # ---- stage 1: hard binding ----
    t0 = time.monotonic()
    env = inp.envelope_result
    stage1_outcome = "no_manifest"
    if inp.c2pa_present:
        if inp.c2pa_valid:
            reasons.append(ReasonCode.C2PA_VALID)
            stage1_outcome = "c2pa_valid"
        else:
            reasons.append(ReasonCode.C2PA_INVALID)
            stage1_outcome = "c2pa_invalid"

    if env is not None:
        if env.valid:
            revoked = [
                k for k in env.key_states.values() if k.status == "revoked" and k.revoked_at
            ]
            signed_at = env.signed_at
            if not revoked:
                reasons.append(ReasonCode.SIG_CHAIN_VALID)
                trace.append(TraceStep(stage="hard_binding", outcome="sig_chain_valid",
                                       ms=int((time.monotonic() - t0) * 1000)))
                d = Decision(verdict=Verdict.VERIFIED, rule=DecisionRule.SIGNATURE_VALID,
                             reasons=reasons, trace=trace,
                             matched_entity_id=inp.envelope_entity_id, campaign=campaign)
                _guard(d.verdict, d.reasons)
                return d
            if signed_at and all(signed_at < k.revoked_at for k in revoked):
                reasons.append(ReasonCode.KEY_REVOKED_AFTER_SIGNING)
                trace.append(TraceStep(stage="hard_binding", outcome="key_revoked_after_signing",
                                       ms=int((time.monotonic() - t0) * 1000)))
                d = Decision(verdict=Verdict.VERIFIED_NOTICE,
                             rule=DecisionRule.SIGNATURE_VALID_KEY_REVOKED,
                             reasons=reasons, trace=trace,
                             matched_entity_id=inp.envelope_entity_id, campaign=campaign)
                _guard(d.verdict, d.reasons)
                return d
            # signed at/after revocation — treated as forged
            reasons.append(ReasonCode.TAMPERED_SIGNATURE)
            stage1_outcome = "signed_after_revocation"
        else:
            reasons.append(ReasonCode.TAMPERED_SIGNATURE)
            stage1_outcome = "envelope_invalid"
    elif not inp.c2pa_present:
        reasons.append(ReasonCode.C2PA_MISSING)
    trace.append(TraceStep(stage="hard_binding", outcome=stage1_outcome,
                           ms=int((time.monotonic() - t0) * 1000)))

    # ---- stage 2: registry match ----
    t0 = time.monotonic()
    m = inp.registry_match
    if m.kind in _MATCH_REASON and m.candidate is not None:
        if m.candidate.comm_status == "published":
            reasons.append(_MATCH_REASON[m.kind])
            trace.append(TraceStep(stage="registry_match", outcome=m.detail.replace(" ", "_"),
                                   ms=int((time.monotonic() - t0) * 1000)))
            trace.append(TraceStep(stage="claims_risk", outcome="skipped_short_circuit", ms=0))
            d = Decision(verdict=Verdict.VERIFIED, rule=DecisionRule.REGISTRY_MATCH,
                         reasons=reasons, trace=trace,
                         matched_communication_id=m.candidate.communication_id,
                         matched_entity_id=m.candidate.entity_id, campaign=campaign)
            _guard(d.verdict, d.reasons)
            return d
        reasons.append(ReasonCode.COMM_WITHDRAWN)
        trace.append(TraceStep(stage="registry_match", outcome="matched_revoked_comm",
                               ms=int((time.monotonic() - t0) * 1000)))
        trace.append(TraceStep(stage="claims_risk", outcome="skipped_short_circuit", ms=0))
        return Decision(verdict=Verdict.OFFICIAL_CLAIM_UNVERIFIED,
                        rule=DecisionRule.MATCHED_WITHDRAWN,
                        reasons=reasons, trace=trace,
                        matched_communication_id=m.candidate.communication_id,
                        matched_entity_id=m.candidate.entity_id, campaign=campaign)
    near = m.kind == "near"
    if near:
        reasons.append(ReasonCode.PHASH_NEAR)
    trace.append(TraceStep(stage="registry_match",
                           outcome=m.detail.replace(" ", "_") if near else "no_match",
                           ms=int((time.monotonic() - t0) * 1000)))

    # TAMPERED_CONTENT: input claims to BE a specific communication but isn't
    if (
        inp.referenced_comm_sha256
        and inp.query_sha256
        and inp.referenced_comm_sha256 != inp.query_sha256
    ):
        reasons.append(ReasonCode.TAMPERED_CONTENT)

    # ---- stage 3: claims + risk ----
    t0 = time.monotonic()
    claims, risk = inp.claims, inp.risk
    for s in risk.signals:
        code = ReasonCode(s.code)
        if code not in reasons:
            reasons.append(code)
    if claims.claim_strength == "strong":
        reasons.append(ReasonCode.ENTITY_CLAIM_STRONG)
        if claims.homoglyph_hit:
            reasons.append(ReasonCode.HOMOGLYPH_ENTITY)
    elif claims.claim_strength == "weak":
        reasons.append(ReasonCode.ENTITY_CLAIM_WEAK)

    # Strict policy: ANY fraud signal escalates, whether or not the content
    # also claims to be official. The previous rule only escalated a bare
    # URL/blacklist hit when no claim was present, so adding an official-
    # sounding claim — strictly more dangerous — produced a *softer* verdict.
    escalating = [c for c in _ESCALATING if c in reasons]
    fraud_positive = bool(escalating) or risk.fraud_positive or risk.url_high

    if claims.claim_strength in ("strong", "weak"):
        if fraud_positive:
            verdict, rule = Verdict.LIKELY_FAKE, DecisionRule.CLAIM_WITH_FRAUD_SIGNALS
            outcome = "claim_plus_fraud_positive"
        else:
            verdict, rule = Verdict.OFFICIAL_CLAIM_UNVERIFIED, DecisionRule.CLAIM_WITHOUT_MATCH
            outcome = "claim_without_match"
    elif fraud_positive:
        verdict, rule = Verdict.LIKELY_FAKE, DecisionRule.FRAUD_SIGNALS_NO_CLAIM
        outcome = "no_claim_fraud_positive"
    else:
        verdict, rule = Verdict.INFORMATIONAL, DecisionRule.NO_CLAIM
        reasons.append(ReasonCode.NO_OFFICIAL_CLAIM)
        outcome = "no_official_claim"
    trace.append(TraceStep(stage="claims_risk", outcome=outcome,
                           ms=int((time.monotonic() - t0) * 1000)))

    _guard(verdict, reasons)
    return Decision(
        verdict=verdict,
        rule=rule,
        escalating_reasons=escalating,
        reasons=reasons,
        claimed_entity_id=claims.claimed_entity_id,
        campaign=campaign,
        trace=trace,
    )
