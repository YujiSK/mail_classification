"""Fold Long metric records and confusion-matrix rows derived from OOF predictions."""

from __future__ import annotations

from collections import Counter

from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from .cv import FoldFitResult

METRICS_LONG_FIELDS = [
    "condition",
    "model",
    "fold_id",
    "n_train",
    "n_test",
    "fit_seconds",
    "predict_seconds",
    "vocabulary_size",
    "metric",
    "value",
]

CONFUSION_FIELDS = ["condition", "model", "true_label", "predicted_label", "count"]


def build_metrics_long(fold_results: list[FoldFitResult]) -> list[dict[str, object]]:
    """One row per (condition, model, fold, metric): macro/weighted F1, accuracy, classwise P/R/F1."""
    rows: list[dict[str, object]] = []
    for result in fold_results:
        y_true = [row["true_label"] for row in result.oof_rows]
        y_pred = [row["predicted_label"] for row in result.oof_rows]
        labels = sorted(set(y_true) | set(y_pred))

        base = {
            "condition": result.condition,
            "model": result.model,
            "fold_id": result.fold_id,
            "n_train": result.n_train,
            "n_test": result.n_test,
            "fit_seconds": result.fit_seconds,
            "predict_seconds": result.predict_seconds,
            "vocabulary_size": result.vocabulary_size,
        }
        rows.append(
            {**base, "metric": "accuracy", "value": accuracy_score(y_true, y_pred)}
        )
        rows.append(
            {
                **base,
                "metric": "macro_f1",
                "value": f1_score(
                    y_true, y_pred, average="macro", labels=labels, zero_division=0
                ),
            }
        )
        rows.append(
            {
                **base,
                "metric": "weighted_f1",
                "value": f1_score(
                    y_true, y_pred, average="weighted", labels=labels, zero_division=0
                ),
            }
        )

        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=labels, zero_division=0
        )
        for label, p, r, f in zip(labels, precision, recall, f1):
            rows.append({**base, "metric": f"precision_{label}", "value": float(p)})
            rows.append({**base, "metric": f"recall_{label}", "value": float(r)})
            rows.append({**base, "metric": f"f1_{label}", "value": float(f)})
    return rows


def build_confusion_matrix_rows(
    fold_results: list[FoldFitResult],
) -> list[dict[str, object]]:
    """Long-format confusion matrix aggregated across all folds, per (condition, model)."""
    grouped: dict[tuple[str, str], Counter] = {}
    for result in fold_results:
        counter = grouped.setdefault((result.condition, result.model), Counter())
        for row in result.oof_rows:
            counter[(row["true_label"], row["predicted_label"])] += 1

    rows: list[dict[str, object]] = []
    for (condition, model), counter in sorted(grouped.items()):
        for (true_label, predicted_label), count in sorted(counter.items()):
            rows.append(
                {
                    "condition": condition,
                    "model": model,
                    "true_label": true_label,
                    "predicted_label": predicted_label,
                    "count": count,
                }
            )
    return rows
