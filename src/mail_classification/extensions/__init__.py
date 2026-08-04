"""Optional Phase 6 Extensions. Never imported by Core code; Core never depends on this."""

from .ja_minhash import (
    NEAR_DUPLICATE_FIELDS as NEAR_DUPLICATE_FIELDS_JA,
    char_shingles,
    find_near_duplicates_ja,
    summarize_near_duplicates as summarize_near_duplicates_ja,
)
from .ja_runner import run_and_write_minhash_extension_ja
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
    "NEAR_DUPLICATE_FIELDS_JA",
    "char_shingles",
    "exact_jaccard",
    "find_near_duplicates",
    "find_near_duplicates_ja",
    "lsh_candidate_pairs",
    "minhash_signature",
    "run_and_write_minhash_extension",
    "run_and_write_minhash_extension_ja",
    "summarize_near_duplicates",
    "summarize_near_duplicates_ja",
    "word_shingles",
]
