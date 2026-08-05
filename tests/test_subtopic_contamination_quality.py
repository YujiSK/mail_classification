"""Checks against the real-data run's already-written artifacts.

Guarded with a skip (matching the existing ``test_extensions_runner.py``/
``test_minhash.py`` real-data-smoke convention) so this suite still passes
in an environment without the generated Full dataset or this Extension's
run directory, while giving a strong end-to-end check wherever both exist.
"""

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RUN_DIR = ROOT / "outputs" / "extensions" / "phase-subtopic-contamination-seed42"


def _skip_unless_run_exists() -> None:
    if not RUN_DIR.is_dir():
        pytest.skip(f"{RUN_DIR} was not generated locally")


def _read_csv(name: str) -> list[dict[str, str]]:
    with (RUN_DIR / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_condition_statistics_reports_800_records_and_200_per_class() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("condition_statistics.csv")

    for level in ("C0", "C10", "C20", "C30"):
        total_row = next(
            r for r in rows if r["level"] == level and r["category"] == "total_count"
        )
        assert int(total_row["value"]) == 800

        class_rows = [r for r in rows if r["level"] == level and r["category"] == "class_counts"]
        assert len(class_rows) == 4
        assert all(int(r["value"]) == 200 for r in class_rows)


def test_condition_statistics_contamination_rate_matches_level() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("condition_statistics.csv")
    expected = {"C0": 0.0, "C10": 0.10, "C20": 0.20, "C30": 0.30}
    for level, fraction in expected.items():
        ratio_row = next(
            r
            for r in rows
            if r["level"] == level and r["category"] == "contamination_rate" and r["key"] == "contaminated_ratio"
        )
        assert abs(float(ratio_row["value"]) - fraction) < 1e-9


def test_condition_statistics_duplicate_counts_are_zero() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("condition_statistics.csv")
    for row in rows:
        if row["category"] == "duplicates":
            assert int(row["value"]) == 0, row


def test_predictions_oof_has_no_missing_or_duplicate_coverage() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("predictions_oof.csv")
    assert len(rows) == 4 * 4 * 800  # 4 levels x 4 (condition, model) cells x 800 samples

    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (row["contamination_level"], row["condition"], row["model"], row["sample_id"])
        assert key not in seen, f"duplicate OOF row: {key}"
        seen.add(key)

    cells = {(row["contamination_level"], row["condition"], row["model"]) for row in rows}
    assert len(cells) == 16
    sample_ids = {row["sample_id"] for row in rows}
    assert len(sample_ids) == 800


def test_paired_differences_cover_every_non_c0_level_and_cell() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("paired_differences.csv")
    levels = {row["level"] for row in rows}
    assert levels == {"C10", "C20", "C30"}
    cells = {(row["condition"], row["model"]) for row in rows}
    assert cells == {
        ("D0", "linear_svc"),
        ("D1", "linear_svc"),
        ("D1", "logistic_regression"),
        ("D2", "linear_svc"),
    }


def test_main_subtopic_pair_summary_covers_all_12_pairs_per_level_and_cell() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("main_subtopic_pair_summary.csv")
    for level in ("C10", "C20", "C30"):
        for condition, model in (
            ("D0", "linear_svc"),
            ("D1", "linear_svc"),
            ("D1", "logistic_regression"),
            ("D2", "linear_svc"),
        ):
            cell_rows = [
                r
                for r in rows
                if r["level"] == level and r["condition"] == condition and r["model"] == model
            ]
            pairs = {(r["main_label"], r["subtopic_label"]) for r in cell_rows}
            assert len(pairs) == 12, (level, condition, model)


def test_misclassifications_have_decision_score_evidence_columns() -> None:
    _skip_unless_run_exists()
    rows = _read_csv("misclassifications.csv")
    assert rows
    required = {
        "decision_score_account_support",
        "decision_score_billing",
        "decision_score_product_inquiry",
        "decision_score_technical_issue",
        "predicted_top_features",
        "true_top_features",
        "pulled_to_subtopic",
    }
    assert required <= set(rows[0].keys())


def test_statistical_tests_json_has_paired_caveats() -> None:
    _skip_unless_run_exists()
    payload = json.loads((RUN_DIR / "statistical_tests.json").read_text(encoding="utf-8"))
    assert payload["mcnemar"]
    assert payload["paired_bootstrap"]
    for entry in payload["mcnemar"]:
        assert "caveat" in entry
    for entry in payload["paired_bootstrap"]:
        assert "caveat" in entry


def test_manifest_json_and_summary_json_are_consistent() -> None:
    _skip_unless_run_exists()
    manifest = json.loads((RUN_DIR / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((RUN_DIR / "summary.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "phase-subtopic-contamination-seed42"
    assert summary["contamination_counts"]["C30"] == 240
    assert summary["contamination_counts"]["C0"] == 0
