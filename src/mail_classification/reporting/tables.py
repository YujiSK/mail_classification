"""Read-only Markdown table builders over already-written Core/Explain/Extension CSVs.

Every cell traces back to a value already on disk; nothing here re-derives or
hand-transcribes a number, and nothing here imports evaluation/explain/extensions
model-fitting code.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, pstdev

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


def read_paired_diff_mean(
    run_dir: str | Path, condition: str, model: str, *, baseline: str = "D0", metric: str = "macro_f1"
) -> float:
    """Fetch a single mean_diff cell from paired_differences.csv, for prose that cites it."""
    rows = read_csv_rows(Path(run_dir) / "paired_differences.csv")
    for r in rows:
        if (
            r["baseline_condition"] == baseline
            and r["condition"] == condition
            and r["model"] == model
            and r["metric"] == metric
        ):
            return float(r["mean_diff"])
    raise ValueError(
        f"no paired_differences row for baseline={baseline!r} condition={condition!r} "
        f"model={model!r} metric={metric!r}"
    )


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


def verify_bert_alignment(
    bert_run_dir: str | Path, fold_artifact_path: str | Path, expected_data_hash: str
) -> None:
    """Fail fast unless the external BERT run used the same Full dataset and the
    same common-Fold validation split as Core (never trust an external, non
    fail-fast-verified artifact at face value)."""
    bert_run_dir = Path(bert_run_dir)
    manifest = json.loads((bert_run_dir / "execution_manifest.json").read_text(encoding="utf-8"))
    if manifest["actual_data_hash"] != expected_data_hash:
        raise ValueError(
            f"BERT run data_hash {manifest['actual_data_hash']!r} does not match "
            f"Core's data_hash {expected_data_hash!r}"
        )

    oof_rows = read_csv_rows(bert_run_dir / "bert_oof_predictions.csv")
    fold_artifact = json.loads(Path(fold_artifact_path).read_text(encoding="utf-8"))
    validation_fold_by_id = {
        rec["sample_id"]: rec["fold_id"]
        for rec in fold_artifact["records"]
        if rec["split_role"] == "validation"
    }

    missing = [r["sample_id"] for r in oof_rows if r["sample_id"] not in validation_fold_by_id]
    if missing:
        raise ValueError(
            f"{len(missing)} BERT OOF sample_id(s) are not in the common Fold artifact: "
            f"{missing[:5]}"
        )

    mismatched = [
        (r["sample_id"], validation_fold_by_id[r["sample_id"]], r["fold_id"])
        for r in oof_rows
        if str(validation_fold_by_id[r["sample_id"]]) != str(r["fold_id"])
    ]
    if mismatched:
        raise ValueError(
            f"{len(mismatched)} BERT OOF row(s) use a different fold_id than the common "
            f"Fold artifact's validation assignment: {mismatched[:5]}"
        )

    covered = {r["sample_id"] for r in oof_rows}
    uncovered = set(validation_fold_by_id) - covered
    if uncovered:
        raise ValueError(
            f"{len(uncovered)} common-Fold sample_id(s) are missing from the BERT OOF "
            f"predictions (incomplete coverage)"
        )


def read_bert_fold_metric_cv(bert_run_dir: str | Path, metric_column: str) -> tuple[float, float, int]:
    """cv_mean/cv_std/n_folds for one bert_fold_metrics.csv column, computed the same
    way (statistics.mean/pstdev over per-fold values) as Core's build_metrics_summary."""
    rows = read_csv_rows(Path(bert_run_dir) / "bert_fold_metrics.csv")
    values = [float(r[metric_column]) for r in rows]
    if not values:
        raise ValueError(f"bert_fold_metrics.csv has no rows to aggregate column {metric_column!r}")
    return mean(values), (pstdev(values) if len(values) > 1 else 0.0), len(values)


def best_core_metric_cell(core_dir: str | Path, metric: str) -> tuple[str, str, float]:
    """(condition, model, cv_mean) for the Core cell with the highest cv_mean of metric."""
    rows = read_csv_rows(Path(core_dir) / "metrics_summary.csv")
    candidates = [
        (float(r["cv_mean"]), r["condition"], r["model"]) for r in rows if r["metric"] == metric
    ]
    if not candidates:
        raise ValueError(f"metric {metric!r} not found in {core_dir}/metrics_summary.csv")
    best_value, condition, model = max(candidates)
    return condition, model, best_value


def build_bert_comparison_table(core_dir: str | Path, bert_run_dir: str | Path) -> str:
    """Core's own macro-F1 cv_mean/cv_std table (all 6 D0-D2 x model cells) with the
    externally fine-tuned DistilBERT row appended, computed via the same aggregation."""
    core_rows = read_csv_rows(Path(core_dir) / "metrics_summary.csv")
    by_key = {
        (r["condition"], r["model"]): r for r in core_rows if r["metric"] == "macro_f1"
    }

    headers = ["condition", "model", "macro_f1 (cv_mean ± cv_std)"]
    table_rows = [
        [
            condition,
            model,
            f"{float(by_key[(condition, model)]['cv_mean']):.3f} ± {float(by_key[(condition, model)]['cv_std']):.3f}",
        ]
        for condition in CORE_CONDITIONS
        for model in CORE_MODELS
    ]

    bert_mean, bert_std, _ = read_bert_fold_metric_cv(bert_run_dir, "f1_score")
    table_rows.append(["Extension", "DistilBERT (fine-tuned)", f"{bert_mean:.3f} ± {bert_std:.3f}"])

    return markdown_table(headers, table_rows)


def build_bert_required_metrics_table(core_dir: str | Path, bert_run_dir: str | Path) -> str:
    """Compare the assignment's four required metrics for D2/LinearSVC and BERT.

    Core macro precision/recall are derived by averaging the four classwise
    ``cv_mean`` values. BERT values are means of its five fold rows. No report
    value is embedded as a literal.
    """
    core_rows = read_csv_rows(Path(core_dir) / "metrics_summary.csv")
    selected = {
        row["metric"]: float(row["cv_mean"])
        for row in core_rows
        if row["condition"] == "D2" and row["model"] == "linear_svc"
    }
    labels = ("account_support", "billing", "product_inquiry", "technical_issue")
    required_core_metrics = {
        "Accuracy": selected["accuracy"],
        "Precision (macro)": mean(selected[f"precision_{label}"] for label in labels),
        "Recall (macro)": mean(selected[f"recall_{label}"] for label in labels),
        "Macro-F1": selected["macro_f1"],
    }
    bert_columns = {
        "Accuracy": "accuracy",
        "Precision (macro)": "precision",
        "Recall (macro)": "recall",
        "Macro-F1": "f1_score",
    }
    rows = []
    for metric, bert_column in bert_columns.items():
        bert_mean, _, _ = read_bert_fold_metric_cv(bert_run_dir, bert_column)
        rows.append([metric, f"{required_core_metrics[metric]:.3f}", f"{bert_mean:.3f}"])
    return markdown_table(
        ["metric", "TF-IDF + LinearSVC (D2)", "DistilBERT (fine-tuned)"], rows
    )
