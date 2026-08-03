"""Read-only Markdown table builders over already-written Core/Explain/Extension CSVs.

Every cell traces back to a value already on disk; nothing here re-derives or
hand-transcribes a number, and nothing here imports evaluation/explain/extensions
model-fitting code.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

CORE_CONDITIONS = ("D0", "D1", "D2")
CORE_MODELS = ("linear_svc", "logistic_regression")


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_metric_summary_table(run_dir: str | Path, metric: str) -> str:
    """Condition x model pivot of ``cv_mean +/- cv_std`` for one metrics_summary.csv metric."""
    rows = read_csv_rows(Path(run_dir) / "metrics_summary.csv")
    by_key = {(r["condition"], r["model"]): r for r in rows if r["metric"] == metric}
    if not by_key:
        raise ValueError(f"metric {metric!r} not found in {run_dir}/metrics_summary.csv")

    headers = ["condition", *CORE_MODELS]
    table_rows = []
    for condition in CORE_CONDITIONS:
        row = [condition]
        for model in CORE_MODELS:
            cell = by_key.get((condition, model))
            row.append(
                "n/a"
                if cell is None
                else f"{float(cell['cv_mean']):.3f} ± {float(cell['cv_std']):.3f}"
            )
        table_rows.append(row)
    return markdown_table(headers, table_rows)


def build_confusion_matrix_table(run_dir: str | Path, condition: str, model: str) -> str:
    rows = read_csv_rows(Path(run_dir) / "confusion_matrix.csv")
    cell_rows = [r for r in rows if r["condition"] == condition and r["model"] == model]
    if not cell_rows:
        raise ValueError(f"no confusion_matrix rows for condition={condition!r} model={model!r}")

    labels = sorted({r["true_label"] for r in cell_rows})
    counts = {(r["true_label"], r["predicted_label"]): r["count"] for r in cell_rows}
    headers = ["true \\ pred", *labels]
    table_rows = [
        [true_label, *(counts.get((true_label, pred_label), "0") for pred_label in labels)]
        for true_label in labels
    ]
    return markdown_table(headers, table_rows)


def build_paired_differences_table(
    run_dir: str | Path, *, baseline: str = "D0", metric: str = "macro_f1"
) -> str:
    rows = read_csv_rows(Path(run_dir) / "paired_differences.csv")
    filtered = [
        r for r in rows if r["baseline_condition"] == baseline and r["metric"] == metric
    ]
    if not filtered:
        raise ValueError(f"no paired_differences rows for baseline={baseline!r} metric={metric!r}")

    headers = ["condition", "model", "mean_diff", "std_diff", "n_improved", "n_worsened", "n_folds"]
    table_rows = [
        [
            r["condition"],
            r["model"],
            f"{float(r['mean_diff']):+.3f}",
            f"{float(r['std_diff']):.3f}",
            r["n_improved"],
            r["n_worsened"],
            r["n_folds"],
        ]
        for r in filtered
    ]
    return markdown_table(headers, table_rows)


def build_error_category_summary_table(explain_run_dir: str | Path) -> str:
    rows = read_csv_rows(Path(explain_run_dir) / "error_category_summary.csv")
    categories = sorted({r["primary_category"] for r in rows})
    by_cell: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        by_cell.setdefault((r["condition"], r["model"]), {})[r["primary_category"]] = int(
            r["count"]
        )

    headers = ["condition", "model", *categories, "total"]
    table_rows = []
    for condition in CORE_CONDITIONS:
        for model in CORE_MODELS:
            counts = by_cell.get((condition, model), {})
            row = [condition, model, *(str(counts.get(c, 0)) for c in categories)]
            row.append(str(sum(counts.values())))
            table_rows.append(row)
    return markdown_table(headers, table_rows)


def build_extension_summary_table(extension_run_dir: str | Path) -> str:
    summary = json.loads((Path(extension_run_dir) / "summary.json").read_text(encoding="utf-8"))
    headers = ["metric", "value"]
    rows = [[key.replace("_", " "), str(value)] for key, value in sorted(summary.items())]
    return markdown_table(headers, rows)


def build_class_distribution_table(quality_summary_path: str | Path) -> str:
    summary = json.loads(Path(quality_summary_path).read_text(encoding="utf-8"))
    headers = ["label", "count", "ratio"]
    rows = [
        [label, str(count), f"{summary['class_ratios'][label]:.2f}"]
        for label, count in sorted(summary["class_counts"].items())
    ]
    return markdown_table(headers, rows)
