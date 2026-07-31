import csv
from pathlib import Path

import pytest

from mail_classification.evaluation import (
    build_common_folds,
    load_fold_artifact,
    load_verified_full_dataset,
    run_and_write_core_experiments,
    verify_full_dataset_hash,
    write_fold_artifact,
)
from test_cv import synthetic_fold_artifact, synthetic_records

ROOT = Path(__file__).parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_load_fold_artifact_round_trips_write_fold_artifact(tmp_path: Path) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    path = tmp_path / "common_folds.json"
    write_fold_artifact(path, artifact)

    reloaded = load_fold_artifact(path)

    assert reloaded.metadata == artifact.metadata
    assert len(reloaded.records) == len(artifact.records)


def test_run_and_write_core_experiments_on_synthetic_data(tmp_path: Path) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1"),
        models=("linear_svc", "logistic_regression"),
        run_id="test-run",
    )

    assert run_dir == tmp_path / "outputs" / "runs" / "test-run"
    for filename in (
        "metrics_long.csv",
        "metrics_summary.csv",
        "predictions_oof.csv",
        "confusion_matrix.csv",
        "paired_differences.csv",
        "manifest.json",
    ):
        assert (run_dir / filename).is_file()

    oof_rows = _read_csv(run_dir / "predictions_oof.csv")
    cells = {(row["condition"], row["model"]) for row in oof_rows}
    assert cells == {
        ("D0", "linear_svc"),
        ("D0", "logistic_regression"),
        ("D1", "linear_svc"),
        ("D1", "logistic_regression"),
    }
    for condition, model in cells:
        sample_ids = [
            row["sample_id"]
            for row in oof_rows
            if row["condition"] == condition and row["model"] == model
        ]
        assert sorted(sample_ids) == sorted(record.id for record in records)
        assert len(sample_ids) == len(set(sample_ids))  # each sample predicted once


def test_run_and_write_core_experiments_manifest_references_fold_artifact(
    tmp_path: Path,
) -> None:
    import json

    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    fold_hash = write_fold_artifact(fold_path, artifact)

    run_dir = run_and_write_core_experiments(
        records, fold_path, tmp_path, conditions=("D0",), models=("linear_svc",)
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["fold_artifact_hash"] == fold_hash
    assert manifest["fold_artifact_path"] == str(fold_path)
    assert manifest["data_hash"] == "a" * 64
    assert manifest["model_name"] is None
    assert manifest["primary_metric"] == "macro_f1"


def test_paired_differences_are_present_for_a_multi_condition_run(
    tmp_path: Path,
) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1"),
        models=("linear_svc",),
    )

    paired_rows = _read_csv(run_dir / "paired_differences.csv")
    assert paired_rows
    assert all(row["baseline_condition"] == "D0" for row in paired_rows)
    assert all(row["condition"] == "D1" for row in paired_rows)


def test_core_run_on_real_full_dataset_and_common_folds(tmp_path: Path) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    if not full_data_path.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")

    data_hash = verify_full_dataset_hash(full_data_path, decision_path)
    records = load_verified_full_dataset(full_data_path, decision_path)
    artifact = build_common_folds(records, data_hash=data_hash)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="phase4-core-real-data-smoke",
    )

    oof_rows = _read_csv(run_dir / "predictions_oof.csv")
    assert len(oof_rows) == 3 * 2 * len(records)  # 3 conditions x 2 models x 800

    metrics_summary = _read_csv(run_dir / "metrics_summary.csv")
    macro_f1_means = {
        (row["condition"], row["model"]): float(row["cv_mean"])
        for row in metrics_summary
        if row["metric"] == "macro_f1"
    }
    assert len(macro_f1_means) == 6
    assert all(0.0 <= value <= 1.0 for value in macro_f1_means.values())

    paired_rows = _read_csv(run_dir / "paired_differences.csv")
    assert {row["condition"] for row in paired_rows} == {"D1", "D2"}
