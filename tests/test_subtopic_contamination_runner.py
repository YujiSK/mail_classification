import csv
import json
from pathlib import Path

from mail_classification.evaluation import write_fold_artifact
from mail_classification.extensions.subtopic_contamination import (
    run_and_write_subtopic_contamination_extension,
)
from test_cv import synthetic_fold_artifact, synthetic_records


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_synthetic_fold_artifact(tmp_path: Path) -> Path:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)
    return fold_path


def test_run_writes_only_under_extensions_and_derived_never_core_namespaces(tmp_path: Path) -> None:
    records = synthetic_records()
    fold_path = _write_synthetic_fold_artifact(tmp_path)

    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-subtopic-contamination", seed=42
    )

    assert run_dir == tmp_path / "outputs" / "extensions" / "test-subtopic-contamination"
    assert not (tmp_path / "outputs" / "runs").exists()
    assert not (tmp_path / "outputs" / "data_quality").exists()
    assert not (tmp_path / "data" / "raw").exists()

    required_files = [
        "contamination_assignment.csv",
        "dataset_manifest.json",
        "condition_statistics.csv",
        "metrics_long.csv",
        "metrics_summary.csv",
        "predictions_oof.csv",
        "confusion_matrix.csv",
        "paired_differences.csv",
        "transition_summary.csv",
        "main_subtopic_pair_summary.csv",
        "misclassifications.csv",
        "feature_shift.csv",
        "review_samples.csv",
        "manifest.json",
    ]
    for filename in required_files:
        assert (run_dir / filename).is_file(), filename

    derived_dir = tmp_path / "data" / "derived" / "subtopic_contamination" / "test-subtopic-contamination"
    for level in ("C0", "C10", "C20", "C30"):
        assert (derived_dir / f"full_emails_{level}.jsonl").is_file()


def test_oof_predictions_have_no_missing_or_duplicate_coverage(tmp_path: Path) -> None:
    records = synthetic_records()
    fold_path = _write_synthetic_fold_artifact(tmp_path)

    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-oof-coverage", seed=42
    )
    oof_rows = _read_csv(run_dir / "predictions_oof.csv")

    cells = {(row["contamination_level"], row["condition"], row["model"]) for row in oof_rows}
    assert len(cells) == 4 * 4  # 4 contamination levels x 4 (condition, model) cells

    all_ids = {record.id for record in records}
    for level, condition, model in cells:
        sample_ids = [
            row["sample_id"]
            for row in oof_rows
            if row["contamination_level"] == level and row["condition"] == condition and row["model"] == model
        ]
        assert sorted(sample_ids) == sorted(all_ids)
        assert len(sample_ids) == len(set(sample_ids))  # no duplicates


def test_fold_assignment_is_identical_across_all_contamination_levels(tmp_path: Path) -> None:
    """Same sample_id -> same fold_id at every level, for a fixed (condition, model)."""
    records = synthetic_records()
    fold_path = _write_synthetic_fold_artifact(tmp_path)

    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-fold-invariance", seed=42
    )
    oof_rows = _read_csv(run_dir / "predictions_oof.csv")

    fold_by_sample_and_level: dict[str, dict[str, str]] = {}
    for row in oof_rows:
        if row["condition"] != "D1" or row["model"] != "linear_svc":
            continue
        fold_by_sample_and_level.setdefault(row["sample_id"], {})[row["contamination_level"]] = row["fold_id"]

    for sample_id, fold_by_level in fold_by_sample_and_level.items():
        values = set(fold_by_level.values())
        assert len(values) == 1, f"{sample_id} has inconsistent fold assignment: {fold_by_level}"


def test_manifest_references_the_shared_fold_artifact_and_dataset_manifest(tmp_path: Path) -> None:
    records = synthetic_records()
    fold_path = _write_synthetic_fold_artifact(tmp_path)

    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-manifest", seed=42
    )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["fold_artifact_path"] == str(fold_path)
    assert manifest["fold_artifact_hash"] is not None
    assert manifest["cv_seed"] == 42
    assert manifest["primary_metric"] == "macro_f1"
    assert manifest["data_path"] == "outputs/extensions/test-manifest/dataset_manifest.json"

    dataset_manifest = json.loads((run_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert set(dataset_manifest["levels"]) == {"C0", "C10", "C20", "C30"}
    assert manifest["data_hash"] == dataset_manifest["levels"]["C0"]["data_hash"]


def test_review_samples_only_contains_flagged_contaminated_rows(tmp_path: Path) -> None:
    records = synthetic_records()
    fold_path = _write_synthetic_fold_artifact(tmp_path)

    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-review-samples", seed=42
    )
    review_rows = _read_csv(run_dir / "review_samples.csv")

    assignment_rows = _read_csv(run_dir / "contamination_assignment.csv")
    assignment_ids = {row["sample_id"] for row in assignment_rows}
    for row in review_rows:
        assert row["sample_id"] in assignment_ids
        assert row["flag_reason"]
