"""Deterministic descriptive quality statistics."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median, pstdev

from mail_classification.preprocessing import EnglishPreprocessor
from mail_classification.schemas import RawMailRecord


def _describe(values: list[int]) -> dict[str, float | int]:
    return {
        "mean": mean(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
        "std": pstdev(values),
    }


def build_quality_statistics(records: list[RawMailRecord]) -> dict[str, object]:
    if not records:
        raise ValueError("quality statistics require at least one record")
    preprocessor = EnglishPreprocessor()
    label_counts = Counter(record.label.value for record in records)
    difficulty_counts = Counter(record.difficulty.value for record in records)
    cross = Counter(
        (record.label.value, record.difficulty.value) for record in records
    )
    by_label: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"characters": [], "tokens": [], "lines": []}
    )
    for record in records:
        tokens = preprocessor.transform(record.raw_text).tokens
        by_label[record.label.value]["characters"].append(len(record.raw_text))
        by_label[record.label.value]["tokens"].append(len(tokens))
        by_label[record.label.value]["lines"].append(len(record.raw_text.splitlines()))

    length_statistics = {
        label: {
            metric: _describe(values)
            for metric, values in measurements.items()
        }
        for label, measurements in sorted(by_label.items())
    }
    total = len(records)
    template_groups = {record.template_group for record in records}
    variations = {(record.template_id, record.variation_id) for record in records}
    template_group_counts = Counter(record.template_group for record in records)
    class_urgency_counts = Counter(
        (
            record.label.value,
            str(record.metadata.get("component_indices", {}).get("urgency")),
        )
        for record in records
    )
    flag_counts = {
        flag: sum(bool(getattr(record, flag)) for record in records)
        for flag in ("has_header", "has_signature", "has_quoted_reply")
    }
    return {
        "total_count": total,
        "class_counts": dict(sorted(label_counts.items())),
        "class_ratios": {
            label: count / total for label, count in sorted(label_counts.items())
        },
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "class_difficulty_counts": {
            f"{label}|{difficulty}": count
            for (label, difficulty), count in sorted(cross.items())
        },
        "template_group_count": len(template_groups),
        "template_group_counts": dict(sorted(template_group_counts.items())),
        "template_groups_per_label": {
            label: len(
                {
                    record.template_group
                    for record in records
                    if record.label.value == label
                }
            )
            for label in sorted(label_counts)
        },
        "variation_count": len(variations),
        "variations_per_group": {
            group: len(
                {
                    record.variation_id
                    for record in records
                    if record.template_group == group
                }
            )
            for group in sorted(template_groups)
        },
        "length_statistics": length_statistics,
        "structure_counts": flag_counts,
        "class_urgency_counts": {
            f"{label}|{urgency}": count
            for (label, urgency), count in sorted(class_urgency_counts.items())
        },
        "structure_ratios": {
            key: value / total for key, value in flag_counts.items()
        },
        "negation_count": sum(
            bool(record.metadata.get("contains_negation")) for record in records
        ),
        "multi_intent_count": sum(
            bool(record.metadata.get("multi_intent")) for record in records
        ),
    }
