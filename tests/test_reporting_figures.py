import csv
from pathlib import Path

import pytest

from mail_classification.reporting import figures, tables


def test_svg_bar_chart_basic() -> None:
    svg = figures.svg_bar_chart("My Title", ["A", "B"], {"series1": [0.5, 0.8]})

    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "My Title" in svg
    assert svg.count("<rect") >= 2  # one bar per group, at least


def test_svg_bar_chart_empty_group_labels_raises() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        figures.svg_bar_chart("Title", [], {"series1": []})


def test_svg_bar_chart_mismatched_series_length_raises() -> None:
    with pytest.raises(ValueError, match="series1"):
        figures.svg_bar_chart("Title", ["A", "B"], {"series1": [0.5]})


def _write_metrics_summary(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = ["condition", "model", "metric", "cv_mean", "cv_std", "n_folds"]
    rows = []
    for i, condition in enumerate(tables.CORE_CONDITIONS):
        for j, model in enumerate(tables.CORE_MODELS):
            rows.append(
                {
                    "condition": condition,
                    "model": model,
                    "metric": "macro_f1",
                    "cv_mean": str(0.5 + 0.01 * i + 0.02 * j),
                    "cv_std": "0.1",
                    "n_folds": "5",
                }
            )
    with (run_dir / "metrics_summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_macro_f1_comparison_svg(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_metrics_summary(run_dir)

    svg = figures.macro_f1_comparison_svg(run_dir)
    assert svg.startswith("<svg")
    for model in tables.CORE_MODELS:
        assert model in svg
    # one bar per condition x model cell
    assert svg.count("<rect") >= len(tables.CORE_CONDITIONS) * len(tables.CORE_MODELS)
