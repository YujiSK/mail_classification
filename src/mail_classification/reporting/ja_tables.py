"""Japanese counterpart of ``tables.py``.

Most of ``tables.py``'s functions are already fully generic (they take a
``run_dir``/metric name and never hardcode a condition set), so they are
reused directly by import: ``build_confusion_matrix_table``,
``build_error_category_percentage_table`` (categories are discovered from
the file itself via ``sorted({row["primary_category"] ...})``, not
hardcoded), ``build_extension_summary_table``, ``build_class_distribution_table``,
``best_core_metric_cell``, ``read_bert_fold_metric_cv``. Only the handful of
functions that hardcode ``CORE_CONDITIONS = ("D0", "D1", "D2")`` need a J0-JC
counterpart here.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from .tables import CLASS_LABELS, MODEL_LABELS, markdown_table, read_csv_rows

# NOTE: tables.py's build_error_category_percentage_table also hardcodes
# CORE_CONDITIONS/CORE_MODELS (D0-D2) in its row-iteration loop, not only in
# category discovery -- caught by rendering a real preview PDF page and
# reading it, where the table showed "D0"/"D1"/"D2" rows all at 0 counts
# instead of J0-JC. It is therefore NOT safe to reuse directly for JA; see
# build_error_category_percentage_table_ja below.

JA_CORE_CONDITIONS = ("J0", "J1", "J2", "JC")
JA_CORE_MODELS = ("linear_svc", "logistic_regression")
JA_CONDITION_LABELS = {
    "J0": "J0（日本語基本unigram条件）",
    "J1": "J1（word bigram追加条件）",
    "J2": "J2（構造要素除去条件）",
    "JC": "JC（文字n-gram基準条件）",
}


def build_metric_summary_table_ja(run_dir: str | Path, metric: str) -> str:
    rows = read_csv_rows(Path(run_dir) / "metrics_summary.csv")
    by_key = {(r["condition"], r["model"]): r for r in rows if r["metric"] == metric}
    if not by_key:
        raise ValueError(f"metric {metric!r} not found in {run_dir}/metrics_summary.csv")

    headers = ["条件", *(MODEL_LABELS[model] for model in JA_CORE_MODELS)]
    table_rows = []
    for condition in JA_CORE_CONDITIONS:
        row = [JA_CONDITION_LABELS[condition]]
        for model in JA_CORE_MODELS:
            cell = by_key.get((condition, model))
            row.append(
                "n/a"
                if cell is None
                else f"{float(cell['cv_mean']):.3f} ± {float(cell['cv_std']):.3f}"
            )
        table_rows.append(row)
    return markdown_table(headers, table_rows)


def read_core_required_metrics_ja(run_dir: str | Path, condition: str, model: str) -> dict[str, float]:
    rows = read_csv_rows(Path(run_dir) / "metrics_summary.csv")
    selected = {
        row["metric"]: float(row["cv_mean"])
        for row in rows
        if row["condition"] == condition and row["model"] == model
    }
    required = {"accuracy", "macro_f1"} | {
        f"{metric}_{label}" for metric in ("precision", "recall") for label in CLASS_LABELS
    }
    missing = required - selected.keys()
    if missing:
        raise ValueError(
            f"missing required metrics for condition={condition!r} model={model!r}: {sorted(missing)}"
        )
    return {
        "Accuracy": selected["accuracy"],
        "Macro Precision": mean(selected[f"precision_{label}"] for label in CLASS_LABELS),
        "Macro Recall": mean(selected[f"recall_{label}"] for label in CLASS_LABELS),
        "Macro-F1": selected["macro_f1"],
    }


def build_core_required_metrics_table_ja(run_dir: str | Path) -> str:
    table_rows = []
    for condition in JA_CORE_CONDITIONS:
        for model in JA_CORE_MODELS:
            metrics = read_core_required_metrics_ja(run_dir, condition, model)
            table_rows.append(
                [
                    JA_CONDITION_LABELS[condition],
                    MODEL_LABELS[model],
                    *(f"{metrics[name]:.3f}" for name in metrics),
                ]
            )
    return markdown_table(
        ["条件", "モデル", "Accuracy", "Macro Precision", "Macro Recall", "Macro-F1"],
        table_rows,
    )


def build_paired_differences_table_ja(
    run_dir: str | Path, *, baseline: str = "J0", metric: str = "macro_f1"
) -> str:
    rows = read_csv_rows(Path(run_dir) / "paired_differences.csv")
    filtered = [r for r in rows if r["baseline_condition"] == baseline and r["metric"] == metric]
    if not filtered:
        raise ValueError(f"no paired_differences rows for baseline={baseline!r} metric={metric!r}")

    headers = ["条件", "モデル", "平均差", "差の標準偏差", "改善Fold", "悪化Fold", "Fold数"]
    table_rows = [
        [
            JA_CONDITION_LABELS[r["condition"]],
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


def read_paired_diff_mean_ja(
    run_dir: str | Path, condition: str, model: str, *, baseline: str = "J0", metric: str = "macro_f1"
) -> float:
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


_SHORT_CATEGORY_LABELS = {
    "ambiguous_difficulty": "曖昧度",
    "mixed_ja_en": "日英混在",
    "morphological_segmentation": "分割境界",
    "multi_intent": "多重意図",
    "negation_present": "否定表現",
    "orthographic_variation": "表記ゆれ",
    "structural_content": "構造要素",
    "uncategorized": "未分類",
}
_SHORT_MODEL_LABELS = {"linear_svc": "SVC", "logistic_regression": "LR"}


def build_error_category_percentage_table_ja(explain_run_dir: str | Path) -> str:
    """JA counterpart of tables.build_error_category_percentage_table, using
    JA_CORE_CONDITIONS/JA_CORE_MODELS instead of the English D0-D2 set."""
    rows = read_csv_rows(Path(explain_run_dir) / "error_category_summary.csv")
    categories = sorted({r["primary_category"] for r in rows})
    by_cell: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        by_cell.setdefault((row["condition"], row["model"]), {})[row["primary_category"]] = int(
            row["count"]
        )

    table_rows = []
    for condition in JA_CORE_CONDITIONS:
        for model in JA_CORE_MODELS:
            counts = by_cell.get((condition, model), {})
            total = sum(counts.values())
            cells = [
                f"{counts.get(category, 0)} ({counts.get(category, 0) / total:.1%})"
                if total
                else "0 (0.0%)"
                for category in categories
            ]
            table_rows.append(
                [JA_CONDITION_LABELS[condition], MODEL_LABELS[model], *cells, str(total)]
            )
    return markdown_table(["条件", "モデル", *categories, "誤分類数"], table_rows)


def build_error_category_counts_table(explain_run_dir: str | Path) -> str:
    """JA-only: render error_category_counts.csv, which allows a row to match
    more than one category (unlike error_category_summary.csv's single pick).

    Percentage-only cells and abbreviated headers (condition+model merged into
    one column, category names shortened) keep the 10-column table from
    overflowing the PDF page width -- caught by rendering and visually
    inspecting a preview PDF page, not by the automated layout checker, which
    does not detect horizontal table overflow (a documented heuristic gap
    also noted in the English track's own report tooling).
    """
    rows = read_csv_rows(Path(explain_run_dir) / "error_category_counts.csv")
    categories = sorted({r["category"] for r in rows})
    by_cell: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        by_cell.setdefault((row["condition"], row["model"]), {})[row["category"]] = float(
            row["share_of_misclassified"]
        )

    table_rows = []
    for condition in JA_CORE_CONDITIONS:
        for model in JA_CORE_MODELS:
            shares = by_cell.get((condition, model), {})
            cells = [f"{shares.get(category, 0.0):.0%}" for category in categories]
            table_rows.append([f"{condition}/{_SHORT_MODEL_LABELS[model]}", *cells])
    headers = ["条件/モデル", *(_SHORT_CATEGORY_LABELS.get(c, c) for c in categories)]
    return markdown_table(headers, table_rows)


def build_bert_comparison_table_ja(core_dir: str | Path, bert_fold_metrics_path: str | Path) -> str:
    """Core's own macro-F1 table (all 8 J0-JC x model cells) with the BERT row appended."""
    core_rows = read_csv_rows(Path(core_dir) / "metrics_summary.csv")
    by_key = {(r["condition"], r["model"]): r for r in core_rows if r["metric"] == "macro_f1"}

    headers = ["条件", "モデル", "macro-F1（平均 ± 標準偏差）"]
    table_rows = [
        [
            JA_CONDITION_LABELS[condition],
            MODEL_LABELS[model],
            f"{float(by_key[(condition, model)]['cv_mean']):.3f} ± {float(by_key[(condition, model)]['cv_std']):.3f}",
        ]
        for condition in JA_CORE_CONDITIONS
        for model in JA_CORE_MODELS
    ]

    bert_rows = read_csv_rows(bert_fold_metrics_path)
    values = [float(r["macro_f1"]) for r in bert_rows]
    from statistics import pstdev

    bert_mean = mean(values)
    bert_std = pstdev(values) if len(values) > 1 else 0.0
    table_rows.append(
        ["発展実験", "BERT（tohoku-nlp/bert-base-japanese-v3、ファインチューニング）", f"{bert_mean:.3f} ± {bert_std:.3f}"]
    )
    return markdown_table(headers, table_rows)


def build_bert_required_metrics_table_ja(
    core_dir: str | Path, bert_fold_metrics_path: str | Path, *, best_condition: str, best_model: str
) -> str:
    required_core_metrics = read_core_required_metrics_ja(core_dir, best_condition, best_model)
    bert_rows = read_csv_rows(bert_fold_metrics_path)
    bert_columns = {
        "Accuracy": "accuracy",
        "Macro Precision": "macro_precision",
        "Macro Recall": "macro_recall",
        "Macro-F1": "macro_f1",
    }
    table_rows = []
    for metric, column in bert_columns.items():
        values = [float(r[column]) for r in bert_rows]
        table_rows.append([metric, f"{required_core_metrics[metric]:.3f}", f"{mean(values):.3f}"])
    return markdown_table(
        [
            "指標",
            f"{JA_CONDITION_LABELS[best_condition]}＋{MODEL_LABELS[best_model]}",
            "BERT（ファインチューニング）",
        ],
        table_rows,
    )


def build_bert_confusion_matrix_table(bert_oof_path: str | Path) -> str:
    rows = read_csv_rows(bert_oof_path)
    labels = sorted({r["true_label"] for r in rows})
    from collections import Counter

    counts = Counter((r["true_label"], r["predicted_label"]) for r in rows)
    headers = ["true \\ pred", *labels]
    table_rows = [
        [true_label, *(str(counts.get((true_label, pred_label), 0)) for pred_label in labels)]
        for true_label in labels
    ]
    return markdown_table(headers, table_rows)
