"""contamination_level-tagged wrappers around Core's metric builders (no reimplementation)."""

from __future__ import annotations

from mail_classification.evaluation.aggregate import METRICS_SUMMARY_FIELDS as _CORE_SUMMARY_FIELDS
from mail_classification.evaluation.aggregate import build_metrics_summary as _core_build_metrics_summary
from mail_classification.evaluation.cv import FoldFitResult
from mail_classification.evaluation.metrics import CONFUSION_FIELDS as _CORE_CONFUSION_FIELDS
from mail_classification.evaluation.metrics import METRICS_LONG_FIELDS as _CORE_METRICS_LONG_FIELDS
from mail_classification.evaluation.metrics import build_confusion_matrix_rows as _core_build_confusion_matrix_rows
from mail_classification.evaluation.metrics import build_metrics_long as _core_build_metrics_long

METRICS_LONG_FIELDS = ["contamination_level", *_CORE_METRICS_LONG_FIELDS]
CONFUSION_FIELDS = ["contamination_level", *_CORE_CONFUSION_FIELDS]
METRICS_SUMMARY_FIELDS = ["contamination_level", *_CORE_SUMMARY_FIELDS]
OOF_FIELDS = [
    "contamination_level",
    "sample_id",
    "condition",
    "model",
    "fold_id",
    "true_label",
    "predicted_label",
]


def build_metrics_long_by_level(
    fold_results_by_level: dict[str, list[FoldFitResult]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for level, fold_results in fold_results_by_level.items():
        for row in _core_build_metrics_long(fold_results):
            rows.append({"contamination_level": level, **row})
    return rows


def build_confusion_matrix_rows_by_level(
    fold_results_by_level: dict[str, list[FoldFitResult]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for level, fold_results in fold_results_by_level.items():
        for row in _core_build_confusion_matrix_rows(fold_results):
            rows.append({"contamination_level": level, **row})
    return rows


def build_oof_rows_by_level(
    fold_results_by_level: dict[str, list[FoldFitResult]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for level, fold_results in fold_results_by_level.items():
        for result in fold_results:
            for oof in result.oof_rows:
                rows.append(
                    {
                        "contamination_level": level,
                        "sample_id": oof["sample_id"],
                        "condition": result.condition,
                        "model": result.model,
                        "fold_id": result.fold_id,
                        "true_label": oof["true_label"],
                        "predicted_label": oof["predicted_label"],
                    }
                )
    return rows


def build_metrics_summary_by_level(
    metrics_long_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Per-level CV mean/std, delegating the actual aggregation to Core's ``aggregate`` module."""
    levels = sorted({row["contamination_level"] for row in metrics_long_rows})
    rows: list[dict[str, object]] = []
    for level in levels:
        filtered = [row for row in metrics_long_rows if row["contamination_level"] == level]
        for row in _core_build_metrics_summary(filtered):
            rows.append({"contamination_level": level, **row})
    return rows
