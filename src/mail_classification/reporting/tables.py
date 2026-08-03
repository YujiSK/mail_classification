"""Read-only Markdown table builders over already-written Core/Explain/Extension CSVs.

Every cell traces back to a value already on disk; nothing here re-derives or
hand-transcribes a number, and nothing here imports evaluation/explain/extensions
model-fitting code.
"""

from __future__ import annotations

import csv
from collections import Counter
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


def _validated_fold_imbalance_rows(
    analysis_path: str | Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = read_csv_rows(analysis_path)
    required = {
        "data_hash",
        "fold_artifact_hash",
        "fold_id",
        "label",
        "n_template_groups",
        "n_samples",
        "template_group_breakdown",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"invalid or empty fold imbalance artifact: {analysis_path}")
    if len({row["data_hash"] for row in rows}) != 1:
        raise ValueError("fold imbalance rows reference different data_hash values")
    if len({row["fold_artifact_hash"] for row in rows}) != 1:
        raise ValueError("fold imbalance rows reference different fold_artifact_hash values")

    label_rows = [row for row in rows if row["label"] != "ALL"]
    total_rows = [row for row in rows if row["label"] == "ALL"]
    if not label_rows or not total_rows:
        raise ValueError("fold imbalance artifact requires label rows and ALL total rows")
    return label_rows, total_rows


def build_fold_imbalance_table(analysis_path: str | Path) -> str:
    """Render the exact per-fold/per-label group identities and sample counts."""
    label_rows, _ = _validated_fold_imbalance_rows(analysis_path)
    rows = sorted(label_rows, key=lambda row: (int(row["fold_id"]), row["label"]))
    return markdown_table(
        ["fold", "label", "groups", "group breakdown", "samples"],
        [
            [
                row["fold_id"],
                row["label"],
                row["n_template_groups"],
                row["template_group_breakdown"],
                row["n_samples"],
            ]
            for row in rows
        ],
    )


def build_fold_imbalance_narrative(analysis_path: str | Path) -> str:
    """Build prose only from ``fold_imbalance_stats.csv`` values."""
    label_rows, total_rows = _validated_fold_imbalance_rows(analysis_path)
    group_cell_counts = Counter(int(row["n_template_groups"]) for row in label_rows)
    class_sample_counts = [int(row["n_samples"]) for row in label_rows]
    fold_totals = sorted(
        (
            int(row["fold_id"]),
            int(row["n_template_groups"]),
            int(row["n_samples"]),
        )
        for row in total_rows
    )
    multi_group_cells = sorted(
        (
            int(row["fold_id"]),
            row["label"],
            row["template_group_breakdown"],
            int(row["n_samples"]),
        )
        for row in label_rows
        if int(row["n_template_groups"]) > 1
    )

    group_distribution = "、".join(
        f"{group_count} group={cell_count}セル"
        for group_count, cell_count in sorted(group_cell_counts.items())
    )
    multi_detail = "、".join(
        f"fold {fold_id}/{label}={breakdown}（{samples}件）"
        for fold_id, label, breakdown, samples in multi_group_cells
    )
    fold_detail = "、".join(
        f"fold {fold_id}={groups} groups/{samples}件"
        for fold_id, groups, samples in fold_totals
    )
    fold_sample_counts = [samples for _, _, samples in fold_totals]

    return (
        f"`outputs/analysis/{Path(analysis_path).name}`の{len(label_rows)}個のfold×labelセルでは、"
        f"{group_distribution}だった。複数groupセルの内訳は{multi_detail}。"
        f"label別validation sample数は{min(class_sample_counts)}〜{max(class_sample_counts)}件、"
        f"fold全体は{fold_detail}で、最小{min(fold_sample_counts)}件・最大{max(fold_sample_counts)}件"
        "となった。"
    )


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


def build_structural_ratio_table(structural_ratio_comparison_path: str | Path) -> str:
    """Renders outputs/analysis/structural_ratio_comparison.json (population
    vs. misclassified ratio per structural flag, with a two-proportion z-test
    p-value; never claims significance itself, only reports the computed value)."""
    payload = json.loads(Path(structural_ratio_comparison_path).read_text(encoding="utf-8"))
    headers = [
        "flag",
        "population ratio",
        "misclassified ratio",
        "difference",
        "exceeds population",
        "p-value (two-proportion z)",
    ]
    table_rows = []
    for flag, stats in sorted(payload["flags"].items()):
        table_rows.append(
            [
                flag,
                f"{stats['population_ratio']:.3f}",
                f"{stats['misclassified_ratio']:.3f}",
                f"{stats['ratio_difference']:+.3f}",
                "Yes" if stats["exceeds_population_ratio"] else "No",
                f"{stats['two_proportion_z_p_value']:.3f}",
            ]
        )
    return markdown_table(headers, table_rows)


_SIGNIFICANCE_ALPHA = 0.05


def build_structural_ratio_narrative(structural_ratio_comparison_path: str | Path) -> str:
    """One paragraph, generated entirely from structural_ratio_comparison.json,
    stating for each flag whether the misclassified-subset ratio significantly
    exceeds the population ratio (two-proportion z-test at alpha=0.05)."""
    payload = json.loads(Path(structural_ratio_comparison_path).read_text(encoding="utf-8"))
    flags = payload["flags"]

    significant_exceed = sorted(
        flag
        for flag, stats in flags.items()
        if stats["exceeds_population_ratio"] and stats["two_proportion_z_p_value"] < _SIGNIFICANCE_ALPHA
    )
    not_significant = sorted(
        flag
        for flag, stats in flags.items()
        if flag not in significant_exceed
    )

    per_flag_detail = "、".join(
        f"{flag}: 母集団{flags[flag]['population_ratio']:.1%}／誤分類{flags[flag]['misclassified_ratio']:.1%}"
        f"（差{flags[flag]['ratio_difference']:+.1%}、p={flags[flag]['two_proportion_z_p_value']:.3f}）"
        for flag in sorted(flags)
    )

    if significant_exceed:
        conclusion = (
            f"{'、'.join(significant_exceed)}は誤分類における出現比率が母集団比率よりp<{_SIGNIFICANCE_ALPHA}で"
            "有意に高く、単なる母集団由来の頻度だけでは説明できないバイアスが示唆される。"
        )
    else:
        conclusion = (
            "いずれの構造要素も誤分類比率と母集団比率の差はp<"
            f"{_SIGNIFICANCE_ALPHA}で有意ではなく（"
            f"{'、'.join(not_significant)}）、構造要素の混入は母集団由来の頻度で説明可能な範囲であり、"
            "誤分類に特有の追加バイアスを生んでいるという根拠は本分析では確認されなかった。"
        )

    return (
        f"`outputs/analysis/{Path(structural_ratio_comparison_path).name}`（母集団{payload['population_total']}件、"
        f"誤分類{payload['misclassified_total']}件、{payload['misclassified_grain']}）による比較: "
        f"{per_flag_detail}。{conclusion}"
    )
