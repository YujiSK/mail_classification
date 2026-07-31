"""Fold-level Before/After paired differences against the D0 baseline."""

from __future__ import annotations

from statistics import mean, pstdev

PAIRED_DIFFERENCE_FIELDS = [
    "baseline_condition",
    "condition",
    "model",
    "metric",
    "mean_diff",
    "std_diff",
    "n_improved",
    "n_worsened",
    "n_folds",
]


def build_paired_differences(
    metrics_long: list[dict[str, object]], *, baseline_condition: str = "D0"
) -> list[dict[str, object]]:
    """Per (condition != baseline, model, metric): mean/std Fold diff vs baseline.

    Requires every (condition, model, metric) to have a value at every fold_id
    that the baseline has for that (model, metric) — a missing pairing is a
    coverage bug, not a value to silently skip, so it raises.
    """
    by_key: dict[tuple[str, str, str, int], float] = {
        (row["condition"], row["model"], row["metric"], row["fold_id"]): row["value"]
        for row in metrics_long
    }
    conditions = sorted(
        {row["condition"] for row in metrics_long} - {baseline_condition}
    )
    models = sorted({row["model"] for row in metrics_long})
    metrics = sorted({row["metric"] for row in metrics_long})
    fold_ids = sorted({row["fold_id"] for row in metrics_long})

    rows: list[dict[str, object]] = []
    for condition in conditions:
        for model in models:
            for metric in metrics:
                diffs: list[float] = []
                for fold_id in fold_ids:
                    baseline_key = (baseline_condition, model, metric, fold_id)
                    after_key = (condition, model, metric, fold_id)
                    if baseline_key not in by_key or after_key not in by_key:
                        raise ValueError(
                            "missing Fold pairing for paired difference: "
                            f"{after_key} vs {baseline_key}"
                        )
                    diffs.append(by_key[after_key] - by_key[baseline_key])
                rows.append(
                    {
                        "baseline_condition": baseline_condition,
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
