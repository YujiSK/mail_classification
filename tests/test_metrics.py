import pytest

from mail_classification.evaluation import build_confusion_matrix_rows, build_metrics_long
from mail_classification.evaluation.cv import FoldFitResult


def _result(condition, model, fold_id, oof_rows, n_train=8, n_test=None) -> FoldFitResult:
    return FoldFitResult(
        condition=condition,
        model=model,
        fold_id=fold_id,
        n_train=n_train,
        n_test=n_test if n_test is not None else len(oof_rows),
        fit_seconds=0.01,
        predict_seconds=0.001,
        vocabulary_size=42,
        oof_rows=tuple(oof_rows),
    )


PERFECT_ROWS = [
    {"sample_id": "s1", "true_label": "billing", "predicted_label": "billing"},
    {"sample_id": "s2", "true_label": "billing", "predicted_label": "billing"},
    {"sample_id": "s3", "true_label": "technical_issue", "predicted_label": "technical_issue"},
    {"sample_id": "s4", "true_label": "technical_issue", "predicted_label": "technical_issue"},
]

ONE_WRONG_ROWS = [
    {"sample_id": "s1", "true_label": "billing", "predicted_label": "billing"},
    {"sample_id": "s2", "true_label": "billing", "predicted_label": "technical_issue"},
    {"sample_id": "s3", "true_label": "technical_issue", "predicted_label": "technical_issue"},
    {"sample_id": "s4", "true_label": "technical_issue", "predicted_label": "technical_issue"},
]


def test_build_metrics_long_reports_perfect_scores_when_all_correct() -> None:
    rows = build_metrics_long([_result("D0", "linear_svc", 0, PERFECT_ROWS)])

    by_metric = {row["metric"]: row["value"] for row in rows}
    assert by_metric["accuracy"] == 1.0
    assert by_metric["macro_f1"] == 1.0
    assert by_metric["weighted_f1"] == 1.0
    assert by_metric["precision_billing"] == 1.0
    assert by_metric["recall_billing"] == 1.0


def test_build_metrics_long_reports_reduced_scores_with_one_mistake() -> None:
    rows = build_metrics_long([_result("D0", "linear_svc", 0, ONE_WRONG_ROWS)])

    by_metric = {row["metric"]: row["value"] for row in rows}
    assert by_metric["accuracy"] == pytest.approx(0.75)
    assert by_metric["recall_billing"] == pytest.approx(0.5)
    assert by_metric["precision_technical_issue"] == pytest.approx(2 / 3)


def test_build_metrics_long_carries_base_fields_onto_every_metric_row() -> None:
    rows = build_metrics_long(
        [_result("D1", "logistic_regression", 2, PERFECT_ROWS, n_train=16)]
    )

    assert all(row["condition"] == "D1" for row in rows)
    assert all(row["model"] == "logistic_regression" for row in rows)
    assert all(row["fold_id"] == 2 for row in rows)
    assert all(row["n_train"] == 16 for row in rows)
    assert all(row["vocabulary_size"] == 42 for row in rows)


def test_build_metrics_long_covers_two_folds_independently() -> None:
    rows = build_metrics_long(
        [
            _result("D0", "linear_svc", 0, PERFECT_ROWS),
            _result("D0", "linear_svc", 1, ONE_WRONG_ROWS),
        ]
    )

    accuracies = {
        row["fold_id"]: row["value"] for row in rows if row["metric"] == "accuracy"
    }
    assert accuracies == {0: 1.0, 1: pytest.approx(0.75)}


def test_build_confusion_matrix_rows_counts_match_oof_row_count() -> None:
    rows = build_confusion_matrix_rows(
        [
            _result("D0", "linear_svc", 0, ONE_WRONG_ROWS),
        ]
    )

    assert sum(row["count"] for row in rows) == len(ONE_WRONG_ROWS)
    mismatch = next(
        row
        for row in rows
        if row["true_label"] == "billing" and row["predicted_label"] == "technical_issue"
    )
    assert mismatch["count"] == 1


def test_build_confusion_matrix_rows_groups_separately_per_condition_and_model() -> None:
    rows = build_confusion_matrix_rows(
        [
            _result("D0", "linear_svc", 0, PERFECT_ROWS),
            _result("D1", "linear_svc", 0, ONE_WRONG_ROWS),
        ]
    )

    keys = {(row["condition"], row["model"]) for row in rows}
    assert keys == {("D0", "linear_svc"), ("D1", "linear_svc")}
