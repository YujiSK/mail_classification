"""Per-condition quality/leakage audits for the contamination datasets.

Reuses Core's own duplicate/statistics checks (``quality.duplicates``,
``quality.statistics``) and the Phase 6 MinHashLSH Extension
(``extensions.minhash``) for cross-label near-duplicate sensitivity, rather
than re-implementing any of them -- this Extension only adds the
contamination-specific counts (rate, main/subtopic pairs, insertion
position, sentence usage) those existing modules do not know about.
"""

from __future__ import annotations

from collections import Counter

from mail_classification.quality.duplicates import find_duplicates
from mail_classification.quality.statistics import build_quality_statistics
from mail_classification.schemas import RawMailRecord

from .assignment import ContaminationAssignmentRow
from .minhash_audit import cross_label_near_duplicate_summary

CONDITION_STATISTICS_FIELDS = ["level", "category", "key", "value"]
REVIEW_SAMPLE_FIELDS = [
    "sample_id",
    "main_label",
    "subtopic_label",
    "style",
    "insertion_position",
    "min_level",
    "difficulty",
    "original_multi_intent",
    "flag_reason",
    "contaminated_body_text",
]


def _rows(level: str, category: str, mapping: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"level": level, "category": category, "key": str(key), "value": value}
        for key, value in sorted(mapping.items(), key=lambda item: str(item[0]))
    ]


def build_condition_statistics(
    level: str,
    records: list[RawMailRecord],
    assignment: list[ContaminationAssignmentRow],
) -> list[dict[str, object]]:
    """One condition's full audit: counts, balance, duplicates, near-duplicates."""
    rows: list[dict[str, object]] = []

    stats = build_quality_statistics(records)
    rows.extend(_rows(level, "total_count", {"total_count": stats["total_count"]}))
    rows.extend(_rows(level, "class_counts", stats["class_counts"]))
    rows.extend(_rows(level, "difficulty_counts", stats["difficulty_counts"]))
    rows.extend(_rows(level, "template_group_counts", stats["template_group_counts"]))

    duplicates = find_duplicates(records)
    exact_count = sum(1 for row in duplicates if row["match_type"] == "exact")
    normalized_count = sum(1 for row in duplicates if row["match_type"] == "normalized")
    rows.extend(
        _rows(
            level,
            "duplicates",
            {"exact_group_count": exact_count, "normalized_group_count": normalized_count},
        )
    )

    near_duplicate_summary = cross_label_near_duplicate_summary(records)
    rows.extend(_rows(level, "near_duplicates", near_duplicate_summary))

    applicable = [row for row in assignment if row.applies_at(level)]
    rows.extend(
        _rows(
            level,
            "contamination_rate",
            {
                "contaminated_count": len(applicable),
                "contaminated_ratio": len(applicable) / len(records) if records else 0.0,
            },
        )
    )

    pair_counts = Counter((row.main_label, row.subtopic_label) for row in applicable)
    rows.extend(
        _rows(
            level,
            "main_subtopic_pairs",
            {f"{main}|{subtopic}": count for (main, subtopic), count in pair_counts.items()},
        )
    )

    position_counts = Counter(row.insertion_position for row in applicable)
    rows.extend(_rows(level, "insertion_position", dict(position_counts)))

    sentence_usage = Counter((row.subtopic_label, row.variant_id) for row in applicable)
    rows.extend(
        _rows(
            level,
            "sentence_usage",
            {f"{subtopic}|variant{variant_id}": count for (subtopic, variant_id), count in sentence_usage.items()},
        )
    )

    style_counts = Counter(row.style for row in applicable)
    rows.extend(_rows(level, "style_usage", dict(style_counts)))

    return rows


def audit_sentence_usage_skew(
    assignment: list[ContaminationAssignmentRow], level: str, *, max_deviation_ratio: float = 2.5
) -> list[dict[str, object]]:
    """Flag any single sentence variant used far more than the per-subtopic average at `level`."""
    applicable = [row for row in assignment if row.applies_at(level)]
    usage: Counter[tuple[str, int]] = Counter((row.subtopic_label, row.variant_id) for row in applicable)
    subtopic_totals: Counter[str] = Counter(row.subtopic_label for row in applicable)

    findings: list[dict[str, object]] = []
    for (subtopic, variant_id), count in usage.items():
        total = subtopic_totals[subtopic]
        expected = total / 12  # SENTENCES_PER_SUBTOPIC
        if expected > 0 and count > expected * max_deviation_ratio:
            findings.append(
                {
                    "level": level,
                    "subtopic_label": subtopic,
                    "variant_id": variant_id,
                    "count": count,
                    "expected": expected,
                    "deviation_ratio": count / expected,
                }
            )
    return sorted(findings, key=lambda item: (item["level"], item["subtopic_label"], item["variant_id"]))


def build_review_samples(
    assignment: list[ContaminationAssignmentRow],
    contaminated_records_by_id: dict[str, RawMailRecord],
    original_records_by_id: dict[str, RawMailRecord],
) -> list[dict[str, object]]:
    """Automatic screening for samples whose primary intent may have become unclear.

    Heuristic only (no manual review was performed in this automated Extension
    run): flags samples whose subtopic sentence style does not explicitly
    de-prioritize the subtopic (``fact``/``concise``) on already-ambiguous
    base emails (``difficulty`` hard/ambiguous), and samples whose original
    email already carried a second intent (``multi_intent``) before
    contamination was added.
    """
    rows: list[dict[str, object]] = []
    for row in assignment:
        original = original_records_by_id[row.sample_id]
        multi_intent = bool(original.metadata.get("multi_intent", False))
        reasons = []
        if row.style in ("fact", "concise") and row.difficulty in ("hard", "ambiguous"):
            reasons.append("non_deprioritizing_style_on_ambiguous_base")
        if multi_intent:
            reasons.append("original_already_multi_intent")
        if not reasons:
            continue
        contaminated = contaminated_records_by_id[row.sample_id]
        rows.append(
            {
                "sample_id": row.sample_id,
                "main_label": row.main_label,
                "subtopic_label": row.subtopic_label,
                "style": row.style,
                "insertion_position": row.insertion_position,
                "min_level": row.min_level,
                "difficulty": row.difficulty,
                "original_multi_intent": multi_intent,
                "flag_reason": "|".join(reasons),
                "contaminated_body_text": contaminated.body_text,
            }
        )
    return sorted(rows, key=lambda item: item["sample_id"])
