from statistics import mean, pstdev

import pytest

from mail_classification.evaluation import build_metrics_summary

METRICS_LONG = [
    {"condition": "D0", "model": "linear_svc", "fold_id": 0, "metric": "accuracy", "value": 0.9},
    {"condition": "D0", "model": "linear_svc", "fold_id": 1, "metric": "accuracy", "value": 0.8},
    {"condition": "D0", "model": "linear_svc", "fold_id": 2, "metric": "accuracy", "value": 1.0},
    {"condition": "D1", "model": "linear_svc", "fold_id": 0, "metric": "accuracy", "value": 0.7},
]


def test_build_metrics_summary_computes_mean_and_std_over_folds() -> None:
    rows = build_metrics_summary(METRICS_LONG)

    d0 = next(row for row in rows if row["condition"] == "D0")
    values = [0.9, 0.8, 1.0]
    assert d0["cv_mean"] == pytest.approx(mean(values))
    assert d0["cv_std"] == pytest.approx(pstdev(values))
    assert d0["n_folds"] == 3


def test_build_metrics_summary_keeps_conditions_separate() -> None:
    rows = build_metrics_summary(METRICS_LONG)

    keys = {(row["condition"], row["model"], row["metric"]) for row in rows}
    assert keys == {
        ("D0", "linear_svc", "accuracy"),
        ("D1", "linear_svc", "accuracy"),
    }


def test_build_metrics_summary_single_fold_has_zero_std() -> None:
    rows = build_metrics_summary(METRICS_LONG)

    d1 = next(row for row in rows if row["condition"] == "D1")
    assert d1["n_folds"] == 1
    assert d1["cv_std"] == 0.0
