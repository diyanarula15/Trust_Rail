"""Content hashing (spec §8.2): sha256, perceptual, SimHash64.

pdqhash is OPTIONAL — absence must not break anything.
"""
import hashlib
import io
import re
import unicodedata

import imagehash
from PIL import Image

try:  # optional PDQ-256
    import pdqhash  # type: ignore[import-not-found]

    HAS_PDQ = True
except ImportError:
    pdqhash = None
    HAS_PDQ = False

_ZERO_WIDTH = re.compile(r"[​‌‍⁠﻿]")
_WS = re.compile(r"\s+")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def phash64_hex(image_bytes: bytes) -> str:
    """64-bit perceptual hash of an image, as 16 hex chars."""
    with Image.open(io.BytesIO(image_bytes)) as im:
        return str(imagehash.phash(im.convert("RGB")))


def pdq256_hex(image_bytes: bytes) -> str | None:
    if not HAS_PDQ:
        return None
    try:
        import numpy as np

        with Image.open(io.BytesIO(image_bytes)) as im:
            vec, _quality = pdqhash.compute(np.asarray(im.convert("RGB")))
        bits = "".join("1" if b else "0" for b in vec)
        return f"{int(bits, 2):064x}"
    except Exception:
        return None


def hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex digests."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def differing_bit_indices(a: str, b: str) -> list[int]:
    """Which bit positions differ, MSB-first (index 0 = most significant).

    Same ordering as `bin(int(h, 16))[2:].zfill(n)`, which for a phash64 is
    imagehash's flattened 8x8 DCT-sign array in row-major order — so index i
    is grid cell (i // 8, i % 8). Used only to explain a match, never to
    decide one.
    """
    n = len(a) * 4
    x = int(a, 16) ^ int(b, 16)
    return [i for i in range(n) if (x >> (n - 1 - i)) & 1]


def normalize_text(text: str) -> str:
    """NFKC, strip zero-width + emoji/symbols, lowercase, collapse whitespace
    (spec §8.2; §16.1 requires stability under emoji injection)."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = "".join(c for c in text if unicodedata.category(c) not in ("So", "Sk", "Co", "Cs"))
    return _WS.sub(" ", text.lower()).strip()


def simhash64_hex(text: str) -> str:
    """SimHash64 over token 3-grams of normalized text. Own implementation —
    no flaky dependency (spec §8.2)."""
    tokens = normalize_text(text).split(" ")
    if not tokens or tokens == [""]:
        return f"{0:016x}"
    grams = (
        [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
        if len(tokens) >= 3
        else [" ".join(tokens)]
    )
    acc = [0] * 64
    for gram in grams:
        h = int.from_bytes(hashlib.sha256(gram.encode()).digest()[:8], "big")
        for bit in range(64):
            acc[bit] += 1 if (h >> bit) & 1 else -1
    value = sum(1 << bit for bit in range(64) if acc[bit] > 0)
    return f"{value:016x}"


_NUMERIC = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numeric_tokens(text: str) -> set[str]:
    """Every number in the text, comma-separators removed.

    SimHash is deliberately tolerant, and on a long document that tolerance
    is dangerous: a filing is ~150 token-trigrams, so altering one figure
    moves the fingerprint by about 2 bits against a match threshold of 6 —
    a doctored financial statement passed as genuine. Numbers are the one
    thing forwarding never changes and tampering always does, so they get
    compared exactly rather than fuzzily.
    """
    return {m.group(0).replace(",", "") for m in _NUMERIC.finditer(text or "")}


def video_match_ratio(query_frames: list[str], registered_frames: list[str], max_dist: int) -> float:
    """Fraction of query frame hashes matching ANY registered frame hash
    within max_dist (spec §8.3 VIDEO_FRAME_MATCH_RATIO semantics)."""
    if not query_frames or not registered_frames:
        return 0.0
    hits = sum(
        1
        for q in query_frames
        if any(hamming_hex(q, r) <= max_dist for r in registered_frames)
    )
    return hits / len(query_frames)


def video_frame_distances(query_frames: list[str], registered_frames: list[str]) -> list[int]:
    """Per query frame, the closest distance to ANY registered frame.

    The per-frame view behind `video_match_ratio`'s single number — same
    comparison, kept separate so the ratio used for the verdict stays the
    one tested in Epic 4.
    """
    if not query_frames or not registered_frames:
        return []
    return [min(hamming_hex(q, r) for r in registered_frames) for q in query_frames]
