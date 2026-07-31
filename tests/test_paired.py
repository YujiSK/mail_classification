import pytest

from mail_classification.evaluation import build_paired_differences

METRICS_LONG = [
    {"condition": "D0", "model": "linear_svc", "fold_id": 0, "metric": "macro_f1", "value": 0.80},
    {"condition": "D0", "model": "linear_svc", "fold_id": 1, "metric": "macro_f1", "value": 0.70},
    {"condition": "D1", "model": "linear_svc", "fold_id": 0, "metric": "macro_f1", "value": 0.85},
    {"condition": "D1", "model": "linear_svc", "fold_id": 1, "metric": "macro_f1", "value": 0.60},
]


def test_build_paired_differences_computes_fold_level_diff_vs_baseline() -> None:
    rows = build_paired_differences(METRICS_LONG, baseline_condition="D0")

    assert len(rows) == 1
    row = rows[0]
    assert row["condition"] == "D1"
    assert row["baseline_condition"] == "D0"
    assert row["mean_diff"] == pytest.approx(((0.85 - 0.80) + (0.60 - 0.70)) / 2)
    assert row["n_improved"] == 1
    assert row["n_worsened"] == 1
    assert row["n_folds"] == 2


def test_build_paired_differences_excludes_baseline_from_conditions() -> None:
    rows = build_paired_differences(METRICS_LONG, baseline_condition="D0")

    assert all(row["condition"] != "D0" for row in rows)


def test_build_paired_differences_raises_on_missing_fold_pairing() -> None:
    incomplete = METRICS_LONG + [
        {
            "condition": "D2",
            "model": "linear_svc",
            "fold_id": 0,
            "metric": "macro_f1",
            "value": 0.9,
        }
    ]

    with pytest.raises(ValueError, match="missing Fold pairing"):
        build_paired_differences(incomplete, baseline_condition="D0")
