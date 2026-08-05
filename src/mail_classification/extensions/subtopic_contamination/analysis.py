"""OOF-derived contamination analysis: misclassifications, transitions, main x subtopic pairs.

Every function here is a pure join/aggregation over already-computed rows
(OOF predictions, the contamination assignment, and the original per-sample
metadata) -- nothing here fits a model or re-runs CV, so these functions are
safe to call both at run time (to write the required CSV artifacts) and
again at report-build time (reading the same CSVs back) without violating
project_rules.md's "report生成だけで実験を再実行しない".
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from mail_classification.schemas import RawMailRecord

from .assignment import CONTAMINATION_LEVELS

MISCLASSIFICATION_FIELDS = [
    "contamination_level",
    "condition",
    "model",
    "sample_id",
    "true_label",
    "predicted_label",
    "contaminated",
    "subtopic_label",
    "insertion_position",
    "style",
    "min_level",
    "difficulty",
    "multi_intent",
    "contains_negation",
    "pulled_to_subtopic",
]

TRANSITION_SUMMARY_FIELDS = [
    "baseline_level",
    "level",
    "condition",
    "model",
    "group",
    "correct_to_correct",
    "correct_to_incorrect",
    "incorrect_to_correct",
    "incorrect_to_incorrect",
    "n_samples",
]

MAIN_SUBTOPIC_PAIR_SUMMARY_FIELDS = [
    "level",
    "condition",
    "model",
    "main_label",
    "subtopic_label",
    "n_samples",
    "accuracy",
    "baseline_accuracy_c0",
    "accuracy_diff",
    "misclassified_count",
    "pulled_to_subtopic_count",
    "pulled_to_subtopic_rate",
]


def _assignment_by_sample(assignment_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {row["sample_id"]: row for row in assignment_rows}


def applies_at(assignment_row: dict[str, object], level: str) -> bool:
    """Dict-row equivalent of ``ContaminationAssignmentRow.applies_at`` for CSV-reloaded rows."""
    if level == "C0":
        return False
    return CONTAMINATION_LEVELS.index(level) >= CONTAMINATION_LEVELS.index(str(assignment_row["min_level"]))


def build_misclassification_rows(
    oof_rows: list[dict[str, object]],
    assignment_rows: list[dict[str, object]],
    original_records_by_id: dict[str, RawMailRecord],
) -> list[dict[str, object]]:
    assignment_by_id = _assignment_by_sample(assignment_rows)
    rows: list[dict[str, object]] = []
    for oof in oof_rows:
        if oof["true_label"] == oof["predicted_label"]:
            continue
        sample_id = oof["sample_id"]
        level = oof["contamination_level"]
        assignment_row = assignment_by_id.get(sample_id)
        contaminated = bool(assignment_row) and applies_at(assignment_row, level)
        subtopic_label = assignment_row["subtopic_label"] if contaminated else ""
        original = original_records_by_id[sample_id]
        rows.append(
            {
                "contamination_level": level,
                "condition": oof["condition"],
                "model": oof["model"],
                "sample_id": sample_id,
                "true_label": oof["true_label"],
                "predicted_label": oof["predicted_label"],
                "contaminated": contaminated,
                "subtopic_label": subtopic_label,
                "insertion_position": assignment_row["insertion_position"] if contaminated else "",
                "style": assignment_row["style"] if contaminated else "",
                "min_level": assignment_row["min_level"] if assignment_row else "",
                "difficulty": original.difficulty.value,
                "multi_intent": bool(original.metadata.get("multi_intent", False)),
                "contains_negation": bool(original.metadata.get("contains_negation", False)),
                "pulled_to_subtopic": bool(contaminated and oof["predicted_label"] == subtopic_label),
            }
        )
    return sorted(rows, key=lambda row: (row["contamination_level"], row["condition"], row["model"], row["sample_id"]))


def build_transition_summary(
    oof_rows: list[dict[str, object]],
    assignment_rows: list[dict[str, object]],
    *,
    baseline_level: str = "C0",
    compare_levels: tuple[str, ...] = ("C10", "C20", "C30"),
) -> list[dict[str, object]]:
    assignment_by_id = _assignment_by_sample(assignment_rows)
    index = {
        (row["contamination_level"], row["condition"], row["model"], row["sample_id"]): row
        for row in oof_rows
    }
    conditions_models = sorted({(row["condition"], row["model"]) for row in oof_rows})

    rows: list[dict[str, object]] = []
    for level in compare_levels:
        for condition, model in conditions_models:
            baseline_rows = [
                row
                for row in oof_rows
                if row["contamination_level"] == baseline_level
                and row["condition"] == condition
                and row["model"] == model
            ]
            groups: dict[str, list[tuple[dict, dict]]] = {"all": [], "contaminated": [], "not_contaminated": []}
            for baseline_row in baseline_rows:
                sample_id = baseline_row["sample_id"]
                compare_row = index.get((level, condition, model, sample_id))
                if compare_row is None:
                    raise ValueError(f"missing OOF pairing for sample {sample_id!r} at level {level!r}")
                assignment_row = assignment_by_id.get(sample_id)
                contaminated = bool(assignment_row) and applies_at(assignment_row, level)
                pair = (baseline_row, compare_row)
                groups["all"].append(pair)
                groups["contaminated" if contaminated else "not_contaminated"].append(pair)

            for group_name, pairs in groups.items():
                c2c = c2i = i2c = i2i = 0
                for baseline_row, compare_row in pairs:
                    baseline_correct = baseline_row["true_label"] == baseline_row["predicted_label"]
                    compare_correct = compare_row["true_label"] == compare_row["predicted_label"]
                    if baseline_correct and compare_correct:
                        c2c += 1
                    elif baseline_correct and not compare_correct:
                        c2i += 1
                    elif not baseline_correct and compare_correct:
                        i2c += 1
                    else:
                        i2i += 1
                rows.append(
                    {
                        "baseline_level": baseline_level,
                        "level": level,
                        "condition": condition,
                        "model": model,
                        "group": group_name,
                        "correct_to_correct": c2c,
                        "correct_to_incorrect": c2i,
                        "incorrect_to_correct": i2c,
                        "incorrect_to_incorrect": i2i,
                        "n_samples": len(pairs),
                    }
                )
    return rows


def build_main_subtopic_pair_summary(
    oof_rows: list[dict[str, object]],
    assignment_rows: list[dict[str, object]],
    *,
    baseline_level: str = "C0",
    compare_levels: tuple[str, ...] = ("C10", "C20", "C30"),
) -> list[dict[str, object]]:
    index = {
        (row["contamination_level"], row["condition"], row["model"], row["sample_id"]): row
        for row in oof_rows
    }
    conditions_models = sorted({(row["condition"], row["model"]) for row in oof_rows})

    rows: list[dict[str, object]] = []
    for level in compare_levels:
        pairs_to_samples: dict[tuple[str, str], list[str]] = defaultdict(list)
        for assignment_row in assignment_rows:
            if applies_at(assignment_row, level):
                key = (str(assignment_row["main_label"]), str(assignment_row["subtopic_label"]))
                pairs_to_samples[key].append(str(assignment_row["sample_id"]))

        for condition, model in conditions_models:
            for (main_label, subtopic_label), sample_ids in sorted(pairs_to_samples.items()):
                n = len(sample_ids)
                correct_at_level = correct_at_baseline = misclassified = pulled = 0
                for sample_id in sample_ids:
                    level_row = index[(level, condition, model, sample_id)]
                    baseline_row = index[(baseline_level, condition, model, sample_id)]
                    if level_row["true_label"] == level_row["predicted_label"]:
                        correct_at_level += 1
                    else:
                        misclassified += 1
                        if level_row["predicted_label"] == subtopic_label:
                            pulled += 1
                    if baseline_row["true_label"] == baseline_row["predicted_label"]:
                        correct_at_baseline += 1
                accuracy = correct_at_level / n if n else 0.0
                baseline_accuracy = correct_at_baseline / n if n else 0.0
                rows.append(
                    {
                        "level": level,
                        "condition": condition,
                        "model": model,
                        "main_label": main_label,
                        "subtopic_label": subtopic_label,
                        "n_samples": n,
                        "accuracy": accuracy,
                        "baseline_accuracy_c0": baseline_accuracy,
                        "accuracy_diff": accuracy - baseline_accuracy,
                        "misclassified_count": misclassified,
                        "pulled_to_subtopic_count": pulled,
                        "pulled_to_subtopic_rate": (pulled / misclassified) if misclassified else 0.0,
                    }
                )
    return rows


def accuracy_by_dimension(
    oof_rows: list[dict[str, object]],
    assignment_rows: list[dict[str, object]],
    original_records_by_id: dict[str, RawMailRecord],
    *,
    level: str,
    condition: str,
    model: str,
    dimension_fn: Callable[[RawMailRecord, dict[str, object] | None, bool], str],
) -> dict[str, tuple[float, int]]:
    """Report-time-only helper (not a saved artifact): accuracy grouped by an arbitrary dimension."""
    assignment_by_id = _assignment_by_sample(assignment_rows)
    buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in oof_rows:
        if row["contamination_level"] != level or row["condition"] != condition or row["model"] != model:
            continue
        sample_id = row["sample_id"]
        assignment_row = assignment_by_id.get(sample_id)
        contaminated = bool(assignment_row) and applies_at(assignment_row, level)
        original = original_records_by_id[sample_id]
        value = dimension_fn(original, assignment_row, contaminated)
        bucket = buckets[value]
        bucket[1] += 1
        if row["true_label"] == row["predicted_label"]:
            bucket[0] += 1
    return {value: (correct / total if total else 0.0, total) for value, (correct, total) in buckets.items()}
