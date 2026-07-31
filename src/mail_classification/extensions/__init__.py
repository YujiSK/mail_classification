"""Optional Phase 6 Extensions. Never imported by Core code; Core never depends on this."""

from .minhash import (
    NEAR_DUPLICATE_FIELDS,
    exact_jaccard,
    find_near_duplicates,
    lsh_candidate_pairs,
    minhash_signature,
    summarize_near_duplicates,
    word_shingles,
)
from .runner import run_and_write_minhash_extension

__all__ = [
    "NEAR_DUPLICATE_FIELDS",
    "exact_jaccard",
    "find_near_duplicates",
    "lsh_candidate_pairs",
    "minhash_signature",
    "run_and_write_minhash_extension",
    "summarize_near_duplicates",
    "word_shingles",
]
