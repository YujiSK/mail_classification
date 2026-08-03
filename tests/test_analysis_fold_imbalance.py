from pathlib import Path

import pytest

from mail_classification.analysis import compute_fold_imbalance_stats, write_fold_imbalance_stats
from mail_classification.evaluation import build_common_folds, write_fold_artifact
from mail_classification.generation.io import write_jsonl
from test_cv import synthetic_records


def _write_synthetic_fixture(tmp_path: Path):
    records = synthetic_records()
    full_path = tmp_path / "full_emails.jsonl"
    data_hash = write_jsonl(full_path, records)

    artifact = build_common_folds(records, data_hash=data_hash, n_splits=5, random_seed=42)
    fold_path = tmp_path / "common_folds.json"
    fold_artifact_hash = write_fold_artifact(fold_path, artifact)
    return full_path, fold_path, data_hash, fold_artifact_hash


def test_compute_fold_imbalance_stats_covers_every_sample_once(tmp_path: Path) -> None:
    full_path, fold_path, data_hash, fold_artifact_hash = _write_synthetic_fixture(tmp_path)

    stats = compute_fold_imbalance_stats(fold_path, full_path)

    assert set(stats["data_hash"]) == {data_hash}
    assert set(stats["fold_artifact_hash"]) == {fold_artifact_hash}
    assert set(stats["fold_id"]) == {0, 1, 2, 3, 4}

    totals = stats[stats["label"] == "ALL"]
    assert len(totals) == 5
    assert totals["n_samples"].sum() == 80  # synthetic_records(): 4 labels x 5 groups x 4 samples


def test_compute_fold_imbalance_stats_raises_on_data_hash_mismatch(tmp_path: Path) -> None:
    full_path, fold_path, data_hash, fold_artifact_hash = _write_synthetic_fixture(tmp_path)
    full_path.write_text(full_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        compute_fold_imbalance_stats(fold_path, full_path)


def test_write_fold_imbalance_stats_writes_csv(tmp_path: Path) -> None:
    full_path, fold_path, _, _ = _write_synthetic_fixture(tmp_path)
    output_path = tmp_path / "outputs" / "analysis" / "fold_imbalance_stats.csv"

    result_path = write_fold_imbalance_stats(fold_path, full_path, output_path)

    assert result_path == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "fold_id" in content.splitlines()[0]


def test_fold_imbalance_on_real_full_dataset_and_common_folds(tmp_path: Path) -> None:
    from mail_classification.evaluation import load_verified_full_dataset, verify_full_dataset_hash

    root = Path(__file__).parents[1]
    full_data_path = root / "data" / "raw" / "full_emails.jsonl"
    decision_path = root / "docs" / "reviews" / "full_review_decision.json"
    common_fold_path = root / "outputs" / "folds" / "common_folds.json"
    if not full_data_path.is_file() or not common_fold_path.is_file():
        pytest.skip("Full dataset or outputs/folds/common_folds.json is not generated locally")

    verify_full_dataset_hash(full_data_path, decision_path)
    load_verified_full_dataset(full_data_path, decision_path)

    stats = compute_fold_imbalance_stats(common_fold_path, full_data_path)
    totals = stats[stats["label"] == "ALL"]
    assert len(totals) == 5
    assert totals["n_samples"].sum() == 800
    # Known imbalance: exactly one fold gets 4 template groups/134 samples,
    # the other four get 5 groups/166-167 samples (see phase3_model_contract.md).
    assert sorted(totals["n_samples"].tolist()) == [134, 166, 166, 167, 167]
