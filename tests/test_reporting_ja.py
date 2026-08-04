from pathlib import Path

import pytest

from mail_classification.reporting.ja_generation import (
    build_report_markdown_ja,
    verify_selected_runs_consistent_ja,
    write_report_ja,
)
from mail_classification.reporting.ja_tables import (
    JA_CORE_CONDITIONS,
    JA_CORE_MODELS,
    build_error_category_counts_table,
    build_error_category_percentage_table_ja,
)
from mail_classification.reporting.ja_figures import macro_f1_comparison_svg_ja

ROOT = Path(__file__).parents[1]
CORE_DIR = ROOT / "outputs" / "runs" / "phaseJA4-core-seed42"
EXPLAIN_DIR = ROOT / "outputs" / "runs" / "phaseJA5-explain-seed42"
EXTENSION_DIR = ROOT / "outputs" / "extensions" / "phaseJA6-minhash-seed42"
QUALITY_SUMMARY = ROOT / "outputs" / "data_quality" / "full_summary_ja.json"


def _require_real_artifacts() -> None:
    if not (CORE_DIR / "manifest.json").is_file():
        pytest.skip("Phase JA-4 run artifacts are not generated locally")


def test_error_category_percentage_table_uses_ja_conditions_not_english() -> None:
    _require_real_artifacts()
    table = build_error_category_percentage_table_ja(EXPLAIN_DIR)
    for condition in JA_CORE_CONDITIONS:
        assert condition in table
    # Regression guard for the bug caught by rendering a real preview PDF:
    # reusing tables.build_error_category_percentage_table directly rendered
    # English D0/D1/D2 rows (all zero counts) instead of J0-JC.
    assert "| D0" not in table
    assert "| D1" not in table
    assert "0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 |" not in table


def test_error_category_counts_table_columns_are_short_enough_to_fit() -> None:
    _require_real_artifacts()
    table = build_error_category_counts_table(EXPLAIN_DIR)
    # Regression guard for the PDF-page-width overflow caught by rendering a
    # real preview page: percentage-only cells, not "count (percent%)".
    assert "%" in table
    for condition in JA_CORE_CONDITIONS:
        assert f"{condition}/SVC" in table or f"{condition}/LR" in table


def test_macro_f1_comparison_svg_ja_includes_all_conditions() -> None:
    _require_real_artifacts()
    svg = macro_f1_comparison_svg_ja(CORE_DIR)
    assert svg.startswith("<svg")
    for condition in JA_CORE_CONDITIONS:
        assert condition in svg


def test_verify_selected_runs_consistent_ja_passes_on_real_artifacts() -> None:
    _require_real_artifacts()
    manifests = verify_selected_runs_consistent_ja(
        ROOT, "phaseJA4-core-seed42", "phaseJA5-explain-seed42", "phaseJA6-minhash-seed42"
    )
    assert manifests["core"]["data_hash"] == manifests["explain"]["data_hash"]


def test_verify_selected_runs_consistent_ja_rejects_mismatched_data_hash(tmp_path: Path) -> None:
    import json

    for name, subdir in (("core", "runs"), ("explain", "runs"), ("extension", "extensions")):
        run_dir = tmp_path / "outputs" / subdir / f"{name}-run"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "data_hash": "a" * 64 if name != "extension" else "b" * 64,
                    "fold_artifact_hash": "c" * 64,
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="different data_hash"):
        verify_selected_runs_consistent_ja(tmp_path, "core-run", "explain-run", "extension-run")


def test_build_report_markdown_ja_without_bert_uses_pending_language() -> None:
    _require_real_artifacts()
    manifests = verify_selected_runs_consistent_ja(
        ROOT, "phaseJA4-core-seed42", "phaseJA5-explain-seed42", "phaseJA6-minhash-seed42"
    )
    en_comparison_path = ROOT / "outputs" / "runs" / "phaseJA8-en-ja-comparison-seed42.json"
    markdown = build_report_markdown_ja(
        manifests, CORE_DIR, EXPLAIN_DIR, EXTENSION_DIR, QUALITY_SUMMARY, en_comparison_path,
        bert_dir=None,
    )
    # The chapter explicitly states it will not fabricate unexecuted BERT
    # numbers, and does not claim results are done.
    assert "捏造してこの章へ記載することはしない" in markdown
    assert "未完了" in markdown or "未実行" in markdown
    assert "第9章 英語版との比較" in markdown


def test_write_report_ja_produces_passing_layout_check() -> None:
    _require_real_artifacts()
    if not (ROOT / "outputs" / "runs" / "phaseJA8-en-ja-comparison-seed42.json").is_file():
        pytest.skip("Phase JA-8 comparison artifact is not generated locally")
    import json

    result = write_report_ja(ROOT, run_id="test-phaseJA9-report")
    layout_check = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert layout_check["status"] == "PASS"
    assert layout_check["violations"] == []
    assert result.pdf_path.is_file()
