import csv
from pathlib import Path

import pytest

from mail_classification.evaluation import (
    build_common_folds,
    load_verified_full_dataset,
    run_and_write_core_experiments,
    verify_full_dataset_hash,
    write_fold_artifact,
)
from mail_classification.explain import run_and_write_explainability
from test_cv import synthetic_fold_artifact, synthetic_records

ROOT = Path(__file__).parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_run_and_write_explainability_on_synthetic_data(tmp_path: Path) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    core_run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1"),
        models=("linear_svc",),
        run_id="test-core-run",
    )

    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1"),
        models=("linear_svc",),
        run_id="test-explain-run",
    )

    assert explain_dir == tmp_path / "outputs" / "runs" / "test-explain-run"
    for filename in (
        "fold_coefficients.csv",
        "descriptive_full_fit_coefficients.csv",
        "structural_artifact_audit.csv",
        "misclassifications.csv",
        "error_category_summary.csv",
        "manifest.json",
    ):
        assert (explain_dir / filename).is_file()

    coefficients = _read_csv(explain_dir / "fold_coefficients.csv")
    assert {row["condition"] for row in coefficients} == {"D0", "D1"}
    assert {row["fold_id"] for row in coefficients} == {"0", "1", "2", "3", "4"}

    descriptive = _read_csv(explain_dir / "descriptive_full_fit_coefficients.csv")
    assert descriptive
    assert all("fold_id" not in row for row in descriptive)


def test_misclassifications_are_a_subset_of_oof_rows_with_true_ne_predicted(
    tmp_path: Path,
) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    core_run_dir = run_and_write_core_experiments(
        records, fold_path, tmp_path, conditions=("D0",), models=("linear_svc",)
    )
    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0",),
        models=("linear_svc",),
    )

    oof_rows = _read_csv(core_run_dir / "predictions_oof.csv")
    expected_wrong_ids = {
        row["sample_id"] for row in oof_rows if row["true_label"] != row["predicted_label"]
    }
    misclassifications = _read_csv(explain_dir / "misclassifications.csv")
    assert {row["sample_id"] for row in misclassifications} == expected_wrong_ids
    assert all(row["true_label"] != row["predicted_label"] for row in misclassifications)


def test_explainability_on_real_full_dataset_and_phase4_run(tmp_path: Path) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    if not full_data_path.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")

    data_hash = verify_full_dataset_hash(full_data_path, decision_path)
    records = load_verified_full_dataset(full_data_path, decision_path)
    artifact = build_common_folds(records, data_hash=data_hash)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    core_run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="phase4-core-real-data-smoke",
    )

    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="phase5-explain-real-data-smoke",
    )

    coefficients = _read_csv(explain_dir / "fold_coefficients.csv")
    cells = {(row["condition"], row["model"]) for row in coefficients}
    assert len(cells) == 6
    assert {row["label"] for row in coefficients} == {
        "billing",
        "product_inquiry",
        "technical_issue",
        "account_support",
    }

    misclassifications = _read_csv(explain_dir / "misclassifications.csv")
    oof_rows = _read_csv(core_run_dir / "predictions_oof.csv")
    expected_wrong = sum(
        1 for row in oof_rows if row["true_label"] != row["predicted_label"]
    )
    assert len(misclassifications) == expected_wrong

    summary = _read_csv(explain_dir / "error_category_summary.csv")
    assert summary
    total_categorized = sum(int(row["count"]) for row in summary)
    assert total_categorized == expected_wrong

    assert misclassifications  # this real dataset/split does produce errors
    from mail_classification.schemas import MailLabel

    for row in misclassifications[:50]:  # sample a subset; full 800x pass is slow
        scores = {
            label.value: float(row[f"decision_score_{label.value}"]) for label in MailLabel
        }
        predicted_score = scores[row["predicted_label"]]
        assert predicted_score == max(scores.values())
        assert row["predicted_top_features"]
        assert row["true_top_features"]
