"""Japanese counterpart of ``figures.py``. ``svg_bar_chart`` itself is fully
generic and reused unmodified; only the J0-JC condition set differs."""

from __future__ import annotations

from pathlib import Path

from .figures import svg_bar_chart
from .ja_tables import JA_CORE_CONDITIONS, JA_CORE_MODELS
from .tables import read_csv_rows


def macro_f1_comparison_svg_ja(core_run_dir: str | Path) -> str:
    rows = read_csv_rows(Path(core_run_dir) / "metrics_summary.csv")
    by_key = {
        (r["condition"], r["model"]): float(r["cv_mean"])
        for r in rows
        if r["metric"] == "macro_f1"
    }
    series = {
        model: [by_key[(condition, model)] for condition in JA_CORE_CONDITIONS]
        for model in JA_CORE_MODELS
    }
    return svg_bar_chart(
        "Task10-JA Core macro-F1 (cv_mean) by condition and model",
        list(JA_CORE_CONDITIONS),
        series,
        y_max=1.0,
    )
