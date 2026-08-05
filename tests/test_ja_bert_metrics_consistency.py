"""Regression guard for the Japanese BERT metric-aggregation audit.

Context: a 2026-08-04 daily-report entry narrated the final report's BERT
Accuracy as "0.737", which is close to fold 1's own accuracy
(0.7365269461...). Direct inspection of report.md and the report-generation
code (scripts/audit_ja_bert_metrics.py; reporting/ja_generation.py,
ja_tables.py) showed the actual generated value was always 0.797 (the
correct 5-fold mean) and that "0.737" appears nowhere in any generated
artifact or code path -- it was a manual transcription slip in the log
narrative, not a pipeline bug. These tests exist so that if the aggregation
code ever DID regress to leaking a single fold's value, it would fail
loudly instead of being caught only by someone re-reading a PDF by eye.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_ja_bert_metrics import (
    BERT_RUN_DIR,
    CORE_RUN_DIR,
    audit_fold_metrics,
    audit_oof_predictions,
    run_audit,
)

ROOT = Path(__file__).parents[1]
REPORT_DIR = ROOT / "outputs" / "reports" / "phaseJA9-report-phaseJA4-core-seed42"


def _require_bert_artifacts() -> None:
    if not (BERT_RUN_DIR / "manifest.json").is_file():
        pytest.skip("Phase JA-7 BERT run artifacts are not generated locally")


def _require_report_artifacts() -> None:
    if not (REPORT_DIR / "report.md").is_file():
        pytest.skip("Phase JA-9 report artifacts are not generated locally")


def test_oof_predictions_have_no_duplicates_or_missing_ids() -> None:
    _require_bert_artifacts()
    summary = audit_oof_predictions(BERT_RUN_DIR / "predictions_oof.csv")
    assert summary["oof_row_count"] == 800
    assert summary["sample_id_duplicate_count"] == 0
    assert summary["sample_id_missing_count"] == 0
    assert summary["confusion_matrix_sum"] == 800
    assert all(count == 200 for count in summary["true_label_counts"].values())


def test_fold_metrics_n_val_sums_to_800() -> None:
    _require_bert_artifacts()
    summary = audit_fold_metrics(BERT_RUN_DIR / "fold_metrics.csv")
    assert summary["n_val_sum"] == 800
    assert len(summary["per_fold_accuracy"]) == 5


def test_full_audit_passes_every_check() -> None:
    _require_bert_artifacts()
    result = run_audit()
    assert result["all_checks_passed"], result["checks"]


def test_fold_mean_accuracy_does_not_equal_any_single_fold_value() -> None:
    """The core regression guard: the reported fold-mean accuracy must not
    coincide with (i.e. must not have silently become) any one fold's raw
    accuracy, which is what a `.iloc[k]`/`first()`-style aggregation bug
    would produce."""
    _require_bert_artifacts()
    summary = audit_fold_metrics(BERT_RUN_DIR / "fold_metrics.csv")
    fold_mean = summary["fold_mean_accuracy"]
    for fold_index, fold_value in enumerate(summary["per_fold_accuracy"]):
        assert fold_mean != pytest.approx(fold_value, abs=1e-9), (
            f"fold_mean_accuracy ({fold_mean}) equals fold {fold_index}'s own "
            f"accuracy ({fold_value}) -- looks like a single-fold value leaked "
            "into the aggregate instead of averaging all 5 folds"
        )


def test_fold_mean_accuracy_matches_manual_recomputation() -> None:
    _require_bert_artifacts()
    summary = audit_fold_metrics(BERT_RUN_DIR / "fold_metrics.csv")
    manual_mean = sum(summary["per_fold_accuracy"]) / len(summary["per_fold_accuracy"])
    assert summary["fold_mean_accuracy"] == pytest.approx(manual_mean, abs=1e-12)


def test_oof_accuracy_matches_direct_recomputation_from_oof_csv() -> None:
    _require_bert_artifacts()
    import csv

    with (BERT_RUN_DIR / "predictions_oof.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    manual_oof_accuracy = sum(
        1 for r in rows if r["true_label"] == r["predicted_label"]
    ) / len(rows)

    summary = audit_oof_predictions(BERT_RUN_DIR / "predictions_oof.csv")
    assert summary["oof_accuracy"] == pytest.approx(manual_oof_accuracy, abs=1e-12)


def test_fold_mean_and_oof_accuracy_are_reported_as_distinct_named_values() -> None:
    """fold_mean_accuracy and oof_accuracy are expected to differ slightly
    (fold sizes are 167/167/134/166/166, not perfectly equal) and must never
    be silently treated as interchangeable."""
    _require_bert_artifacts()
    result = run_audit()
    fold_mean = result["fold_summary"]["fold_mean_accuracy"]
    oof_value = result["oof_summary"]["oof_accuracy"]
    assert fold_mean != oof_value
    assert abs(fold_mean - oof_value) < 0.01  # close, but must stay distinct


def test_bert_hashes_match_core_manifest() -> None:
    _require_bert_artifacts()
    import json

    bert_manifest = json.loads((BERT_RUN_DIR / "manifest.json").read_text(encoding="utf-8"))
    if not (CORE_RUN_DIR / "manifest.json").is_file():
        pytest.skip("Phase JA-4 Core run artifacts are not generated locally")
    core_manifest = json.loads((CORE_RUN_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert bert_manifest["data_hash"] == core_manifest["data_hash"]
    assert bert_manifest["fold_artifact_hash"] == core_manifest["fold_artifact_hash"]


def test_report_md_bert_metrics_match_audit_script_fold_means() -> None:
    """report.md's Chapter 8 required-metrics table must show exactly the
    fold-mean values this audit script independently recomputes -- not any
    other aggregation, and not a single fold's value."""
    _require_bert_artifacts()
    _require_report_artifacts()
    summary = audit_fold_metrics(BERT_RUN_DIR / "fold_metrics.csv")
    report_text = (REPORT_DIR / "report.md").read_text(encoding="utf-8")

    assert f"{summary['fold_mean_accuracy']:.3f}" in report_text
    assert f"{summary['fold_mean_macro_precision']:.3f}" in report_text
    assert f"{summary['fold_mean_macro_recall']:.3f}" in report_text
    assert f"{summary['fold_mean_macro_f1']:.3f}" in report_text

    # Regression guard for the specific value narrated (in error) in the
    # 2026-08-04 daily report log -- must never appear in the generated
    # report itself.
    assert "0.737" not in report_text


def test_report_md_confusion_matrix_sums_to_800() -> None:
    """Parse the actual BERT confusion-matrix Markdown table in Chapter 8 and
    verify its cells sum to 800, matching the audit script's own
    confusion_matrix_sum check on the same underlying OOF predictions."""
    _require_report_artifacts()
    report_text = (REPORT_DIR / "report.md").read_text(encoding="utf-8")
    section = report_text.split("混同行列（全800件のOOF予測を統合）")[1].split("考察")[0]

    total = 0
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("true \\ pred", "---"):
            continue
        row_values = [int(cell) for cell in cells[1:] if cell.isdigit()]
        if len(row_values) == 4:
            total += sum(row_values)

    assert total == 800


def test_no_manual_fixed_bert_values_hardcoded_in_generation_module() -> None:
    """The report-generation source must never contain a hardcoded literal
    match for the erroneous 0.737 figure."""
    generation_source = (
        ROOT / "src" / "mail_classification" / "reporting" / "ja_generation.py"
    ).read_text(encoding="utf-8")
    tables_source = (
        ROOT / "src" / "mail_classification" / "reporting" / "ja_tables.py"
    ).read_text(encoding="utf-8")
    assert "0.737" not in generation_source
    assert "0.737" not in tables_source
