"""Cross-check report.md's numbers against the artifacts they were generated from.

Guarded skip (real Full-data run required) matching the project's existing
real-data-smoke convention. Also exercises building the report end-to-end
from a synthetic run so the report path itself is covered even without the
real 800-record artifacts.
"""

import json
from pathlib import Path

import pytest

from mail_classification.evaluation import write_fold_artifact
from mail_classification.extensions.subtopic_contamination import (
    run_and_write_subtopic_contamination_extension,
    write_subtopic_contamination_report,
)
from test_cv import synthetic_fold_artifact, synthetic_records

ROOT = Path(__file__).parents[1]
RUN_DIR = ROOT / "outputs" / "extensions" / "phase-subtopic-contamination-seed42"
REPORT_MD = ROOT / "outputs" / "reports" / "ext-subtopic-contamination-report-seed42" / "report.md"


def _skip_unless_real_report_exists() -> str:
    if not REPORT_MD.is_file():
        pytest.skip(f"{REPORT_MD} was not generated locally")
    return REPORT_MD.read_text(encoding="utf-8")


def test_report_macro_f1_headline_matches_summary_json() -> None:
    report_text = _skip_unless_real_report_exists()
    summary = json.loads((RUN_DIR / "summary.json").read_text(encoding="utf-8"))
    macro_f1 = summary["primary_cell_macro_f1_by_level"]

    expected = (
        f"C0 {macro_f1['C0']:.3f} → C10 {macro_f1['C10']:.3f} → "
        f"C20 {macro_f1['C20']:.3f} → C30 {macro_f1['C30']:.3f}"
    )
    assert expected in report_text


def test_report_accuracy_headline_matches_summary_json() -> None:
    report_text = _skip_unless_real_report_exists()
    summary = json.loads((RUN_DIR / "summary.json").read_text(encoding="utf-8"))
    accuracy = summary["primary_cell_accuracy_by_level"]

    expected = (
        f"C0 {accuracy['C0']:.3f} → C10 {accuracy['C10']:.3f} → "
        f"C20 {accuracy['C20']:.3f} → C30 {accuracy['C30']:.3f}"
    )
    assert expected in report_text


def test_report_contamination_counts_match_dataset_manifest() -> None:
    report_text = _skip_unless_real_report_exists()
    dataset_manifest = json.loads((RUN_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))

    for level, info in dataset_manifest["levels"].items():
        assert f"{info['contaminated_ratio']:.1%}" in report_text or level == "C0"


def test_report_fold_artifact_hash_matches_manifest() -> None:
    report_text = _skip_unless_real_report_exists()
    manifest = json.loads((RUN_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["fold_artifact_hash"] in report_text
    assert manifest["run_id"] in report_text


def test_report_mcnemar_p_values_match_statistical_tests_json() -> None:
    report_text = _skip_unless_real_report_exists()
    payload = json.loads((RUN_DIR / "statistical_tests.json").read_text(encoding="utf-8"))
    for entry in payload["mcnemar"]:
        assert f"{entry['p_value']:.2e}" in report_text


def test_pdf_and_layout_check_exist_and_pass() -> None:
    _skip_unless_real_report_exists()
    report_dir = REPORT_MD.parent
    assert (report_dir / "report.pdf").is_file()
    layout_check = json.loads((report_dir / "layout_check.json").read_text(encoding="utf-8"))
    assert layout_check["status"] == "PASS"
    assert layout_check["violations"] == []


def test_write_report_end_to_end_on_synthetic_data(tmp_path: Path) -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    fold_path = tmp_path / "outputs" / "folds" / "common_folds.json"
    write_fold_artifact(fold_path, artifact)

    run_and_write_subtopic_contamination_extension(
        records, fold_path, tmp_path, run_id="test-report-run", seed=42
    )
    result = write_subtopic_contamination_report(
        tmp_path, run_id="test-report-run", report_run_id="test-report-run-report"
    )

    assert result.markdown_path.is_file()
    assert result.pdf_path.is_file()
    layout_check = json.loads(result.layout_check_path.read_text(encoding="utf-8"))
    assert layout_check["status"] == "PASS"

    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert "問い合わせメール分類における副トピック混入率の影響" in markdown_text
