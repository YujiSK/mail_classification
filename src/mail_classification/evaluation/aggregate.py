"""CV mean/std/n_folds aggregation of Fold Long metric records."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev

METRICS_SUMMARY_FIELDS = ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"]


def build_metrics_summary(
    metrics_long: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Aggregate Fold Long rows to one row per (condition, model, metric)."""
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in metrics_long:
        key = (row["condition"], row["model"], row["metric"])
        grouped[key].append(row["value"])

    rows: list[dict[str, object]] = []
    for (condition, model, metric), values in sorted(grouped.items()):
        rows.append(
            {
                "condition": condition,
                "model": model,
                "metric": metric,
                "cv_mean": mean(values),
                "cv_std": pstdev(values) if len(values) > 1 else 0.0,
                "n_folds": len(values),
            }
        )
    return rows
