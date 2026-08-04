"""Japanese counterpart of ``minhash.py``: character shingles, not word shingles.

``word_shingles`` splits on whitespace, which is meaningless for
unsegmented Japanese running text (no inter-word spaces), so a Japanese
near-duplicate check needs character shingles instead, per explicit
instruction ("日本語では文字shingleを使用してください"). The generic
signature/LSH/Jaccard machinery (``minhash_signature``, ``lsh_candidate_pairs``,
``exact_jaccard``) is reused unmodified from ``minhash.py`` by import: none
of it assumes word-level shingles, only that shingles are hashable strings.
Only shingle extraction and the normalized-duplicate cross-check (which
needs ``JapanesePreprocessor`` instead of ``EnglishPreprocessor``) are
Japanese-specific, so those are the only two forked pieces.
"""

from __future__ import annotations

from mail_classification.preprocessing import (
    JapaneseCleaningConfig,
    JapanesePreprocessingConfig,
    JapanesePreprocessor,
    JapaneseSegmentationConfig,
)
from mail_classification.schemas import RawMailRecord

from .minhash import (
    DEFAULT_BANDS,
    DEFAULT_NUM_PERM,
    DEFAULT_SEED,
    DEFAULT_THRESHOLD,
    exact_jaccard,
    lsh_candidate_pairs,
    minhash_signature,
)

DEFAULT_CHAR_SHINGLE_SIZE = 5

NEAR_DUPLICATE_FIELDS = [
    "sample_id_a",
    "sample_id_b",
    "label_a",
    "label_b",
    "template_group_a",
    "template_group_b",
    "same_label",
    "same_template_group",
    "jaccard_similarity",
    "exact_raw_duplicate",
    "exact_body_duplicate",
    "normalized_duplicate",
]

# Light normalization only (NFKC/neologdn/whitespace/lowercase), no
# header/signature/quoted-reply removal and no segmentation: shingles
# should reflect the same "as-authored" content JC's character n-gram
# Core condition sees, not a heavily cleaned variant.
_LIGHT_CONFIG = JapanesePreprocessingConfig(
    cleaning=JapaneseCleaningConfig(
        remove_headers=False,
        remove_signatures=False,
        remove_quoted_reply=False,
        replace_urls=False,
        replace_emails=False,
    ),
    segmentation=JapaneseSegmentationConfig(enabled=False),
)


def char_shingles(text: str, k: int = DEFAULT_CHAR_SHINGLE_SIZE) -> frozenset[str]:
    """Contiguous k-character shingles of already-normalized text."""
    if len(text) < k:
        return frozenset({text}) if text else frozenset()
    return frozenset(text[i : i + k] for i in range(len(text) - k + 1))


def find_near_duplicates_ja(
    records: list[RawMailRecord],
    *,
    shingle_size: int = DEFAULT_CHAR_SHINGLE_SIZE,
    num_perm: int = DEFAULT_NUM_PERM,
    bands: int = DEFAULT_BANDS,
    threshold: float = DEFAULT_THRESHOLD,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, object]]:
    """MinHashLSH candidate generation (character shingles), then exact-Jaccard confirmation.

    Cross-references each pair against Core's own exact/normalized
    duplicate definitions (byte-equal raw_text/body_text, or equal
    JapanesePreprocessor clean_text) so the output distinguishes what
    Core's checks would already catch from what only this fuzzier method
    finds.
    """
    if not records:
        raise ValueError("near-duplicate analysis requires at least one record")

    preprocessor = JapanesePreprocessor(_LIGHT_CONFIG)
    normalized_by_id = {
        record.id: preprocessor.transform(record.body_text).clean_text
        for record in records
    }
    shingles_by_id = {
        sample_id: char_shingles(text, shingle_size)
        for sample_id, text in normalized_by_id.items()
    }
    signatures = {
        sample_id: minhash_signature(shingles, num_perm=num_perm, seed=seed)
        for sample_id, shingles in shingles_by_id.items()
    }
    candidate_pairs = lsh_candidate_pairs(signatures, bands=bands)

    records_by_id = {record.id: record for record in records}
    raw_normalized_by_id = {
        record.id: preprocessor.transform(record.raw_text).clean_text for record in records
    }

    rows: list[dict[str, object]] = []
    for sample_id_a, sample_id_b in candidate_pairs:
        similarity = exact_jaccard(shingles_by_id[sample_id_a], shingles_by_id[sample_id_b])
        if similarity < threshold:
            continue
        record_a, record_b = records_by_id[sample_id_a], records_by_id[sample_id_b]
        rows.append(
            {
                "sample_id_a": sample_id_a,
                "sample_id_b": sample_id_b,
                "label_a": record_a.label.value,
                "label_b": record_b.label.value,
                "template_group_a": record_a.template_group,
                "template_group_b": record_b.template_group,
                "same_label": record_a.label == record_b.label,
                "same_template_group": record_a.template_group == record_b.template_group,
                "jaccard_similarity": similarity,
                "exact_raw_duplicate": record_a.raw_text == record_b.raw_text,
                "exact_body_duplicate": record_a.body_text == record_b.body_text,
                "normalized_duplicate": (
                    raw_normalized_by_id[sample_id_a] == raw_normalized_by_id[sample_id_b]
                ),
            }
        )
    rows.sort(key=lambda row: (-row["jaccard_similarity"], row["sample_id_a"], row["sample_id_b"]))
    return rows


def summarize_near_duplicates(rows: list[dict[str, object]]) -> dict[str, object]:
    """The sensitivity question: what did MinHashLSH find beyond Core's own checks?"""
    additional_beyond_core = [
        row
        for row in rows
        if not row["exact_raw_duplicate"]
        and not row["exact_body_duplicate"]
        and not row["normalized_duplicate"]
    ]
    cross_label = [row for row in rows if not row["same_label"]]
    return {
        "total_candidate_pairs": len(rows),
        "additional_beyond_core_exact_normalized": len(additional_beyond_core),
        "cross_label_pairs": len(cross_label),
        "same_template_group_pairs": sum(1 for row in rows if row["same_template_group"]),
        "different_template_group_pairs": sum(
            1 for row in rows if not row["same_template_group"]
        ),
    }
