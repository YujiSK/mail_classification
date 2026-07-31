"""MinHashLSH near-duplicate sensitivity analysis (Phase 6 Extension, optional).

Rabiloo's onboarding material and docs/contracts/data_quality_contract.md
both name MinHashLSH near-duplicate detection as explicitly out of Core's
scope ("Phase 2 does not implement MinHash, edit-distance clustering,
embeddings, or semantic near duplicates."). This module answers the
sensitivity question Core intentionally left open: does a fuzzier,
similarity-based near-duplicate check surface anything Core's exact/
normalized-only checks (mail_classification.quality.duplicates) miss?

Deliberately separate from Core: its own module, own output directory
(outputs/extensions/, never outputs/data_quality/ or outputs/runs/), and no
third-party dependency (a from-scratch permutation MinHash signature plus
banding-based LSH, stdlib hashlib only) so this Extension carries no new
Core/Extension dependency risk (project_rules.md: don't mix Core and
Extension dependencies/config/output).

Approved 2026-07-31 by User (Yuji Sunagawa): MinHashLSH only; a BERT
comparison Extension was considered and explicitly declined after a real
torch resolution attempt timed out at 60s (large wheel, unverified Python
3.14 compatibility), confirming the "heavy dependency/download" risk named
in docs/management/execution_plan.md Phase 6 Main risks.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib

from mail_classification.preprocessing import EnglishPreprocessor
from mail_classification.schemas import RawMailRecord

DEFAULT_SHINGLE_SIZE = 3
DEFAULT_NUM_PERM = 64
DEFAULT_BANDS = 16
DEFAULT_THRESHOLD = 0.5
DEFAULT_SEED = 42

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


def word_shingles(text: str, k: int = DEFAULT_SHINGLE_SIZE) -> frozenset[str]:
    """Contiguous k-word shingles of already-lowercased/normalized text."""
    words = text.split()
    if len(words) < k:
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(" ".join(words[i : i + k]) for i in range(len(words) - k + 1))


def _hash_shingle(shingle: str, salt: int, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{salt}:{shingle}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def minhash_signature(
    shingles: frozenset[str], *, num_perm: int = DEFAULT_NUM_PERM, seed: int = DEFAULT_SEED
) -> tuple[int, ...]:
    """A deterministic num_perm-length MinHash signature for one document's shingles."""
    if not shingles:
        return tuple(0 for _ in range(num_perm))
    return tuple(
        min(_hash_shingle(shingle, salt, seed) for shingle in shingles)
        for salt in range(num_perm)
    )


def lsh_candidate_pairs(
    signatures: dict[str, tuple[int, ...]], *, bands: int = DEFAULT_BANDS
) -> set[tuple[str, str]]:
    """Candidate near-duplicate pairs: documents sharing a band's signature slice."""
    if not signatures:
        return set()
    num_perm = len(next(iter(signatures.values())))
    if num_perm % bands != 0:
        raise ValueError("num_perm must be divisible by bands")
    rows_per_band = num_perm // bands

    candidates: set[tuple[str, str]] = set()
    for band_index in range(bands):
        start = band_index * rows_per_band
        end = start + rows_per_band
        buckets: dict[tuple[int, ...], list[str]] = defaultdict(list)
        for sample_id, signature in signatures.items():
            buckets[signature[start:end]].append(sample_id)
        for bucket_ids in buckets.values():
            if len(bucket_ids) < 2:
                continue
            for i in range(len(bucket_ids)):
                for j in range(i + 1, len(bucket_ids)):
                    candidates.add(tuple(sorted((bucket_ids[i], bucket_ids[j]))))
    return candidates


def exact_jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Exact Jaccard similarity, computed directly from the shingle sets (not estimated)."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def find_near_duplicates(
    records: list[RawMailRecord],
    *,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
    num_perm: int = DEFAULT_NUM_PERM,
    bands: int = DEFAULT_BANDS,
    threshold: float = DEFAULT_THRESHOLD,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, object]]:
    """MinHashLSH candidate generation, then exact-Jaccard confirmation above threshold.

    Cross-references each pair against Core's own exact/normalized duplicate
    definitions (byte-equal raw_text/body_text, or equal EnglishPreprocessor
    clean_text) so the output distinguishes what Core's checks would already
    catch from what only this fuzzier method finds.
    """
    if not records:
        raise ValueError("near-duplicate analysis requires at least one record")

    preprocessor = EnglishPreprocessor()
    shingles_by_id = {
        record.id: word_shingles(record.body_text.casefold(), shingle_size)
        for record in records
    }
    signatures = {
        sample_id: minhash_signature(shingles, num_perm=num_perm, seed=seed)
        for sample_id, shingles in shingles_by_id.items()
    }
    candidate_pairs = lsh_candidate_pairs(signatures, bands=bands)

    records_by_id = {record.id: record for record in records}
    normalized_by_id = {
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
                    normalized_by_id[sample_id_a] == normalized_by_id[sample_id_b]
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
