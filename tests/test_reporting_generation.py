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
        "第1章 はじめに",
        "第2章 関連技術",
        "第3章 実験方法",
        "第4章 実験結果",
        "第5章 考察",
        "第6章 データ品質とリーク対策",
        "第7章 限界と今後の課題",
        "第8章 まとめ",
        "第9章 参考文献",
        "付録 Technical Appendix",
    ):
        assert heading in markdown_text
    assert manifests["core"]["data_hash"] in markdown_text
    assert "figures/macro_f1_comparison.svg" in markdown_text
    body, appendix = markdown_text.split("## 付録 Technical Appendix", maxsplit=1)
    assert manifests["core"]["data_hash"] not in body
    assert manifests["core"]["run_id"] not in body
    assert "outputs/" not in body
    assert "Phase " not in body
    assert manifests["core"]["data_hash"] in appendix
    assert "Macro Precision" in body and "Macro Recall" in body
    assert "D1（bigram追加条件）" in body
    assert "uni-gram" not in body and "bi-gram" not in body
    assert "linear_svc" not in body
    assert "/home/" not in appendix and "/tmp/" not in appendix
    assert "各指標は5分割の平均値を用いて比較した" in body
    assert "表中の値は5分割の平均と母標準偏差" not in body


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

    html_text = result.html_path.read_text(encoding="utf-8")
    assert 'data-source-id="heading-6"' in html_text
    assert 'class="force-page-break" data-source-id="heading-6"' in html_text

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


def test_build_report_with_real_bert_comparison_chapter(tmp_path: Path) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    quality_summary_path = ROOT / "outputs" / "data_quality" / "full_summary.json"
    real_bert_dir = ROOT / "outputs" / "runs" / "phase8-bert-seed42"
    if not full_data_path.is_file() or not quality_summary_path.is_file() or not real_bert_dir.is_dir():
        pytest.skip("Full dataset, quality summary, or real Phase 8 BERT artifact not present locally")

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
        run_id="phase8-bert-smoke-core",
    )
    run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="phase8-bert-smoke-explain",
    )
    run_and_write_minhash_extension(records, data_hash, tmp_path, run_id="phase8-bert-smoke-extension")

    bert_dir = tmp_path / "outputs" / "runs" / "phase8-bert-seed42"
    bert_dir.mkdir(parents=True)
    for name in ("bert_fold_metrics.csv", "bert_oof_predictions.csv", "execution_manifest.json"):
        (bert_dir / name).write_bytes((real_bert_dir / name).read_bytes())

    result = generation.write_report(
        tmp_path,
        run_id="phase8-bert-smoke-report",
        core_run_id="phase8-bert-smoke-core",
        explain_run_id="phase8-bert-smoke-explain",
        extension_run_id="phase8-bert-smoke-extension",
        bert_run_id="phase8-bert-seed42",
        quality_summary_path=quality_summary_path,
    )

    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert "4.5 DistilBERTとの比較" in markdown_text
    assert "5.5 DistilBERTとの比較" in markdown_text
    assert "第7章 限界と今後の課題" in markdown_text
    assert "distilbert-base-uncased" in markdown_text
    assert "DistilBERT（ファインチューニング）" in markdown_text
    assert "D1（bigram追加条件）＋LinearSVC" in markdown_text
    assert "`body_text`を加工せず標準Tokenizerへ渡して" in markdown_text
    assert "入力対象が完全には一致していない" in markdown_text
    assert "分類パイプライン全体の比較" in markdown_text
    assert "今後は同一入力を用いた比較が必要" in markdown_text

    check_result = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert check_result["status"] != "FAIL"


def test_build_report_with_real_fold_imbalance_and_structural_ratio_chapters(
    tmp_path: Path,
) -> None:
    from mail_classification.analysis import (
        write_fold_imbalance_stats,
        write_structural_ratio_comparison,
    )

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
        run_id="analysis-smoke-core",
    )
    explain_dir = run_and_write_explainability(
        records,
        fold_path,
        core_run_dir / "predictions_oof.csv",
        tmp_path,
        conditions=("D0", "D1", "D2"),
        models=("linear_svc", "logistic_regression"),
        run_id="analysis-smoke-explain",
    )
    run_and_write_minhash_extension(records, data_hash, tmp_path, run_id="analysis-smoke-extension")

    fold_imbalance_path = write_fold_imbalance_stats(
        fold_path, full_data_path, tmp_path / "outputs" / "analysis" / "fold_imbalance_stats.csv"
    )
    structural_ratio_path = write_structural_ratio_comparison(
        full_data_path,
        explain_dir / "misclassifications.csv",
        tmp_path / "outputs" / "analysis" / "structural_ratio_comparison.json",
    )

    result = generation.write_report(
        tmp_path,
        run_id="analysis-smoke-report",
        core_run_id="analysis-smoke-core",
        explain_run_id="analysis-smoke-explain",
        extension_run_id="analysis-smoke-extension",
        quality_summary_path=quality_summary_path,
        fold_imbalance_path=fold_imbalance_path,
        structural_ratio_path=structural_ratio_path,
    )

    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert "outputs/analysis/fold_imbalance_stats.csv" in markdown_text
    assert "outputs/analysis/structural_ratio_comparison.json" in markdown_text
    assert "group breakdown" in markdown_text
    assert "has_header" in markdown_text and "has_signature" in markdown_text
    assert "本分析では未検証" not in markdown_text

    check_result = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert check_result["status"] != "FAIL"


def test_render_report_pdf_reflects_hand_edited_markdown_verbatim(tmp_path: Path) -> None:
    """render_report_pdf must never regenerate/overwrite report.md content;
    it only converts whatever text is already on disk."""
    report_dir = tmp_path / "outputs" / "reports" / "manual-edit-smoke"
    report_dir.mkdir(parents=True)
    markdown_path = report_dir / "report.md"
    markdown_path.write_text(
        "# Hand-edited title\n\nThis paragraph was typed by hand, not generated.\n",
        encoding="utf-8",
    )

    html_path, registry_path, pdf_path, layout_check_path = generation.render_report_pdf(
        markdown_path, report_dir
    )

    assert markdown_path.read_text(encoding="utf-8").startswith("# Hand-edited title")
    assert "Hand-edited title" in html_path.read_text(encoding="utf-8")
    assert pdf_path.is_file()
    check_result = json.loads(layout_check_path.read_text(encoding="utf-8"))
    assert check_result["status"] != "FAIL"
