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
CONDITION_LABELS = {
    "D0": "D0（基本unigram条件）",
    "D1": "D1（bigram追加条件）",
    "D2": "D2（構造要素除去条件）",
}
MODEL_LABELS = {
    "linear_svc": "LinearSVC",
    "logistic_regression": "Logistic Regression",
}
CLASS_LABELS = ("account_support", "billing", "product_inquiry", "technical_issue")


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

    headers = ["条件", *(MODEL_LABELS[model] for model in CORE_MODELS)]
    table_rows = []
    for condition in CORE_CONDITIONS:
        row = [CONDITION_LABELS[condition]]
        for model in CORE_MODELS:
            cell = by_key.get((condition, model))
            row.append(
                "n/a"
                if cell is None
                else f"{float(cell['cv_mean']):.3f} ± {float(cell['cv_std']):.3f}"
            )
        table_rows.append(row)
    return markdown_table(headers, table_rows)


def read_core_required_metrics(
    run_dir: str | Path, condition: str, model: str
) -> dict[str, float]:
    """Read the assignment's four metrics for one Core cell from metrics_summary.csv."""
    rows = read_csv_rows(Path(run_dir) / "metrics_summary.csv")
    selected = {
        row["metric"]: float(row["cv_mean"])
        for row in rows
        if row["condition"] == condition and row["model"] == model
    }
    required = {"accuracy", "macro_f1"} | {
        f"{metric}_{label}"
        for metric in ("precision", "recall")
        for label in CLASS_LABELS
    }
    missing = required - selected.keys()
    if missing:
        raise ValueError(
            f"missing required metrics for condition={condition!r} model={model!r}: "
            f"{sorted(missing)}"
        )
    return {
        "Accuracy": selected["accuracy"],
        "Macro Precision": mean(selected[f"precision_{label}"] for label in CLASS_LABELS),
        "Macro Recall": mean(selected[f"recall_{label}"] for label in CLASS_LABELS),
        "Macro-F1": selected["macro_f1"],
    }


def build_core_required_metrics_table(run_dir: str | Path) -> str:
    """Render Accuracy, macro Precision/Recall/F1 for all six Core cells."""
    table_rows = []
    for condition in CORE_CONDITIONS:
        for model in CORE_MODELS:
            metrics = read_core_required_metrics(run_dir, condition, model)
            table_rows.append(
                [
                    CONDITION_LABELS[condition],
                    MODEL_LABELS[model],
                    *(f"{metrics[name]:.3f}" for name in metrics),
                ]
            )
    return markdown_table(
        ["条件", "モデル", "Accuracy", "Macro Precision", "Macro Recall", "Macro-F1"],
        table_rows,
    )


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

    headers = ["条件", "モデル", "平均差", "差の標準偏差", "改善Fold", "悪化Fold", "Fold数"]
    table_rows = [
        [
            CONDITION_LABELS[r["condition"]],
            MODEL_LABELS[r["model"]],
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


def build_error_category_percentage_table(explain_run_dir: str | Path) -> str:
    """Render each error category as count and within-cell percentage."""
    rows = read_csv_rows(Path(explain_run_dir) / "error_category_summary.csv")
    categories = sorted({r["primary_category"] for r in rows})
    by_cell: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        by_cell.setdefault((row["condition"], row["model"]), {})[
            row["primary_category"]
        ] = int(row["count"])

    table_rows = []
    for condition in CORE_CONDITIONS:
        for model in CORE_MODELS:
            counts = by_cell.get((condition, model), {})
            total = sum(counts.values())
            cells = [
                f"{counts.get(category, 0)} ({counts.get(category, 0) / total:.1%})"
                if total
                else "0 (0.0%)"
                for category in categories
            ]
            table_rows.append(
                [CONDITION_LABELS[condition], MODEL_LABELS[model], *cells, str(total)]
            )
    return markdown_table(["条件", "モデル", *categories, "誤分類数"], table_rows)


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


def build_fold_imbalance_brief_narrative(analysis_path: str | Path) -> str:
    """Concise main-text summary; detailed group identities remain in the appendix."""
    label_rows, total_rows = _validated_fold_imbalance_rows(analysis_path)
    group_counts = [int(row["n_template_groups"]) for row in label_rows]
    fold_counts = [int(row["n_samples"]) for row in total_rows]
    return (
        "テンプレートグループ数を5分割で均等に配分できないため、評価Foldの件数は"
        f"{min(fold_counts)}〜{max(fold_counts)}件となった。また、クラスごとの評価対象は"
        f"{min(group_counts)}〜{max(group_counts)}グループとなり、Foldごとの語彙構成に差が生じた。"
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

    headers = ["条件", "モデル", "macro-F1（平均 ± 標準偏差）"]
    table_rows = [
        [
            CONDITION_LABELS[condition],
            MODEL_LABELS[model],
            f"{float(by_key[(condition, model)]['cv_mean']):.3f} ± {float(by_key[(condition, model)]['cv_std']):.3f}",
        ]
        for condition in CORE_CONDITIONS
        for model in CORE_MODELS
    ]

    bert_mean, bert_std, _ = read_bert_fold_metric_cv(bert_run_dir, "f1_score")
    table_rows.append(
        ["発展実験", "DistilBERT（ファインチューニング）", f"{bert_mean:.3f} ± {bert_std:.3f}"]
    )

    return markdown_table(headers, table_rows)


def build_bert_required_metrics_table(core_dir: str | Path, bert_run_dir: str | Path) -> str:
    """Compare the best Core model (D1/LinearSVC) with DistilBERT."""
    required_core_metrics = read_core_required_metrics(core_dir, "D1", "linear_svc")
    bert_columns = {
        "Accuracy": "accuracy",
        "Macro Precision": "precision",
        "Macro Recall": "recall",
        "Macro-F1": "f1_score",
    }
    rows = []
    for metric, bert_column in bert_columns.items():
        bert_mean, _, _ = read_bert_fold_metric_cv(bert_run_dir, bert_column)
        rows.append([metric, f"{required_core_metrics[metric]:.3f}", f"{bert_mean:.3f}"])
    return markdown_table(
        ["指標", "D1（bigram追加条件）＋LinearSVC", "DistilBERT（ファインチューニング）"],
        rows,
    )


def build_structural_ratio_table(structural_ratio_comparison_path: str | Path) -> str:
    """Render descriptive population/misclassification ratios without inferential p-values."""
    payload = json.loads(Path(structural_ratio_comparison_path).read_text(encoding="utf-8"))
    headers = [
        "flag",
        "population ratio",
        "misclassified ratio",
        "difference",
        "exceeds population",
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
            ]
        )
    return markdown_table(headers, table_rows)


def build_structural_ratio_narrative(structural_ratio_comparison_path: str | Path) -> str:
    """Describe ratios only; repeated sample IDs invalidate an independence claim."""
    payload = json.loads(Path(structural_ratio_comparison_path).read_text(encoding="utf-8"))
    flags = payload["flags"]

    per_flag_detail = "、".join(
        f"{flag}: 母集団{flags[flag]['population_ratio']:.1%}／誤分類{flags[flag]['misclassified_ratio']:.1%}"
        f"（差{flags[flag]['ratio_difference']:+.1%}）"
        for flag in sorted(flags)
    )
    return (
        f"母集団{payload['population_total']}件、誤分類{payload['misclassified_total']}行による記述的比較: "
        f"{per_flag_detail}。誤分類データは同一sample_idを条件・モデル別に反復して含むため、"
        "各行を独立観測とみなす推測統計は適用せず、有意差の主張は行わない。"
    )
