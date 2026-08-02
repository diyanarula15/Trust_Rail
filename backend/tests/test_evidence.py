"""Match evidence: explains the registry stage without influencing it.

The load-bearing property is the last class here — building evidence must
never change what `decide()` would have said, since the §20 guardrail is a
statement about the verdict engine alone.
"""
import uuid

from app.pipeline.evidence import build_match_evidence
from app.pipeline.hashing import differing_bit_indices
from app.pipeline.verdict import (
    Candidate,
    DecisionInput,
    MatchThresholds,
    QueryHashes,
    decide,
    match_registry,
)

T = MatchThresholds()
ENTITY_ID = uuid.uuid4()
COMM_ID = uuid.uuid4()


def _candidate(**kw) -> Candidate:
    return Candidate(
        communication_id=COMM_ID,
        entity_id=ENTITY_ID,
        comm_status=kw.get("comm_status", "published"),
        sha256=kw.get("sha256", "aa" * 32),
        phash64=kw.get("phash64"),
        simhash64=kw.get("simhash64"),
        video_frame_hashes=kw.get("video_frame_hashes"),
    )


class TestDifferingBits:
    def test_msb_first_indexing(self) -> None:
        # 0x8000... differs from 0x0000... in bit 0 (most significant)
        assert differing_bit_indices("8000000000000000", "0000000000000000") == [0]
        # low bit is index 63
        assert differing_bit_indices("0000000000000001", "0000000000000000") == [63]

    def test_count_matches_hamming(self) -> None:
        a, b = "00ff00ff00ff00ff", "00ff00ff00ff00fe"
        assert len(differing_bit_indices(a, b)) == 1

    def test_identical_hashes_have_no_differing_bits(self) -> None:
        assert differing_bit_indices("abcd" * 4, "abcd" * 4) == []


class TestEvidenceShape:
    def test_phash_match_reports_distance_and_thresholds(self) -> None:
        cand = _candidate(phash64="00ff00ff00ff00ff")
        q = QueryHashes(sha256="bb" * 32, phash64="00ff00ff00ff00fe")
        ev = build_match_evidence(q, match_registry(q, [cand], T), T)
        assert ev is not None and ev.outcome == "match"
        assert ev.hash_comparison is not None
        assert ev.hash_comparison.distance == 1
        assert ev.hash_comparison.differing_bits == [63]
        assert ev.hash_comparison.threshold_match == T.phash_match_max_dist
        assert ev.sha256_identical is False  # different bytes, same picture

    def test_exact_match_reports_identical_bytes(self) -> None:
        cand = _candidate(sha256="cc" * 32)
        q = QueryHashes(sha256="cc" * 32)
        ev = build_match_evidence(q, match_registry(q, [cand], T), T)
        assert ev is not None and ev.outcome == "match" and ev.sha256_identical

    def test_near_match_is_reported_as_near_not_match(self) -> None:
        cand = _candidate(phash64="0000000000000000")
        q = QueryHashes(sha256="bb" * 32, phash64="0000000000003fff")  # dist 14
        ev = build_match_evidence(q, match_registry(q, [cand], T), T)
        assert ev is not None and ev.outcome == "near"
        assert ev.hash_comparison is not None and ev.hash_comparison.distance == 14

    def test_miss_still_explains_the_closest_candidate(self) -> None:
        cand = _candidate(phash64="ffffffffffffffff")
        q = QueryHashes(sha256="bb" * 32, phash64="0000000000000000")  # dist 64
        m = match_registry(q, [cand], T)
        assert m.kind == "none"
        ev = build_match_evidence(q, m, T)
        assert ev is not None and ev.outcome == "miss"
        assert ev.hash_comparison is not None and ev.hash_comparison.distance == 64

    def test_video_match_reports_per_frame_distances(self) -> None:
        frames = ["00ff00ff00ff00ff", "ff00ff00ff00ff00", "0f0f0f0f0f0f0f0f"]
        cand = _candidate(video_frame_hashes=frames)
        q = QueryHashes(sha256="xx", video_frame_hashes=[frames[0], frames[1], "ffffffffffffffff"])
        ev = build_match_evidence(q, match_registry(q, [cand], T), T)
        assert ev is not None and ev.video_comparison is not None
        vc = ev.video_comparison
        assert vc.total_frames == 3 and vc.matched_frames == 2
        assert vc.frame_distances[0] == 0

    def test_nothing_to_explain_returns_none(self) -> None:
        q = QueryHashes(sha256="aa" * 32)
        assert build_match_evidence(q, match_registry(q, [], T), T) is None


class TestEvidenceDoesNotAffectDecisions:
    """The whole point: `closest` tracking is observability, not input."""

    CASES = [
        (QueryHashes(sha256="bb" * 32, phash64="00ff00ff00ff00fe"),
         [_candidate(phash64="00ff00ff00ff00ff")]),
        (QueryHashes(sha256="bb" * 32, phash64="0000000000003fff"),
         [_candidate(phash64="0000000000000000")]),
        (QueryHashes(sha256="bb" * 32, phash64="0000000000000000"),
         [_candidate(phash64="ffffffffffffffff")]),
        (QueryHashes(sha256="cc" * 32), [_candidate(sha256="cc" * 32)]),
    ]

    def test_verdict_identical_with_and_without_evidence(self) -> None:
        for q, candidates in self.CASES:
            m = match_registry(q, candidates, T)
            before = decide(DecisionInput(registry_match=m, query_sha256=q.sha256))
            build_match_evidence(q, m, T)  # must not mutate anything
            after = decide(DecisionInput(registry_match=m, query_sha256=q.sha256))
            assert before.verdict == after.verdict
            assert before.reasons == after.reasons

    def test_closest_never_populates_the_decision_candidate(self) -> None:
        """A miss carries a `closest` for display but must stay kind='none',
        so decide() can't mistake it for a match."""
        q = QueryHashes(sha256="bb" * 32, phash64="0000000000000000")
        m = match_registry(q, [_candidate(phash64="ffffffffffffffff")], T)
        assert m.kind == "none"
        assert m.candidate is None  # decide() reads this one
        assert m.closest is not None  # the UI reads this one
        d = decide(DecisionInput(registry_match=m))
        assert d.matched_communication_id is None
        assert d.matched_entity_id is None
