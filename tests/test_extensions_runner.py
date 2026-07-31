import json
from pathlib import Path

import pytest

from mail_classification.evaluation import load_verified_full_dataset, verify_full_dataset_hash
from mail_classification.extensions import run_and_write_minhash_extension

ROOT = Path(__file__).parents[1]


def test_run_and_write_minhash_extension_writes_under_extensions_not_core(
    tmp_path: Path,
) -> None:
    from test_minhash import _record
    from mail_classification.schemas import MailLabel

    records = [
        _record("m1", MailLabel.BILLING, "Please cancel my subscription now."),
        _record("m2", MailLabel.BILLING, "Please cancel my subscription now."),
    ]

    run_dir = run_and_write_minhash_extension(
        records, "a" * 64, tmp_path, run_id="test-minhash-run"
    )

    assert run_dir == tmp_path / "outputs" / "extensions" / "test-minhash-run"
    assert (run_dir / "near_duplicates.csv").is_file()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "manifest.json").is_file()

    # Core namespaces must not exist as a side effect of running the Extension.
    assert not (tmp_path / "outputs" / "runs").exists()
    assert not (tmp_path / "outputs" / "data_quality").exists()


def test_run_and_write_minhash_extension_manifest_has_no_fold_reference(
    tmp_path: Path,
) -> None:
    from test_minhash import _record
    from mail_classification.schemas import MailLabel

    records = [_record("m1", MailLabel.BILLING, "Please cancel my subscription now.")]

    run_dir = run_and_write_minhash_extension(records, "a" * 64, tmp_path)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["fold_artifact_path"] is None
    assert manifest["fold_artifact_hash"] is None
    assert manifest["dependency_versions"] == {}
    assert manifest["data_hash"] == "a" * 64
    assert manifest["primary_metric"] == "jaccard_similarity"


def test_minhash_extension_on_real_full_dataset_never_touches_core_outputs(
    tmp_path: Path,
) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    if not full_data_path.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")

    data_hash = verify_full_dataset_hash(full_data_path, decision_path)
    records = load_verified_full_dataset(full_data_path, decision_path)

    run_dir = run_and_write_minhash_extension(
        records, data_hash, tmp_path, run_id="phase6-minhash-real-data-smoke"
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_candidate_pairs"] >= 0
    assert not (tmp_path / "outputs" / "runs").exists()
    assert not (tmp_path / "outputs" / "data_quality").exists()
    assert not (tmp_path / "outputs" / "folds").exists()
