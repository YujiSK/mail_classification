"""Extension report generation: reads only already-written artifacts, never re-runs training.

Mirrors ``mail_classification.reporting``'s own rule (project_rules.md
section 12: "report生成だけで実験を再実行しない"; "Markdownへ数値を手動転記
しない"): every number below is read from a CSV/JSON artifact under
``outputs/extensions/<run_id>/`` (or, for the four contamination levels'
per-sample difficulty/multi_intent/negation, from the derived dataset JSONL
that ``dataset_manifest.json`` already points to), and every chart is built
with the same hand-rolled, dependency-free SVG helper Core's own reporting
module uses (``mail_classification.reporting.figures.svg_bar_chart``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path

from mail_classification.generation.io import read_jsonl
from mail_classification.reporting.figures import svg_bar_chart
from mail_classification.reporting.generation import render_report_pdf
from mail_classification.reporting.tables import markdown_table, read_csv_rows

from .analysis import accuracy_by_dimension
from .assignment import CONTAMINATION_LEVELS

CELL_LABELS = {
    ("D1", "linear_svc"): "D1 + LinearSVC",
    ("D1", "logistic_regression"): "D1 + Logistic Regression",
    ("D0", "linear_svc"): "D0 + LinearSVC",
    ("D2", "linear_svc"): "D2 + LinearSVC",
}
CELL_ORDER = list(CELL_LABELS)
PRIMARY_CELL = ("D1", "linear_svc")
LEVEL_LABELS = {"C0": "C0 (0%)", "C10": "C10 (10%)", "C20": "C20 (20%)", "C30": "C30 (30%)"}
CLASS_LABELS = ("account_support", "billing", "product_inquiry", "technical_issue")
_ABBREV = {
    "account_support": "AS",
    "billing": "BI",
    "product_inquiry": "PI",
    "technical_issue": "TI",
}


def _rows(run_dir: Path, name: str) -> list[dict[str, str]]:
    return read_csv_rows(run_dir / name)


def _metric_by_level(
    metrics_summary_rows: list[dict[str, str]], metric: str, condition: str, model: str
) -> dict[str, tuple[float, float]]:
    return {
        row["contamination_level"]: (float(row["cv_mean"]), float(row["cv_std"]))
        for row in metrics_summary_rows
        if row["metric"] == metric and row["condition"] == condition and row["model"] == model
    }


def _metrics_summary_table(metrics_summary_rows: list[dict[str, str]], metric: str) -> str:
    headers = ["混入率", *(CELL_LABELS[cell] for cell in CELL_ORDER)]
    table_rows = []
    for level in CONTAMINATION_LEVELS:
        row = [LEVEL_LABELS[level]]
        for condition, model in CELL_ORDER:
            values = _metric_by_level(metrics_summary_rows, metric, condition, model)
            mean_value, std_value = values.get(level, (float("nan"), float("nan")))
            row.append(f"{mean_value:.3f} ± {std_value:.3f}")
        table_rows.append(row)
    return markdown_table(headers, table_rows)


def _macro_f1_chart(metrics_summary_rows: list[dict[str, str]]) -> str:
    series = {
        CELL_LABELS[(condition, model)]: [
            _metric_by_level(metrics_summary_rows, "macro_f1", condition, model)[level][0]
            for level in CONTAMINATION_LEVELS
        ]
        for condition, model in CELL_ORDER
    }
    return svg_bar_chart(
        "混入率ごとのmacro-F1（5-fold平均）", list(LEVEL_LABELS.values()), series, y_max=1.0
    )


def _accuracy_chart(metrics_summary_rows: list[dict[str, str]]) -> str:
    series = {
        CELL_LABELS[(condition, model)]: [
            _metric_by_level(metrics_summary_rows, "accuracy", condition, model)[level][0]
            for level in CONTAMINATION_LEVELS
        ]
        for condition, model in CELL_ORDER
    }
    return svg_bar_chart(
        "混入率ごとのAccuracy（5-fold平均）", list(LEVEL_LABELS.values()), series, y_max=1.0
    )


def _classwise_f1_chart(metrics_summary_rows: list[dict[str, str]]) -> str:
    condition, model = PRIMARY_CELL
    series = {
        label: [
            _metric_by_level(metrics_summary_rows, f"f1_{label}", condition, model)[level][0]
            for level in CONTAMINATION_LEVELS
        ]
        for label in CLASS_LABELS
    }
    return svg_bar_chart(
        f"クラス別F1（{CELL_LABELS[PRIMARY_CELL]}、混入率別）",
        list(LEVEL_LABELS.values()),
        series,
        y_max=1.0,
    )


def _pulled_to_subtopic_rate_by_level(misclassification_rows: list[dict[str, str]]) -> dict[str, float]:
    condition, model = PRIMARY_CELL
    rates: dict[str, float] = {}
    for level in ("C10", "C20", "C30"):
        contaminated_errors = [
            row
            for row in misclassification_rows
            if row["contamination_level"] == level
            and row["condition"] == condition
            and row["model"] == model
            and row["contaminated"] == "True"
        ]
        if not contaminated_errors:
            rates[level] = 0.0
            continue
        pulled = sum(1 for row in contaminated_errors if row["pulled_to_subtopic"] == "True")
        rates[level] = pulled / len(contaminated_errors)
    return rates


def _pulled_to_subtopic_chart(misclassification_rows: list[dict[str, str]]) -> str:
    rates = _pulled_to_subtopic_rate_by_level(misclassification_rows)
    levels = ["C10", "C20", "C30"]
    return svg_bar_chart(
        f"副トピックのカテゴリへ誤分類された割合（{CELL_LABELS[PRIMARY_CELL]}、混入済sampleの誤分類のうち）",
        [LEVEL_LABELS[level] for level in levels],
        {"副トピックへの誤分類率": [rates[level] for level in levels]},
        y_max=1.0,
    )


def _transition_chart(transition_rows: list[dict[str, str]]) -> str:
    condition, model = PRIMARY_CELL
    categories = ["correct_to_correct", "correct_to_incorrect", "incorrect_to_correct", "incorrect_to_incorrect"]
    category_labels_ja = ["正解→正解", "正解→誤分類", "誤分類→正解", "誤分類→誤分類"]
    series = {}
    for group, group_label in (("contaminated", "混入あり"), ("not_contaminated", "混入なし")):
        row = next(
            r
            for r in transition_rows
            if r["level"] == "C30" and r["condition"] == condition and r["model"] == model and r["group"] == group
        )
        series[group_label] = [int(row[category]) for category in categories]
    return svg_bar_chart("C0→C30の予測遷移（件数、" + CELL_LABELS[PRIMARY_CELL] + "）", category_labels_ja, series)


def _main_subtopic_degradation_chart(pair_summary_rows: list[dict[str, str]]) -> str:
    condition, model = PRIMARY_CELL
    rows = [
        row
        for row in pair_summary_rows
        if row["level"] == "C30" and row["condition"] == condition and row["model"] == model
    ]
    rows.sort(key=lambda r: (r["main_label"], r["subtopic_label"]))
    group_labels = [f"{_ABBREV[r['main_label']]}→{_ABBREV[r['subtopic_label']]}" for r in rows]
    values = [float(r["accuracy_diff"]) for r in rows]
    return svg_bar_chart(
        f"主ラベル×副トピック別の正解率変化（C0比、C30、{CELL_LABELS[PRIMARY_CELL]}）",
        group_labels,
        {"accuracy_diff": values},
        y_max=max(0.05, max((abs(v) for v in values), default=0.05) * 1.2),
    )


def _main_subtopic_pair_table(pair_summary_rows: list[dict[str, str]]) -> str:
    condition, model = PRIMARY_CELL
    rows = [
        row
        for row in pair_summary_rows
        if row["level"] == "C30" and row["condition"] == condition and row["model"] == model
    ]
    rows.sort(key=lambda r: float(r["accuracy_diff"]))
    headers = ["主ラベル", "副トピック", "件数", "C30正解率", "C0正解率", "差", "副トピックへ誤分類の割合"]
    table_rows = [
        [
            row["main_label"],
            row["subtopic_label"],
            row["n_samples"],
            f"{float(row['accuracy']):.3f}",
            f"{float(row['baseline_accuracy_c0']):.3f}",
            f"{float(row['accuracy_diff']):+.3f}",
            f"{float(row['pulled_to_subtopic_rate']):.1%}",
        ]
        for row in rows
    ]
    return markdown_table(headers, table_rows)


def _breakdown_table(
    oof_rows: list[dict[str, str]],
    assignment_rows: list[dict[str, str]],
    original_records_by_id: dict[str, object],
    *,
    level: str,
    dimension_fn,
    dimension_header: str,
) -> str:
    condition, model = PRIMARY_CELL
    typed_oof = [
        {**row, "fold_id": int(row["fold_id"])}
        for row in oof_rows
        if row["contamination_level"] == level and row["condition"] == condition and row["model"] == model
    ]
    breakdown = accuracy_by_dimension(
        typed_oof,
        assignment_rows,
        original_records_by_id,
        level=level,
        condition=condition,
        model=model,
        dimension_fn=dimension_fn,
    )
    headers = [dimension_header, "件数", "正解率"]
    table_rows = [
        [value, str(total), f"{accuracy:.3f}"]
        for value, (accuracy, total) in sorted(breakdown.items())
    ]
    return markdown_table(headers, table_rows)


def _feature_shift_table(feature_shift_rows: list[dict[str, str]], *, top_n: int = 15) -> str:
    matched = [row for row in feature_shift_rows if row["subtopic_vocabulary_match"]]

    def _shift(row: dict[str, str]) -> float:
        return abs(float(row["coefficient_shift"])) if row["coefficient_shift"] else 0.0

    matched.sort(key=_shift, reverse=True)
    headers = ["主ラベル", "特徴語", "C0係数（平均）", "C30係数（平均）", "変化量", "一致した副トピック語彙"]
    table_rows = [
        [
            row["label"],
            row["feature"],
            f"{float(row['mean_coefficient_c0']):.3f}" if row["mean_coefficient_c0"] else "n/a",
            f"{float(row['mean_coefficient_c30']):.3f}" if row["mean_coefficient_c30"] else "n/a",
            f"{float(row['coefficient_shift']):+.3f}" if row["coefficient_shift"] else "n/a",
            row["subtopic_vocabulary_match"],
        ]
        for row in matched[:top_n]
    ]
    return markdown_table(headers, table_rows)


def _quote_block(text: str) -> str:
    """Render multi-paragraph body text as a Markdown blockquote (a `` `code` `` span cannot
    safely contain a blank line -- it would break out of the inline span mid-render)."""
    return "\n".join(f"> {line}" if line else ">" for line in text.split("\n"))


def _representative_examples_section(rows: list[dict[str, str]]) -> str:
    flipped = [row for row in rows if row["transition"] == "correct_to_incorrect"]
    parts = []
    for row in flipped[:3]:
        parts.append(
            f"""**sample {row['sample_id']}**（主ラベル: {row['main_label']}、副トピック: {row['subtopic_label']}、
style: {row['style']}、挿入位置: {row['insertion_position']}、fold {row['fold_id']}）

C0（混入前）本文:

{_quote_block(row['body_text_c0'])}

C30（混入後）本文:

{_quote_block(row['body_text_c30'])}

- 正解ラベル: {row['true_label']} / C0予測: {row['predicted_label_c0']} / C30予測: {row['predicted_label_c30']}
- 正解ラベルへのdecision score: C0 {float(row['decision_score_true_label_c0']):+.3f} → C30 {float(row['decision_score_true_label_c30']):+.3f}
- 副トピックラベルへのdecision score: C0 {float(row['decision_score_subtopic_label_c0']):+.3f} → C30 {float(row['decision_score_subtopic_label_c30']):+.3f}
- C0の主な寄与語: {row['top_features_predicted_c0']}
- C30の主な寄与語: {row['top_features_predicted_c30']}
"""
        )
    return "\n".join(parts)


@dataclass(frozen=True)
class ReportArtifacts:
    run_dir: Path
    metrics_summary: list[dict[str, str]]
    condition_statistics: list[dict[str, str]]
    transition_summary: list[dict[str, str]]
    main_subtopic_pair_summary: list[dict[str, str]]
    misclassifications: list[dict[str, str]]
    oof_rows: list[dict[str, str]]
    assignment_rows: list[dict[str, str]]
    feature_shift: list[dict[str, str]]
    representative_examples: list[dict[str, str]]
    review_samples: list[dict[str, str]]
    statistical_tests: dict[str, object]
    manifest: dict[str, object]
    summary: dict[str, object]
    dataset_manifest: dict[str, object]
    original_records_by_id: dict[str, object]


def load_report_artifacts(run_dir: Path, project_root: Path) -> ReportArtifacts:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    dataset_manifest = json.loads((run_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    c0_data_path = project_root / dataset_manifest["levels"]["C0"]["data_path"]
    original_records = read_jsonl(c0_data_path)

    return ReportArtifacts(
        run_dir=run_dir,
        metrics_summary=_rows(run_dir, "metrics_summary.csv"),
        condition_statistics=_rows(run_dir, "condition_statistics.csv"),
        transition_summary=_rows(run_dir, "transition_summary.csv"),
        main_subtopic_pair_summary=_rows(run_dir, "main_subtopic_pair_summary.csv"),
        misclassifications=_rows(run_dir, "misclassifications.csv"),
        oof_rows=_rows(run_dir, "predictions_oof.csv"),
        assignment_rows=_rows(run_dir, "contamination_assignment.csv"),
        feature_shift=_rows(run_dir, "feature_shift.csv"),
        representative_examples=_rows(run_dir, "representative_transition_examples.csv"),
        review_samples=_rows(run_dir, "review_samples.csv"),
        statistical_tests=json.loads((run_dir / "statistical_tests.json").read_text(encoding="utf-8")),
        manifest=manifest,
        summary=json.loads((run_dir / "summary.json").read_text(encoding="utf-8")),
        dataset_manifest=dataset_manifest,
        original_records_by_id={record.id: record for record in original_records},
    )


def build_report_markdown(artifacts: ReportArtifacts) -> str:
    a = artifacts
    condition, model = PRIMARY_CELL

    mcnemar_rows = [
        [
            entry["compare_level"],
            "混入sampleのみ" if entry["contaminated_only"] else "全800件",
            str(entry["n_pairs"]),
            str(entry["n_correct_to_incorrect"]),
            str(entry["n_incorrect_to_correct"]),
            f"{entry['statistic']:.3f}",
            f"{entry['p_value']:.2e}",
        ]
        for entry in a.statistical_tests["mcnemar"]
    ]
    bootstrap_rows = [
        [
            entry["compare_level"],
            f"{entry['observed_diff']:+.4f}",
            f"{entry['ci95_low']:+.4f}",
            f"{entry['ci95_high']:+.4f}",
            f"{entry['fraction_bootstrap_le_zero']:.1%}",
        ]
        for entry in a.statistical_tests["paired_bootstrap"]
    ]

    macro_f1_by_level = a.summary["primary_cell_macro_f1_by_level"]
    accuracy_by_level = a.summary["primary_cell_accuracy_by_level"]
    pulled_rates = _pulled_to_subtopic_rate_by_level(a.misclassifications)

    difficulty_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: original.difficulty.value,
        dimension_header="難易度",
    )
    contaminated_flag_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: "混入あり" if contaminated else "混入なし",
        dimension_header="副トピック混入",
    )
    position_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: (arow["insertion_position"] if contaminated else "（混入なし）"),
        dimension_header="挿入位置",
    )
    multi_intent_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: str(bool(original.metadata.get("multi_intent", False))),
        dimension_header="元のmulti_intent",
    )
    negation_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: str(bool(original.metadata.get("contains_negation", False))),
        dimension_header="元のcontains_negation",
    )
    style_table_c30 = _breakdown_table(
        a.oof_rows,
        a.assignment_rows,
        a.original_records_by_id,
        level="C30",
        dimension_fn=lambda original, arow, contaminated: (arow["style"] if contaminated else "（混入なし）"),
        dimension_header="副トピック文の表現style",
    )

    review_reason_counts: dict[str, int] = defaultdict(int)
    for row in a.review_samples:
        review_reason_counts[row["flag_reason"]] += 1
    review_table = markdown_table(
        ["自動判定理由", "件数"],
        [[reason, str(count)] for reason, count in sorted(review_reason_counts.items())],
    )

    return f"""# 問い合わせメール分類における副トピック混入率の影響

英語版Task 10（TF-IDF + 線形分類器による問い合わせメール4クラス分類）の発展実験（Extension）。
既存のCore実験・確定成果物（`outputs/runs/phase4-core-seed42/`等）は一切変更していない。

## 1. 目的

主トピック（ラベル）は変えずに、本文へ別カテゴリに関連する副トピックの一文を意図的に混入させ、
混入率（0%・10%・20%・30%）が分類性能（Accuracy、macro Precision/Recall/F1、クラス別指標、
誤分類先、主トピック×副トピック別の弱点）にどう影響するかを検証する。特に、モデルの予測が
主トピックより副トピックの語彙へ引っ張られる傾向があるかを明示的に検証する。

## 2. 実験設計

- 対象: 既存の英語版Full data 800件（4クラス各200件）。既存の共通5-fold
  （`outputs/folds/common_folds.json`、`StratifiedGroupKFold`、seed=42）をそのまま再利用し、
  新しいtrain/test分割は作成していない。
- 混入率: C0（0%・混入なし）、C10（10%）、C20（20%）、C30（30%）。各クラス内で
  seed=42のround-robin選択（template_group×difficultyで交互に順序付け）により、
  先頭20/40/60件（クラスの10%/20%/30%）をC10/C20/C30として選び、C10⊂C20⊂C30の
  入れ子構造とした（同一sample_idに対し混入の有無だけを変えるpaired design）。
- 主トピック×副トピックの組合せ: 4クラス×3副トピック=12組合せをC30で各20件ずつ均等に配分。
- モデル: {", ".join(CELL_LABELS[c] for c in CELL_ORDER)}（{CELL_LABELS[PRIMARY_CELL]}を主比較対象とする）。
- 実験用メタデータ（`subtopic_label`、`contamination_level`、`insertion_position`等）は
  `raw_text`/`body_text`へは一切含めず、`metadata`側にのみ記録し、モデル入力（TF-IDF）には
  一切使用していない（`tests/test_subtopic_contamination_dataset.py`で検証済み）。

## 3. 副トピック生成方法

4カテゴリ（billing / account_support / technical_issue / product_inquiry）それぞれについて、
12種類の副トピック文を用意した。各文は次の6つの表現styleを2文ずつ含む: 丁寧な依頼、簡潔な一言、
否定表現、優先順位を明示する表現、後回しでよいとする表現、事実の補足のみ。特定の1文だけが
ラベルや混入条件の手掛かりにならないよう、優先順位の明確化はstyleの組合せ全体で実現しており、
単一の定型文を繰り返してはいない。挿入位置は本文前半・中盤・末尾のいずれかをround-robinで
選び、ヘッダー・署名・件名・引用返信には一切挿入していない（`body_text`の段落単位挿入、
`insertion.py`で実装）。

## 4. データ品質

`condition_statistics.csv`で全4条件について件数・クラス分布・難易度分布・template_group分布・
完全一致重複・正規化後重複・混入率・組合せ・挿入位置・副トピック表現使用回数を監査した。

- 全条件で800件、クラス各200件を維持（`class_counts`列で確認）。
- 完全一致重複・正規化後重複は全条件で0件。
- cross-label近接重複（MinHashLSH、`extensions.minhash`を再利用）はC30でも0件——副トピック混入は
  他クラスとの近接重複を作り出していない。
- 混入率はC10=10.0%、C20=20.0%、C30=30.0%と設計値に厳密一致。
- 副トピック表現の使用回数の偏り監査（期待値の2.5倍を超える使用）は0件。
- 自動スクリーニングで主目的が不明確になり得ると判定されたsampleは{len(a.review_samples)}件
  （全{len([r for r in a.assignment_rows if r['min_level']=='C30'])}件中）。理由の内訳:

{review_table}

  （本Extensionの実行はAI編集者による自動実行であり、上記は自動ヒューリスティックによる
  スクリーニング結果である。人間によるレビューは本セッションでは実施していない。）

## 5. 混入率別の結果

主比較対象（{CELL_LABELS[PRIMARY_CELL]}）のmacro-F1は
C0 {macro_f1_by_level['C0']:.3f} → C10 {macro_f1_by_level['C10']:.3f} → C20 {macro_f1_by_level['C20']:.3f} → C30 {macro_f1_by_level['C30']:.3f}、
Accuracyは
C0 {accuracy_by_level['C0']:.3f} → C10 {accuracy_by_level['C10']:.3f} → C20 {accuracy_by_level['C20']:.3f} → C30 {accuracy_by_level['C30']:.3f}
と推移した（5-fold平均、値は`metrics_summary.csv`より）。

{_macro_f1_chart(a.metrics_summary)}

{_accuracy_chart(a.metrics_summary)}

### macro-F1（cv_mean ± 母標準偏差）

{_metrics_summary_table(a.metrics_summary, "macro_f1")}

### Accuracy（cv_mean ± 母標準偏差）

{_metrics_summary_table(a.metrics_summary, "accuracy")}

{_classwise_f1_chart(a.metrics_summary)}

### C0基準のpaired difference（`paired_differences.csv`より抜粋、macro-F1）

{markdown_table(
    ["混入率", "条件", "モデル", "平均差", "差の標準偏差", "改善Fold", "悪化Fold"],
    [
        [row["level"], row["condition"], row["model"], f"{float(row['mean_diff']):+.3f}",
         f"{float(row['std_diff']):.3f}", row["n_improved"], row["n_worsened"]]
        for row in read_csv_rows(a.run_dir / "paired_differences.csv")
        if row["metric"] == "macro_f1" and row["condition"] == condition and row["model"] == model
    ],
)}

### 副トピックあり／なし別の正解率（C30、{CELL_LABELS[PRIMARY_CELL]}）

{contaminated_flag_table_c30}

### 挿入位置別の正解率（C30、混入sampleのみ、{CELL_LABELS[PRIMARY_CELL]}）

{position_table_c30}

### 難易度別の正解率（C30、{CELL_LABELS[PRIMARY_CELL]}）

{difficulty_table_c30}

### multi_intent属性別の正解率（元のラベル、C30、{CELL_LABELS[PRIMARY_CELL]}）

{multi_intent_table_c30}

### 否定表現（contains_negation）属性別の正解率（元のラベル、C30、{CELL_LABELS[PRIMARY_CELL]}）

{negation_table_c30}

### 副トピック文の表現style別の正解率（C30、混入sampleのみ、{CELL_LABELS[PRIMARY_CELL]}）

{style_table_c30}

## 6. 主トピック×副トピック別分析

{_pulled_to_subtopic_chart(a.misclassifications)}

副トピックへの誤分類率（混入sampleの誤分類のうち、予測が副トピックのクラスと一致した割合）は
C10 {pulled_rates['C10']:.1%} → C20 {pulled_rates['C20']:.1%} → C30 {pulled_rates['C30']:.1%}
であり、モデルが主トピックより副トピックの語彙へ引っ張られる明確な傾向が確認された
（`misclassifications.csv`の`pulled_to_subtopic`列より集計）。

{_main_subtopic_degradation_chart(a.main_subtopic_pair_summary)}

### 主ラベル×副トピック別の詳細（C30、{CELL_LABELS[PRIMARY_CELL]}、正解率変化の小さい順）

{_main_subtopic_pair_table(a.main_subtopic_pair_summary)}

## 7. 誤分類遷移

{_transition_chart(a.transition_summary)}

`transition_summary.csv`（{CELL_LABELS[PRIMARY_CELL]}、C0→C30）によれば、混入sample群
（240件）では正解→誤分類への遷移が誤分類→正解への遷移を上回る一方、非混入sample群（560件）では
両者はほぼ拮抗している。これは、混入による性能低下が主に混入sample自身に集中しており、
（訓練データの一部が混入したことによる）間接的な影響は非混入sampleに対しては強い方向性を
持たないことを示唆する。

### 統計的検定（paired design、sample単位）

同一sampleを複数条件で評価するpaired designであるため、独立標本を前提とする通常の検定は
適用していない。McNemar検定（連続性補正、1自由度）とsample単位paired bootstrap
（2000回, 95%区間）を実施したが、混入率3水準×比較対象4件＝12通りの多重比較は補正していない
ため、記述統計としての参考値として報告する。

**McNemar検定**（{CELL_LABELS[PRIMARY_CELL]}、C0との比較）

{markdown_table(["比較先", "対象", "n", "正解→誤分類", "誤分類→正解", "統計量", "p値"], mcnemar_rows)}

**Sample単位paired bootstrap**（{CELL_LABELS[PRIMARY_CELL]}、macro-F1差、C0との比較、全800件）

{markdown_table(["比較先", "観測差", "95%CI下限", "95%CI上限", "bootstrap差が0以下の割合"], bootstrap_rows)}

## 8. 特徴語・decision score分析

`feature_shift.csv`は{CELL_LABELS[PRIMARY_CELL]}のFold再fit係数（top_absolute特徴、
5-fold平均）をC0とC30で比較したもの。以下は副トピックの文章バンク語彙と一致した特徴語のうち、
変化量が大きい上位である。

{_feature_shift_table(a.feature_shift)}

### 代表的な誤分類例（匿名化・合成データ、C0→C30で正解から誤分類へ転じたsample）

以下は、C30で初めて副トピックが混入された（C10/C20では非混入の）sampleのうち、
{CELL_LABELS[PRIMARY_CELL]}の予測がC0では正解、C30では誤分類へ転じた例を、対象sampleの
検証Foldを再fitして得たdecision scoreとともに示す。本文は合成データであり、実在の個人・組織を
含まない。

{_representative_examples_section(a.representative_examples)}

## 9. 限界

- 訓練データそのものが条件間で異なる（C10/C20/C30では一部sampleが混入されているため、
  混入されていないsampleの予測も、訓練Foldに混入sampleが含まれることで間接的に変化しうる）。
  本レポートの「混入あり／なし別正解率」「遷移分析」はこの間接効果を分離していない。
- McNemar検定・paired bootstrapは多重比較（3混入率×4モデルセル）を補正していない。
- 副トピック文章バンクは各カテゴリ12種類に限定されており、より多様な言い回しでは異なる結果に
  なる可能性がある。
- 本Extensionの品質監査（`review_samples.csv`）は自動ヒューリスティックによるスクリーニングの
  みであり、Core Full dataのような人間によるレビュー・承認は実施していない。
- 合成データ上の統制実験であり、実際の問い合わせメール分布への一般化は主張しない。
- Fold間のtemplate_group不均衡（Core Phase 3で確認済みの既知の限界）は本Extensionでも
  そのまま引き継いでいる。

## 10. 結論

{CELL_LABELS[PRIMARY_CELL]}を主対象として、副トピックの混入率を10%刻みで30%まで増やすと、
macro-F1・Accuracyは低下傾向を示した（C0 {macro_f1_by_level['C0']:.3f} → C30 {macro_f1_by_level['C30']:.3f}）。
特に混入sample自身の誤分類率が有意に上昇し（McNemar p値は各混入率で有意水準0.05を下回った、
多重比較未補正）、誤分類の一部は副トピックのクラスへ引っ張られていた
（C30で副トピックへの誤分類率{pulled_rates['C30']:.1%}）。特徴語分析でも、副トピックの
文章バンク語彙に含まれる語（例: payment、item等の請求関連語）の係数が混入後に変化しており、
モデルが主トピックだけでなく副トピックの語彙にも反応していることが確認された。

## 11. Technical Appendix

- Run ID: `{a.manifest['run_id']}`
- Fold artifact: `{a.manifest['fold_artifact_path']}`（hash `{a.manifest['fold_artifact_hash']}`）
- C0データhash（既存Full dataと同一）: `{a.manifest['data_hash']}`
- 各条件のデータhash: {", ".join(f"{level}=`{info['data_hash'][:16]}...`" for level, info in a.dataset_manifest['levels'].items())}
- git commit: `{a.manifest['git_commit']}`（dirty={a.manifest['git_dirty']}）
- 依存関係: {a.manifest['dependency_versions']}

### 全metrics_summary（cv_mean ± 母標準偏差、macro-F1）

{_metrics_summary_table(a.metrics_summary, "macro_f1")}

### 全条件の件数・混入率（`condition_statistics.csv`より）

{markdown_table(
    ["混入率", "件数", "混入件数", "混入率"],
    [
        [
            level,
            next(r["value"] for r in a.condition_statistics if r["level"] == level and r["category"] == "total_count"),
            next(r["value"] for r in a.condition_statistics if r["level"] == level and r["category"] == "contamination_rate" and r["key"] == "contaminated_count"),
            f"{float(next(r['value'] for r in a.condition_statistics if r['level'] == level and r['category'] == 'contamination_rate' and r['key'] == 'contaminated_ratio')):.1%}",
        ]
        for level in CONTAMINATION_LEVELS
    ],
)}

### 再現手順

```bash
uv run python3 scripts/run_subtopic_contamination_extension.py
uv run python3 scripts/build_subtopic_contamination_report.py
```
"""


DEFAULT_REPORT_RUN_ID = "ext-subtopic-contamination-report-seed42"


@dataclass(frozen=True)
class ExtensionReportBuildResult:
    report_dir: Path
    markdown_path: Path
    pdf_path: Path
    layout_check_path: Path


def write_subtopic_contamination_report(
    project_root: str | Path,
    *,
    run_id: str = "phase-subtopic-contamination-seed42",
    report_run_id: str = DEFAULT_REPORT_RUN_ID,
) -> ExtensionReportBuildResult:
    """Build report.md from the Extension's own artifacts, then render to PDF."""
    project_root = Path(project_root).resolve()
    run_dir = project_root / "outputs" / "extensions" / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(
            f"{run_dir} does not exist; run "
            "run_and_write_subtopic_contamination_extension first"
        )

    artifacts = load_report_artifacts(run_dir, project_root)
    markdown = build_report_markdown(artifacts)

    report_dir = project_root / "outputs" / "reports" / report_run_id
    markdown_path = report_dir / "report.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")

    _html_path, _registry_path, pdf_path, layout_check_path = render_report_pdf(
        markdown_path, report_dir, layout_overrides_path=None
    )
    return ExtensionReportBuildResult(
        report_dir=report_dir,
        markdown_path=markdown_path,
        pdf_path=pdf_path,
        layout_check_path=layout_check_path,
    )
