import json
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
from mail_classification.extensions import run_and_write_minhash_extension
from mail_classification.reporting import generation
from test_cv import synthetic_fold_artifact, synthetic_records

ROOT = Path(__file__).parents[1]


def _write_manifest(run_dir: Path, *, data_hash: str, fold_artifact_hash: str | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_dir.name,
        "data_hash": data_hash,
        "fold_artifact_hash": fold_artifact_hash,
        "fold_artifact_path": "outputs/folds/common_folds.json",
        "cv_seed": 42,
    }
    (run_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_verify_selected_runs_consistent_raises_on_data_hash_mismatch(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "outputs" / "runs" / "core", data_hash="a" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(tmp_path / "outputs" / "runs" / "explain", data_hash="b" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(
        tmp_path / "outputs" / "extensions" / "ext", data_hash="a" * 64, fold_artifact_hash=None
    )

    with pytest.raises(ValueError, match="different data_hash"):
        generation.verify_selected_runs_consistent(tmp_path, "core", "explain", "ext")


def test_verify_selected_runs_consistent_raises_on_fold_hash_mismatch(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "outputs" / "runs" / "core", data_hash="a" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(tmp_path / "outputs" / "runs" / "explain", data_hash="a" * 64, fold_artifact_hash="e" * 64)
    _write_manifest(
        tmp_path / "outputs" / "extensions" / "ext", data_hash="a" * 64, fold_artifact_hash=None
    )

    with pytest.raises(ValueError, match="different fold_artifact_hash"):
        generation.verify_selected_runs_consistent(tmp_path, "core", "explain", "ext")


def test_verify_selected_runs_consistent_passes_when_aligned(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "outputs" / "runs" / "core", data_hash="a" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(tmp_path / "outputs" / "runs" / "explain", data_hash="a" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(
        tmp_path / "outputs" / "extensions" / "ext", data_hash="a" * 64, fold_artifact_hash=None
    )

    manifests = generation.verify_selected_runs_consistent(tmp_path, "core", "explain", "ext")
    assert manifests["core"]["data_hash"] == "a" * 64


def _build_synthetic_pipeline(tmp_path: Path) -> tuple[Path, Path, Path]:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    core_run_dir = run_and_write_core_experiments(
        records,
        fold_path,
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="test-core-run",
    )
    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="test-explain-run",
    )
    extension_dir = run_and_write_minhash_extension(
        records, artifact.metadata.data_hash, tmp_path, run_id="test-extension-run"
    )
    return core_run_dir, explain_dir, extension_dir


def test_build_report_markdown_contains_key_sections(tmp_path: Path) -> None:
    core_dir, explain_dir, extension_dir = _build_synthetic_pipeline(tmp_path)
    manifests = generation.verify_selected_runs_consistent(
        tmp_path, "test-core-run", "test-explain-run", "test-extension-run"
    )

    quality_summary_path = ROOT / "outputs" / "data_quality" / "full_summary.json"
    if not quality_summary_path.is_file():
        pytest.skip("outputs/data_quality/full_summary.json is not generated locally")

    markdown_text = generation.build_report_markdown(
        manifests, core_dir, explain_dir, extension_dir, quality_summary_path
    )

    for heading in (
        "第1章 大学課題要件との対応",
        "第2章 データ概要と合成データの限界",
        "第3章 Core実験結果",
        "第4章 説明性・誤分類分析",
        "第5章 Extension",
        "第6章 リーク監査まとめ",
        "第7章 再現手順",
        "第8章 既知の限界・未実施事項",
    ):
        assert heading in markdown_text
    assert manifests["core"]["data_hash"] in markdown_text
    assert "figures/macro_f1_comparison.svg" in markdown_text


def test_write_report_end_to_end_with_synthetic_pipeline(tmp_path: Path) -> None:
    core_dir, explain_dir, extension_dir = _build_synthetic_pipeline(tmp_path)

    quality_summary_path = ROOT / "outputs" / "data_quality" / "full_summary.json"
    if not quality_summary_path.is_file():
        pytest.skip("outputs/data_quality/full_summary.json is not generated locally")

    result = generation.write_report(
        tmp_path,
        run_id="test-report-run",
        core_run_id="test-core-run",
        explain_run_id="test-explain-run",
        extension_run_id="test-extension-run",
        quality_summary_path=quality_summary_path,
    )

    assert result.markdown_path.is_file()
    assert result.html_path.is_file()
    assert result.pdf_path.is_file()
    assert result.registry_path.is_file()
    assert result.layout_check_path.is_file()
    assert result.manifest_path.is_file()

    check_result = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert check_result["status"] != "FAIL"

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "test-report-run"
    assert manifest["dependency_versions"]


def test_write_report_raises_on_hash_mismatch_without_writing_pdf(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "outputs" / "runs" / "core", data_hash="a" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(tmp_path / "outputs" / "runs" / "explain", data_hash="b" * 64, fold_artifact_hash="f" * 64)
    _write_manifest(
        tmp_path / "outputs" / "extensions" / "ext", data_hash="a" * 64, fold_artifact_hash=None
    )

    with pytest.raises(ValueError, match="different data_hash"):
        generation.write_report(
            tmp_path, core_run_id="core", explain_run_id="explain", extension_run_id="ext"
        )
    assert not (tmp_path / "outputs" / "reports").exists()


def test_build_report_on_real_full_dataset_and_phase_4_5_6_pipeline(tmp_path: Path) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    quality_summary_path = ROOT / "outputs" / "data_quality" / "full_summary.json"
    if not full_data_path.is_file() or not quality_summary_path.is_file():
        pytest.skip("Full dataset or outputs/data_quality/full_summary.json is not generated locally")

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
        run_id="phase7-report-real-data-smoke-core",
    )
    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="phase7-report-real-data-smoke-explain",
    )
    extension_dir = run_and_write_minhash_extension(
        records, data_hash, tmp_path, run_id="phase7-report-real-data-smoke-extension"
    )

    result = generation.write_report(
        tmp_path,
        run_id="phase7-report-real-data-smoke",
        core_run_id="phase7-report-real-data-smoke-core",
        explain_run_id="phase7-report-real-data-smoke-explain",
        extension_run_id="phase7-report-real-data-smoke-extension",
        quality_summary_path=quality_summary_path,
    )

    assert result.pdf_path.stat().st_size > 0
    check_result = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert check_result["status"] != "FAIL"
    assert check_result["page_count"] > 1

    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert data_hash in markdown_text
    assert explain_dir.name in markdown_text
