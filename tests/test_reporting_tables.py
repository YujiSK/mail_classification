import json
from pathlib import Path

import pytest

from mail_classification.reporting import tables


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_markdown_table_basic() -> None:
    result = tables.markdown_table(["a", "b"], [["1", "2"], ["3", "4"]])
    lines = result.splitlines()
    assert lines[0] == "| a | b |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"
    assert lines[3] == "| 3 | 4 |"


def _metrics_summary_rows() -> list[dict[str, str]]:
    rows = []
    for condition in tables.CORE_CONDITIONS:
        for model in tables.CORE_MODELS:
            for metric, value in (("macro_f1", 0.6), ("accuracy", 0.65)):
                rows.append(
                    {
                        "condition": condition,
                        "model": model,
                        "metric": metric,
                        "cv_mean": str(value),
                        "cv_std": "0.05",
                        "n_folds": "5",
                    }
                )
    return rows


def test_build_metric_summary_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_csv(
        run_dir / "metrics_summary.csv",
        _metrics_summary_rows(),
        ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"],
    )

    result = tables.build_metric_summary_table(run_dir, "macro_f1")
    assert "0.600 ± 0.050" in result
    assert result.count("0.600 ± 0.050") == len(tables.CORE_CONDITIONS) * len(tables.CORE_MODELS)


def test_build_metric_summary_table_missing_metric_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_csv(
        run_dir / "metrics_summary.csv",
        _metrics_summary_rows(),
        ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"],
    )

    with pytest.raises(ValueError, match="not found"):
        tables.build_metric_summary_table(run_dir, "nonexistent_metric")


def test_build_confusion_matrix_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = [
        {"condition": "D0", "model": "linear_svc", "true_label": "billing", "predicted_label": "billing", "count": "10"},
        {"condition": "D0", "model": "linear_svc", "true_label": "billing", "predicted_label": "technical_issue", "count": "2"},
        {"condition": "D0", "model": "linear_svc", "true_label": "technical_issue", "predicted_label": "technical_issue", "count": "8"},
    ]
    _write_csv(
        run_dir / "confusion_matrix.csv",
        rows,
        ["condition", "model", "true_label", "predicted_label", "count"],
    )

    result = tables.build_confusion_matrix_table(run_dir, "D0", "linear_svc")
    assert "billing" in result
    assert "technical_issue" in result
    assert "10" in result
    # unseen (technical_issue -> billing) cell must default to 0, not be omitted.
    lines = result.splitlines()
    technical_row = next(line for line in lines if line.startswith("| technical_issue"))
    assert "| 0 |" in technical_row


def test_build_confusion_matrix_table_missing_cell_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = [
        {"condition": "D0", "model": "linear_svc", "true_label": "billing", "predicted_label": "billing", "count": "10"},
    ]
    _write_csv(
        run_dir / "confusion_matrix.csv",
        rows,
        ["condition", "model", "true_label", "predicted_label", "count"],
    )

    with pytest.raises(ValueError, match="no confusion_matrix rows"):
        tables.build_confusion_matrix_table(run_dir, "D1", "logistic_regression")


def test_build_paired_differences_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = [
        {
            "baseline_condition": "D0",
            "condition": "D1",
            "model": "linear_svc",
            "metric": "macro_f1",
            "mean_diff": "0.01",
            "std_diff": "0.02",
            "n_improved": "4",
            "n_worsened": "1",
            "n_folds": "5",
        }
    ]
    _write_csv(
        run_dir / "paired_differences.csv",
        rows,
        [
            "baseline_condition",
            "condition",
            "model",
            "metric",
            "mean_diff",
            "std_diff",
            "n_improved",
            "n_worsened",
            "n_folds",
        ],
    )

    result = tables.build_paired_differences_table(run_dir, baseline="D0", metric="macro_f1")
    assert "+0.010" in result
    assert "D1" in result


def test_read_paired_diff_mean(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = [
        {
            "baseline_condition": "D0",
            "condition": "D1",
            "model": "linear_svc",
            "metric": "macro_f1",
            "mean_diff": "0.0123",
            "std_diff": "0.02",
            "n_improved": "4",
            "n_worsened": "1",
            "n_folds": "5",
        }
    ]
    _write_csv(
        run_dir / "paired_differences.csv",
        rows,
        [
            "baseline_condition",
            "condition",
            "model",
            "metric",
            "mean_diff",
            "std_diff",
            "n_improved",
            "n_worsened",
            "n_folds",
        ],
    )

    assert tables.read_paired_diff_mean(run_dir, "D1", "linear_svc") == pytest.approx(0.0123)


def test_read_paired_diff_mean_missing_cell_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_csv(
        run_dir / "paired_differences.csv",
        [],
        [
            "baseline_condition",
            "condition",
            "model",
            "metric",
            "mean_diff",
            "std_diff",
            "n_improved",
            "n_worsened",
            "n_folds",
        ],
    )

    with pytest.raises(ValueError, match="no paired_differences row"):
        tables.read_paired_diff_mean(run_dir, "D1", "linear_svc")


def test_build_error_category_summary_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = []
    for condition in tables.CORE_CONDITIONS:
        for model in tables.CORE_MODELS:
            rows.append({"condition": condition, "model": model, "primary_category": "multi_intent", "count": "3"})
    _write_csv(
        run_dir / "error_category_summary.csv",
        rows,
        ["condition", "model", "primary_category", "count"],
    )

    result = tables.build_error_category_summary_table(run_dir)
    assert "multi_intent" in result
    assert result.count("| 3 |") == len(tables.CORE_CONDITIONS) * len(tables.CORE_MODELS)


def test_build_extension_summary_table(tmp_path: Path) -> None:
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir(parents=True)
    (extension_dir / "summary.json").write_text(
        json.dumps({"total_candidate_pairs": 5, "cross_label_pairs": 0}), encoding="utf-8"
    )

    result = tables.build_extension_summary_table(extension_dir)
    assert "total candidate pairs" in result
    assert "5" in result


def test_build_class_distribution_table(tmp_path: Path) -> None:
    quality_path = tmp_path / "full_summary.json"
    quality_path.write_text(
        json.dumps({"class_counts": {"billing": 200, "account_support": 200}, "class_ratios": {"billing": 0.5, "account_support": 0.5}}),
        encoding="utf-8",
    )

    result = tables.build_class_distribution_table(quality_path)
    assert "billing" in result
    assert "200" in result
    assert "0.50" in result
