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


def _write_fold_artifact(path: Path, *, data_hash: str, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"metadata": {"data_hash": data_hash}, "records": records}), encoding="utf-8"
    )


def _write_bert_run(
    bert_dir: Path,
    *,
    data_hash: str,
    fold_rows: list[dict[str, str]],
    oof_rows: list[dict[str, str]],
) -> None:
    _write_csv(
        bert_dir / "bert_fold_metrics.csv",
        fold_rows,
        ["fold_id", "accuracy", "precision", "recall", "f1_score"],
    )
    _write_csv(
        bert_dir / "bert_oof_predictions.csv",
        oof_rows,
        ["sample_id", "fold_id", "predicted_label", "true_label"],
    )
    (bert_dir / "execution_manifest.json").write_text(
        json.dumps(
            {
                "actual_data_hash": data_hash,
                "model_config": {
                    "model_name": "distilbert-base-uncased",
                    "epochs": 3,
                    "batch_size": 16,
                    "learning_rate": 2e-05,
                    "max_length": 128,
                    "random_seed": 42,
                },
                "environment": {
                    "transformers_version": "5.13.1",
                    "torch_version": "2.11.0+cu128",
                    "python_version": "3.12.13",
                    "device": "cuda",
                },
            }
        ),
        encoding="utf-8",
    )


def _two_sample_fold_records() -> list[dict[str, object]]:
    return [
        {"sample_id": "s1", "fold_id": 0, "split_role": "validation", "template_group": "g0", "label": "billing"},
        {"sample_id": "s1", "fold_id": 1, "split_role": "train", "template_group": "g0", "label": "billing"},
        {"sample_id": "s2", "fold_id": 1, "split_role": "validation", "template_group": "g1", "label": "technical_issue"},
        {"sample_id": "s2", "fold_id": 0, "split_role": "train", "template_group": "g1", "label": "technical_issue"},
    ]


def test_verify_bert_alignment_passes_when_consistent(tmp_path: Path) -> None:
    data_hash = "a" * 64
    fold_path = tmp_path / "common_folds.json"
    _write_fold_artifact(fold_path, data_hash=data_hash, records=_two_sample_fold_records())

    bert_dir = tmp_path / "bert"
    _write_bert_run(
        bert_dir,
        data_hash=data_hash,
        fold_rows=[{"fold_id": "0", "accuracy": "0.9", "precision": "0.9", "recall": "0.9", "f1_score": "0.9"}],
        oof_rows=[
            {"sample_id": "s1", "fold_id": "0", "predicted_label": "billing", "true_label": "billing"},
            {"sample_id": "s2", "fold_id": "1", "predicted_label": "technical_issue", "true_label": "technical_issue"},
        ],
    )

    tables.verify_bert_alignment(bert_dir, fold_path, data_hash)


def test_verify_bert_alignment_raises_on_data_hash_mismatch(tmp_path: Path) -> None:
    fold_path = tmp_path / "common_folds.json"
    _write_fold_artifact(fold_path, data_hash="a" * 64, records=_two_sample_fold_records())

    bert_dir = tmp_path / "bert"
    _write_bert_run(
        bert_dir,
        data_hash="b" * 64,
        fold_rows=[{"fold_id": "0", "accuracy": "0.9", "precision": "0.9", "recall": "0.9", "f1_score": "0.9"}],
        oof_rows=[
            {"sample_id": "s1", "fold_id": "0", "predicted_label": "billing", "true_label": "billing"},
            {"sample_id": "s2", "fold_id": "1", "predicted_label": "technical_issue", "true_label": "technical_issue"},
        ],
    )

    with pytest.raises(ValueError, match="data_hash"):
        tables.verify_bert_alignment(bert_dir, fold_path, "a" * 64)


def test_verify_bert_alignment_raises_on_fold_id_mismatch(tmp_path: Path) -> None:
    data_hash = "a" * 64
    fold_path = tmp_path / "common_folds.json"
    _write_fold_artifact(fold_path, data_hash=data_hash, records=_two_sample_fold_records())

    bert_dir = tmp_path / "bert"
    _write_bert_run(
        bert_dir,
        data_hash=data_hash,
        fold_rows=[{"fold_id": "0", "accuracy": "0.9", "precision": "0.9", "recall": "0.9", "f1_score": "0.9"}],
        oof_rows=[
            # s1's real validation fold is 0, not 1 -- must be flagged.
            {"sample_id": "s1", "fold_id": "1", "predicted_label": "billing", "true_label": "billing"},
            {"sample_id": "s2", "fold_id": "1", "predicted_label": "technical_issue", "true_label": "technical_issue"},
        ],
    )

    with pytest.raises(ValueError, match="different fold_id"):
        tables.verify_bert_alignment(bert_dir, fold_path, data_hash)


def test_verify_bert_alignment_raises_on_incomplete_coverage(tmp_path: Path) -> None:
    data_hash = "a" * 64
    fold_path = tmp_path / "common_folds.json"
    _write_fold_artifact(fold_path, data_hash=data_hash, records=_two_sample_fold_records())

    bert_dir = tmp_path / "bert"
    _write_bert_run(
        bert_dir,
        data_hash=data_hash,
        fold_rows=[{"fold_id": "0", "accuracy": "0.9", "precision": "0.9", "recall": "0.9", "f1_score": "0.9"}],
        oof_rows=[
            # s2 is missing entirely.
            {"sample_id": "s1", "fold_id": "0", "predicted_label": "billing", "true_label": "billing"},
        ],
    )

    with pytest.raises(ValueError, match="incomplete coverage"):
        tables.verify_bert_alignment(bert_dir, fold_path, data_hash)


def test_read_bert_fold_metric_cv(tmp_path: Path) -> None:
    bert_dir = tmp_path / "bert"
    _write_csv(
        bert_dir / "bert_fold_metrics.csv",
        [
            {"fold_id": "0", "accuracy": "0.8", "precision": "0.8", "recall": "0.8", "f1_score": "0.70"},
            {"fold_id": "1", "accuracy": "0.9", "precision": "0.9", "recall": "0.9", "f1_score": "0.80"},
        ],
        ["fold_id", "accuracy", "precision", "recall", "f1_score"],
    )

    cv_mean, cv_std, n_folds = tables.read_bert_fold_metric_cv(bert_dir, "f1_score")
    assert cv_mean == pytest.approx(0.75)
    assert n_folds == 2
    assert cv_std > 0


def test_best_core_metric_cell(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    rows = [
        {"condition": "D0", "model": "linear_svc", "metric": "macro_f1", "cv_mean": "0.6", "cv_std": "0.1", "n_folds": "5"},
        {"condition": "D1", "model": "linear_svc", "metric": "macro_f1", "cv_mean": "0.7", "cv_std": "0.1", "n_folds": "5"},
        {"condition": "D2", "model": "linear_svc", "metric": "macro_f1", "cv_mean": "0.5", "cv_std": "0.1", "n_folds": "5"},
    ]
    _write_csv(run_dir / "metrics_summary.csv", rows, ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"])

    condition, model, value = tables.best_core_metric_cell(run_dir, "macro_f1")
    assert (condition, model) == ("D1", "linear_svc")
    assert value == pytest.approx(0.7)


def test_build_bert_comparison_table(tmp_path: Path) -> None:
    core_dir = tmp_path / "core"
    rows = []
    for condition in tables.CORE_CONDITIONS:
        for model in tables.CORE_MODELS:
            rows.append(
                {"condition": condition, "model": model, "metric": "macro_f1", "cv_mean": "0.6", "cv_std": "0.1", "n_folds": "5"}
            )
    _write_csv(core_dir / "metrics_summary.csv", rows, ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"])

    bert_dir = tmp_path / "bert"
    _write_csv(
        bert_dir / "bert_fold_metrics.csv",
        [{"fold_id": "0", "accuracy": "0.8", "precision": "0.8", "recall": "0.8", "f1_score": "0.80"}],
        ["fold_id", "accuracy", "precision", "recall", "f1_score"],
    )

    result = tables.build_bert_comparison_table(core_dir, bert_dir)
    assert "DistilBERT (fine-tuned)" in result
    assert "0.800 ± 0.000" in result
    assert result.count("0.600 ± 0.100") == len(tables.CORE_CONDITIONS) * len(tables.CORE_MODELS)


def test_build_bert_required_metrics_table(tmp_path: Path) -> None:
    core_dir = tmp_path / "core"
    rows = [
        {"condition": "D2", "model": "linear_svc", "metric": "accuracy", "cv_mean": "0.61", "cv_std": "0.1", "n_folds": "5"},
        {"condition": "D2", "model": "linear_svc", "metric": "macro_f1", "cv_mean": "0.60", "cv_std": "0.1", "n_folds": "5"},
    ]
    for prefix, values in (("precision", (0.60, 0.62, 0.64, 0.66)), ("recall", (0.58, 0.60, 0.62, 0.64))):
        for label, value in zip(
            ("account_support", "billing", "product_inquiry", "technical_issue"), values
        ):
            rows.append(
                {"condition": "D2", "model": "linear_svc", "metric": f"{prefix}_{label}", "cv_mean": str(value), "cv_std": "0.1", "n_folds": "5"}
            )
    _write_csv(
        core_dir / "metrics_summary.csv",
        rows,
        ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"],
    )

    bert_dir = tmp_path / "bert"
    _write_csv(
        bert_dir / "bert_fold_metrics.csv",
        [
            {"fold_id": "0", "accuracy": "0.78", "precision": "0.80", "recall": "0.76", "f1_score": "0.74"},
            {"fold_id": "1", "accuracy": "0.80", "precision": "0.84", "recall": "0.78", "f1_score": "0.76"},
        ],
        ["fold_id", "accuracy", "precision", "recall", "f1_score"],
    )

    result = tables.build_bert_required_metrics_table(core_dir, bert_dir)
    assert "TF-IDF + LinearSVC (D2)" in result
    assert "| Accuracy | 0.610 | 0.790 |" in result
    assert "| Precision (macro) | 0.630 | 0.820 |" in result
    assert "| Recall (macro) | 0.610 | 0.770 |" in result
    assert "| Macro-F1 | 0.600 | 0.750 |" in result
