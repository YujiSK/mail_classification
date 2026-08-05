"""Fold-level paired differences of every contamination level against C0.

Same shape as ``mail_classification.evaluation.paired`` but keyed by
(contamination_level, condition, model, metric) instead of (condition,
model, metric): the baseline here is a *level* (C0), held fixed across four
(condition, model) cells, rather than a single Core condition.
"""

from __future__ import annotations

from statistics import mean, pstdev

PAIRED_DIFFERENCE_FIELDS = [
    "baseline_level",
    "level",
    "condition",
    "model",
    "metric",
    "mean_diff",
    "std_diff",
    "n_improved",
    "n_worsened",
    "n_folds",
]


def build_paired_differences_vs_c0(
    metrics_long_rows: list[dict[str, object]], *, baseline_level: str = "C0"
) -> list[dict[str, object]]:
    by_key: dict[tuple[str, str, str, str, int], float] = {
        (
            row["contamination_level"],
            row["condition"],
            row["model"],
            row["metric"],
            row["fold_id"],
        ): row["value"]
        for row in metrics_long_rows
    }
    levels = sorted({row["contamination_level"] for row in metrics_long_rows} - {baseline_level})
    # Actual (condition, model) cells present, not the full cartesian product:
    # the Extension only runs 4 of the 6 possible Core (condition, model) pairs.
    condition_models = sorted({(row["condition"], row["model"]) for row in metrics_long_rows})
    metrics = sorted({row["metric"] for row in metrics_long_rows})
    fold_ids = sorted({row["fold_id"] for row in metrics_long_rows})

    rows: list[dict[str, object]] = []
    for level in levels:
        for condition, model in condition_models:
            for metric in metrics:
                diffs: list[float] = []
                for fold_id in fold_ids:
                    baseline_key = (baseline_level, condition, model, metric, fold_id)
                    after_key = (level, condition, model, metric, fold_id)
                    if baseline_key not in by_key or after_key not in by_key:
                        raise ValueError(
                            "missing Fold pairing for paired difference: "
                            f"{after_key} vs {baseline_key}"
                        )
                    diffs.append(by_key[after_key] - by_key[baseline_key])
                rows.append(
                    {
                        "baseline_level": baseline_level,
                        "level": level,
                        "condition": condition,
                        "model": model,
                        "metric": metric,
                        "mean_diff": mean(diffs),
                        "std_diff": pstdev(diffs) if len(diffs) > 1 else 0.0,
                        "n_improved": sum(1 for diff in diffs if diff > 0),
                        "n_worsened": sum(1 for diff in diffs if diff < 0),
                        "n_folds": len(diffs),
                    }
                )
    return rows
