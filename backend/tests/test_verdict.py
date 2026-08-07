"""Verdict engine gate tests (spec §8.6, §20 guardrail).

Covers: all five verdicts; key-revocation timing on both sides; near-match
must NOT verify; homoglyph claim; and the release-blocker guardrail — no
input combination may yield VERIFIED without a valid chain or a registry
match to a PUBLISHED communication.
"""
import uuid
from datetime import UTC, datetime

import pytest

from app.pipeline.claims import EntityRef, extract_claim
from app.pipeline.risk import BlacklistRef, analyze_risk
from app.pipeline.verdict import (
    Candidate,
    Decision,
    DecisionInput,
    DecisionRule,
    MatchThresholds,
    QueryHashes,
    ReasonCode,
    RegistryMatch,
    Verdict,
    decide,
    match_registry,
)
from app.trust.envelope import EnvelopeResult, KeyInfo

T = MatchThresholds()
ENTITY_ID = uuid.uuid4()
COMM_ID = uuid.uuid4()
SIGNED_AT = datetime(2026, 7, 10, 9, 30, tzinfo=UTC)

MERIDIAN = EntityRef(
    id=uuid.uuid4(), name="Meridian Broking Ltd", kind="broker",
    sebi_reg_no="DEMO-INZ-000123", domains=["meridianbroking.example"], sms_headers=["MERIDN"],
)


def _candidate(status: str = "published", **kw) -> Candidate:
    return Candidate(
        communication_id=COMM_ID, entity_id=ENTITY_ID, comm_status=status,
        sha256=kw.get("sha256", "aa" * 32), phash64=kw.get("phash64"),
        simhash64=kw.get("simhash64"), video_frame_hashes=kw.get("video_frame_hashes"),
    )


def _env(valid: bool = True, key_status: str = "active", revoked_at=None) -> EnvelopeResult:
    return EnvelopeResult(
        valid=valid, maker_ok=valid, checker_ok=None, checker_required=False,
        key_states={"k1": KeyInfo(key_id="k1", public_key_ed25519="x",
                                  status=key_status, revoked_at=revoked_at)},
        signed_at=SIGNED_AT, entity_active=True,
    )


# ---- the five verdicts ----

def test_verified_via_valid_envelope() -> None:
    d = decide(DecisionInput(envelope_result=_env(), envelope_entity_id=ENTITY_ID))
    assert d.verdict == Verdict.VERIFIED
    assert ReasonCode.SIG_CHAIN_VALID in d.reasons
    assert d.matched_entity_id == ENTITY_ID


def test_verified_via_registry_phash_match() -> None:
    cand = _candidate(phash64="00ff00ff00ff00ff")
    m = match_registry(QueryHashes(sha256="bb" * 32, phash64="00ff00ff00ff00fe"), [cand], T)
    d = decide(DecisionInput(registry_match=m))
    assert d.verdict == Verdict.VERIFIED
    assert ReasonCode.PHASH_MATCH in d.reasons
    assert d.matched_communication_id == COMM_ID
    assert d.trace[-1].outcome == "skipped_short_circuit"


def test_verified_notice_key_revoked_after_signing() -> None:
    d = decide(DecisionInput(
        envelope_result=_env(key_status="revoked",
                             revoked_at=datetime(2026, 7, 12, tzinfo=UTC)),
        envelope_entity_id=ENTITY_ID,
    ))
    assert d.verdict == Verdict.VERIFIED_NOTICE
    assert ReasonCode.KEY_REVOKED_AFTER_SIGNING in d.reasons


def test_signed_after_revocation_is_tampered_not_verified() -> None:
    """Other side of the timing rule: revoked BEFORE signing → forged."""
    d = decide(DecisionInput(
        envelope_result=_env(key_status="revoked",
                             revoked_at=datetime(2026, 7, 1, tzinfo=UTC)),
        envelope_entity_id=ENTITY_ID,
        claims=extract_claim("From Meridian Broking Ltd", [MERIDIAN]),
    ))
    assert d.verdict == Verdict.LIKELY_FAKE  # tampered sig is a fraud-positive
    assert ReasonCode.TAMPERED_SIGNATURE in d.reasons
    assert d.verdict not in (Verdict.VERIFIED, Verdict.VERIFIED_NOTICE)


def test_official_claim_unverified() -> None:
    claims = extract_claim("Important circular from Kumaon Metals Ltd", [
        EntityRef(id=ENTITY_ID, name="Kumaon Metals Ltd", kind="listed_company",
                  sebi_reg_no="DEMO-INE-000451", domains=["kumaonmetals.example"],
                  sms_headers=["KUMAON"]),
    ])
    d = decide(DecisionInput(claims=claims))
    assert d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED
    assert ReasonCode.ENTITY_CLAIM_STRONG in d.reasons
    assert d.claimed_entity_id == ENTITY_ID
    assert d.matched_entity_id is None  # claimed ≠ proven


def test_likely_fake_lookalike_sms() -> None:
    text = ("MERIDN IPO allotment confirmed! Pay allotment fee now to "
            "http://rneridianbroking-refunds.top/claim — last 2 hours only. "
            "Pay via UPI meridianrefund@okpay")
    claims = extract_claim(text, [MERIDIAN])
    risk = analyze_risk(text, ["meridianbroking.example"],
                        [BlacklistRef(kind="domain", value="rneridianbroking-refunds.top",
                                      campaign="FXROAD-DEMO")])
    d = decide(DecisionInput(claims=claims, risk=risk))
    assert d.verdict == Verdict.LIKELY_FAKE
    assert ReasonCode.LOOKALIKE_DOMAIN in d.reasons
    assert ReasonCode.BLACKLIST_MATCH in d.reasons
    assert d.campaign == "FXROAD-DEMO"


def test_informational_plain_news() -> None:
    text = "Benchmark indices ended higher today led by banking and IT stocks."
    d = decide(DecisionInput(
        claims=extract_claim(text, [MERIDIAN]),
        risk=analyze_risk(text, ["meridianbroking.example"], []),
    ))
    assert d.verdict == Verdict.INFORMATIONAL
    assert ReasonCode.NO_OFFICIAL_CLAIM in d.reasons
    fraud = {ReasonCode.LOOKALIKE_DOMAIN, ReasonCode.BLACKLIST_MATCH,
             ReasonCode.TAMPERED_SIGNATURE, ReasonCode.TAMPERED_CONTENT}
    assert not (set(d.reasons) & fraud)


# ---- near-match must NOT verify ----

def test_phash_near_match_does_not_verify() -> None:
    cand = _candidate(phash64="0000000000000000")
    q = QueryHashes(sha256="bb" * 32, phash64="0000000000003fff")  # dist 14: near band
    m = match_registry(q, [cand], T)
    assert m.kind == "near"
    d = decide(DecisionInput(registry_match=m,
                             claims=extract_claim("From Meridian Broking Ltd", [MERIDIAN])))
    assert d.verdict != Verdict.VERIFIED
    assert ReasonCode.PHASH_NEAR in d.reasons
    assert d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED  # claim + no fraud-positive


def test_match_against_revoked_comm_is_withdrawn_not_verified() -> None:
    cand = _candidate(status="revoked", sha256="cc" * 32)
    m = match_registry(QueryHashes(sha256="cc" * 32), [cand], T)
    d = decide(DecisionInput(registry_match=m))
    assert d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED
    assert ReasonCode.COMM_WITHDRAWN in d.reasons


# ---- homoglyph claim ----

def test_homoglyph_claim_case() -> None:
    text = "Notice from Mеridiаn Broking Ltd: verify your account at http://meridian-verify.xyz"
    claims = extract_claim(text, [MERIDIAN])
    assert claims.homoglyph_hit
    risk = analyze_risk(text, ["meridianbroking.example"], [])
    d = decide(DecisionInput(claims=claims, risk=risk))
    assert ReasonCode.HOMOGLYPH_ENTITY in d.reasons
    assert d.verdict in (Verdict.LIKELY_FAKE, Verdict.OFFICIAL_CLAIM_UNVERIFIED)
    assert d.verdict != Verdict.VERIFIED


# ---- tampered content ----

def test_tampered_content_referenced_comm_mismatch() -> None:
    d = decide(DecisionInput(
        referenced_comm_sha256="aa" * 32, query_sha256="dd" * 32,
        claims=extract_claim("From Meridian Broking Ltd", [MERIDIAN]),
    ))
    assert d.verdict == Verdict.LIKELY_FAKE
    assert ReasonCode.TAMPERED_CONTENT in d.reasons


# ---- §20 guardrail: release blocker ----

class TestGuardrailNoUnprovenVerified:
    """No input combination may produce VERIFIED without proof."""

    UNPROVEN: list[DecisionInput] = [
        DecisionInput(),  # nothing at all
        DecisionInput(envelope_result=_env(valid=False)),  # broken envelope
        DecisionInput(registry_match=RegistryMatch(kind="near", candidate=_candidate(),
                                                   detail="phash near, dist 14")),
        DecisionInput(claims=extract_claim("From Meridian Broking Ltd — official circular",
                                           [MERIDIAN])),  # loud claim, zero proof
        DecisionInput(c2pa_present=True, c2pa_valid=False),  # invalid c2pa
    ]

    def test_unproven_inputs_never_verify(self) -> None:
        for inp in self.UNPROVEN:
            d: Decision = decide(inp)
            assert d.verdict not in (Verdict.VERIFIED, Verdict.VERIFIED_NOTICE), (
                f"guardrail violated for {inp}"
            )

    def test_engine_guard_raises_on_forced_bad_state(self) -> None:
        """The runtime assertion itself works."""
        from app.pipeline.verdict import _guard

        with pytest.raises(AssertionError):
            _guard(Verdict.VERIFIED, [ReasonCode.ENTITY_CLAIM_STRONG])

    def test_verified_paths_all_carry_proof_reason(self) -> None:
        proofs = {ReasonCode.SIG_CHAIN_VALID, ReasonCode.C2PA_VALID,
                  ReasonCode.HASH_EXACT_MATCH, ReasonCode.PHASH_MATCH, ReasonCode.PDQ_MATCH,
                  ReasonCode.SIMHASH_MATCH, ReasonCode.VIDEO_MATCH}
        proven = [
            decide(DecisionInput(envelope_result=_env(), envelope_entity_id=ENTITY_ID)),
            decide(DecisionInput(registry_match=match_registry(
                QueryHashes(sha256="aa" * 32), [_candidate()], T))),
        ]
        for d in proven:
            assert d.verdict == Verdict.VERIFIED
            assert set(d.reasons) & proofs


class TestStrictEscalation:
    """Strict about fraud signals, never strict about absence of proof.

    The rule this replaced was asymmetric: a risky URL escalated only when
    NO claim was present, so adding an official-sounding claim — strictly
    more dangerous — produced a *softer* verdict.
    """

    RISKY_URL = "Login now at http://emeetings-example-verify.top/claim before it expires today."

    def test_risky_url_escalates_with_a_claim(self) -> None:
        text = f"Dear Shareholder, AGM notice. {self.RISKY_URL}"
        d = decide(DecisionInput(
            claims=extract_claim(text, [MERIDIAN]),
            risk=analyze_risk(text, ["meridianbroking.example"], []),
        ))
        assert d.verdict == Verdict.LIKELY_FAKE
        assert d.rule == DecisionRule.CLAIM_WITH_FRAUD_SIGNALS
        assert ReasonCode.URL_RISK in d.escalating_reasons

    def test_risky_url_escalates_without_a_claim(self) -> None:
        d = decide(DecisionInput(risk=analyze_risk(self.RISKY_URL, [], [])))
        assert d.verdict == Verdict.LIKELY_FAKE
        assert d.rule == DecisionRule.FRAUD_SIGNALS_NO_CLAIM

    def test_lookalike_domain_alone_escalates(self) -> None:
        """Previously missed entirely: a lookalike with no entity named fell
        through to INFORMATIONAL."""
        text = "Update your details at http://rneridianbroking-refunds.top/claim"
        d = decide(DecisionInput(risk=analyze_risk(text, ["meridianbroking.example"], [])))
        assert d.verdict == Verdict.LIKELY_FAKE
        assert ReasonCode.LOOKALIKE_DOMAIN in d.reasons

    def test_absence_of_proof_never_escalates(self) -> None:
        """The other half of the policy, and the more important half: an
        official-looking message with no fraud signals is 'cannot confirm',
        never 'fake' — a genuine issuer outside the registry lands here."""
        text = ("Dear Shareholder, 18th AGM of Some Housing Finance Ltd is scheduled today "
                "at 3:45 PM through virtual mode. Please login to https://emeetings.example.com/ "
                "to participate.")
        d = decide(DecisionInput(
            claims=extract_claim(text, [MERIDIAN]),
            risk=analyze_risk(text, ["meridianbroking.example"], []),
        ))
        assert d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED
        assert d.rule == DecisionRule.CLAIM_WITHOUT_MATCH
        assert d.escalating_reasons == []

    def test_ordinary_news_is_untouched_by_strictness(self) -> None:
        text = "Benchmark indices ended higher today led by banking and IT stocks."
        d = decide(DecisionInput(
            claims=extract_claim(text, [MERIDIAN]),
            risk=analyze_risk(text, ["meridianbroking.example"], []),
        ))
        assert d.verdict == Verdict.INFORMATIONAL
        assert d.rule == DecisionRule.NO_CLAIM

    def test_contact_email_is_not_a_payment_demand(self) -> None:
        """An email address is not a UPI handle; treating it as one used to
        put PAYMENT_ASK on ordinary corporate mail, which now escalates."""
        text = "Dear Shareholder, for queries write to investor.relations@example.com"
        risk = analyze_risk(text, [], [])
        assert not any(s.code == "PAYMENT_ASK" for s in risk.signals)
        d = decide(DecisionInput(claims=extract_claim(text, [MERIDIAN]), risk=risk))
        assert d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED

    def test_every_verdict_carries_a_rule(self) -> None:
        for inp in [
            DecisionInput(envelope_result=_env(), envelope_entity_id=ENTITY_ID),
            DecisionInput(registry_match=match_registry(
                QueryHashes(sha256="aa" * 32), [_candidate()], T)),
            DecisionInput(claims=extract_claim("Official circular", [MERIDIAN])),
            DecisionInput(),
        ]:
            assert decide(inp).rule in set(DecisionRule)


# ---- registry matcher unit coverage ----

def test_match_registry_exact_beats_perceptual() -> None:
    cand = _candidate(sha256="ee" * 32, phash64="00ff00ff00ff00ff")
    m = match_registry(QueryHashes(sha256="ee" * 32, phash64="00ff00ff00ff00ff"), [cand], T)
    assert m.kind == "exact"


def test_match_registry_simhash() -> None:
    cand = _candidate(simhash64="00ff00ff00ff00ff")
    m = match_registry(QueryHashes(sha256="xx", simhash64="00ff00ff00ff00fd"), [cand], T)
    assert m.kind == "simhash"


def test_match_registry_video_ratio() -> None:
    frames = ["00ff00ff00ff00ff", "ff00ff00ff00ff00", "0f0f0f0f0f0f0f0f", "f0f0f0f0f0f0f0f0"]
    cand = _candidate(video_frame_hashes=frames)
    q = QueryHashes(sha256="xx", video_frame_hashes=[frames[0], frames[1], "ffffffffffffffff"])
    m = match_registry(q, [cand], T)
    assert m.kind == "video"  # 2/3 ≈ 0.67 ≥ 0.55


def test_match_registry_none() -> None:
    m = match_registry(QueryHashes(sha256="aa" * 32), [], T)
    assert m.kind == "none"
