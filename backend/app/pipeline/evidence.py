"""Match evidence: how the registry stage reached its answer, in a form the
UI can draw.

Everything here is derived from comparisons `match_registry` has already
made. It explains a decision and never influences one: `decide()` has
already returned by the time this runs, and nothing in this module is read
back into the pipeline. Keeping it separate is what lets the §20 guardrail
stay a statement about the verdict engine alone.

The one non-obvious bit: a phash64 is a flattened 8x8 grid of DCT-sign
bits, so `differing_bits` indices map to grid cells (i // 8, i % 8). The
frontend draws that grid directly — it isn't a visualisation of the hash,
it *is* the hash.
"""
from typing import Literal

from pydantic import BaseModel

from app.pipeline.hashing import differing_bit_indices, video_frame_distances
from app.pipeline.verdict import Candidate, MatchThresholds, QueryHashes, RegistryMatch

Algorithm = Literal["phash64", "pdq256", "simhash64"]

_KIND_TO_ALGORITHM: dict[str, Algorithm] = {
    "phash": "phash64",
    "pdq": "pdq256",
    "simhash": "simhash64",
    "near": "phash64",  # the near band is only ever produced by phash
}

_ALGORITHM_BITS: dict[Algorithm, int] = {"phash64": 64, "pdq256": 256, "simhash64": 64}


class HashComparison(BaseModel):
    """Two fingerprints of the same width, and exactly how they differ."""

    algorithm: Algorithm
    bits: int
    query_hex: str
    registered_hex: str
    distance: int
    differing_bits: list[int]
    threshold_match: int
    threshold_near: int | None = None


class VideoComparison(BaseModel):
    """Per-frame view of the ratio that decided a video match."""

    frame_distances: list[int]  # per query frame, closest registered frame
    frame_max_distance: int  # a frame counts as matched at or below this
    matched_frames: int
    total_frames: int
    ratio: float
    threshold_ratio: float


ContentKind = Literal["image", "text", "video", "document"]

# What the reader is actually looking at, which decides how the comparison
# gets described. Explaining a forwarded SMS in terms of "the picture" is
# nonsense, so the copy is chosen per kind rather than written once for
# images and reused everywhere.
_INPUT_KIND_TO_CONTENT: dict[str, ContentKind] = {
    "image": "image",
    "video": "video",
    "pdf": "document",
    "eml": "text",
    "text": "text",
    "url": "text",
}


def content_kind_for(input_kind: str) -> ContentKind:
    return _INPUT_KIND_TO_CONTENT.get(input_kind, "text")


class MatchEvidence(BaseModel):
    outcome: Literal["match", "near", "miss"]
    kind: str  # the RegistryMatch kind that produced it
    content_kind: ContentKind = "image"
    # For text/document matches: the wording the issuer actually published,
    # so the panel can show it side by side the way images are shown.
    registered_text: str | None = None
    query_sha256: str | None = None
    registered_sha256: str | None = None
    sha256_identical: bool = False
    hash_comparison: HashComparison | None = None
    video_comparison: VideoComparison | None = None
    registered_communication_id: str | None = None


def _hex_for(algorithm: Algorithm, q: QueryHashes) -> str | None:
    return {"phash64": q.phash64, "pdq256": q.pdq256, "simhash64": q.simhash64}[algorithm]


def _candidate_hex_for(algorithm: Algorithm, c: Candidate) -> str | None:
    return {"phash64": c.phash64, "pdq256": c.pdq256, "simhash64": c.simhash64}[algorithm]


def _threshold_for(algorithm: Algorithm, t: MatchThresholds) -> tuple[int, int | None]:
    if algorithm == "phash64":
        return t.phash_match_max_dist, t.phash_near_max_dist
    if algorithm == "pdq256":
        return t.pdq_match_max_dist, None
    return t.simhash_match_max_dist, None


def _compare(algorithm: Algorithm, q: QueryHashes, c: Candidate, t: MatchThresholds
             ) -> HashComparison | None:
    query_hex = _hex_for(algorithm, q)
    registered_hex = _candidate_hex_for(algorithm, c)
    if not query_hex or not registered_hex or len(query_hex) != len(registered_hex):
        return None
    differing = differing_bit_indices(query_hex, registered_hex)
    threshold_match, threshold_near = _threshold_for(algorithm, t)
    return HashComparison(
        algorithm=algorithm,
        bits=_ALGORITHM_BITS[algorithm],
        query_hex=query_hex,
        registered_hex=registered_hex,
        distance=len(differing),
        differing_bits=differing,
        threshold_match=threshold_match,
        threshold_near=threshold_near,
    )


def _video(q: QueryHashes, c: Candidate, t: MatchThresholds) -> VideoComparison | None:
    if not q.video_frame_hashes or not c.video_frame_hashes:
        return None
    distances = video_frame_distances(q.video_frame_hashes, c.video_frame_hashes)
    if not distances:
        return None
    matched = sum(1 for d in distances if d <= t.phash_match_max_dist)
    return VideoComparison(
        frame_distances=distances,
        frame_max_distance=t.phash_match_max_dist,
        matched_frames=matched,
        total_frames=len(distances),
        ratio=matched / len(distances),
        threshold_ratio=t.video_frame_match_ratio,
    )


def build_match_evidence(
    q: QueryHashes, m: RegistryMatch, t: MatchThresholds, input_kind: str = "image"
) -> MatchEvidence | None:
    """Explain `m`. Returns None when there is nothing to show — a text-only
    submission that never reached a hash comparison, say."""
    ck = content_kind_for(input_kind)
    if m.kind == "exact" and m.candidate is not None:
        return MatchEvidence(
            content_kind=ck,
            outcome="match",
            kind=m.kind,
            query_sha256=q.sha256,
            registered_sha256=m.candidate.sha256,
            sha256_identical=True,
            registered_communication_id=str(m.candidate.communication_id),
        )

    if m.kind == "video" and m.candidate is not None:
        return MatchEvidence(
            content_kind=ck,
            outcome="match",
            kind=m.kind,
            query_sha256=q.sha256,
            registered_sha256=m.candidate.sha256,
            sha256_identical=bool(q.sha256 and q.sha256 == m.candidate.sha256),
            video_comparison=_video(q, m.candidate, t),
            registered_communication_id=str(m.candidate.communication_id),
        )

    # match / near: the candidate that produced the result explains it
    if m.candidate is not None and m.kind in _KIND_TO_ALGORITHM:
        comparison = _compare(_KIND_TO_ALGORITHM[m.kind], q, m.candidate, t)
        if comparison is None:
            return None
        return MatchEvidence(
            content_kind=ck,
            outcome="near" if m.kind == "near" else "match",
            kind=m.kind,
            query_sha256=q.sha256,
            registered_sha256=m.candidate.sha256,
            sha256_identical=bool(q.sha256 and q.sha256 == m.candidate.sha256),
            hash_comparison=comparison,
            registered_communication_id=str(m.candidate.communication_id),
        )

    # miss: still worth showing how far off the closest registered item was
    if m.closest is not None:
        video = _video(q, m.closest, t) if m.closest_video_ratio is not None else None
        comparison = None
        if m.closest_algorithm in _ALGORITHM_BITS:
            comparison = _compare(m.closest_algorithm, q, m.closest, t)  # type: ignore[arg-type]
        if comparison is None and video is None:
            return None
        return MatchEvidence(
            content_kind=ck,
            outcome="miss",
            kind=m.kind,
            query_sha256=q.sha256,
            registered_sha256=m.closest.sha256,
            sha256_identical=False,
            hash_comparison=comparison,
            video_comparison=video,
            registered_communication_id=str(m.closest.communication_id),
        )

    return None
