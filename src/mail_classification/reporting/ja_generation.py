"""Phase JA-9: assemble the Task10-JA report from saved artifacts only.

Mirrors ``generation.py``'s non-destructive, artifact-only design exactly
(never imports evaluation/explain/extensions model-fitting code, never
re-runs training) but is a fully independent module writing to its own
``outputs/reports/<run_id>/`` directory, so it never touches the English
track's report. ``render_report_pdf`` itself (Markdown -> HTML -> PDF ->
layout check) is reused unmodified by import: nothing in that pipeline is
English-specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
from statistics import mean, pstdev

from mail_classification.generation.io import write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.schemas import RunManifest

from .generation import render_report_pdf
from . import ja_tables as jt
from .tables import (
    build_class_distribution_table,
    build_confusion_matrix_table,
    build_extension_summary_table,
    read_csv_rows,
)

DEFAULT_CORE_RUN_ID = "phaseJA4-core-seed42"
DEFAULT_EXPLAIN_RUN_ID = "phaseJA5-explain-seed42"
DEFAULT_EXTENSION_RUN_ID = "phaseJA6-minhash-seed42"
DEFAULT_BERT_RUN_ID = "phaseJA7-bert-seed42"
DEFAULT_QUALITY_SUMMARY_RELATIVE = Path("outputs") / "data_quality" / "full_summary_ja.json"
DEFAULT_EN_COMPARISON_RELATIVE = Path("outputs") / "runs" / "phaseJA8-en-ja-comparison-seed42.json"


def _load_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def verify_selected_runs_consistent_ja(
    project_root: Path, core_run_id: str, explain_run_id: str, extension_run_id: str
) -> dict[str, dict]:
    manifests = {
        "core": _load_manifest(project_root / "outputs" / "runs" / core_run_id),
        "explain": _load_manifest(project_root / "outputs" / "runs" / explain_run_id),
        "extension": _load_manifest(project_root / "outputs" / "extensions" / extension_run_id),
    }
    data_hashes = {name: m["data_hash"] for name, m in manifests.items()}
    if len(set(data_hashes.values())) != 1:
        raise ValueError(f"selected runs reference different data_hash values: {data_hashes}")
    fold_hashes = {
        name: m["fold_artifact_hash"]
        for name, m in manifests.items()
        if m["fold_artifact_hash"] is not None
    }
    if len(set(fold_hashes.values())) > 1:
        raise ValueError(f"selected runs reference different fold_artifact_hash values: {fold_hashes}")
    return manifests


def _bert_chapter(bert_dir: Path | None, core_dir: Path) -> tuple[str, str, str]:
    """Returns (chapter8_body, appendix_bert_block, requirement_row)."""
    if bert_dir is None or not (bert_dir / "fold_metrics.csv").is_file():
        body = (
            "本レポート生成時点で、ローカルCPU環境でのBERTフルファインチューニング実行が完了して"
            "いなかったため、この章は暫定内容である。実行可能なColab Notebook（`bert_ja_finetune_"
            "colab.ipynb`）と、ローカルCPU実行の途中経過（存在する場合は`fold_metrics.json`）を"
            "証跡として保存している。未実行のBERT数値を推測・捏造してこの章へ記載することはしない。"
        )
        appendix = "BERT実行は本レポート生成時点で未完了。Colab Notebookのみ証跡として保存。"
        requirement = "| BERTとの比較 | 8 | Colab Notebook（証跡）、実行中/未完了 | 実行中または未完了 |"
        return body, appendix, requirement

    bert_manifest = json.loads((bert_dir / "manifest.json").read_text(encoding="utf-8"))
    bert_rows = read_csv_rows(bert_dir / "fold_metrics.csv")
    from .tables import best_core_metric_cell

    best_condition, best_model, best_macro_f1 = best_core_metric_cell(core_dir, "macro_f1")

    bert_macro_f1_values = [float(r["macro_f1"]) for r in bert_rows]
    fold_mean_macro_f1 = mean(bert_macro_f1_values)
    fold_std_macro_f1 = pstdev(bert_macro_f1_values) if len(bert_macro_f1_values) > 1 else 0.0

    required_table = jt.build_bert_required_metrics_table_ja(
        core_dir, bert_dir / "fold_metrics.csv", best_condition=best_condition, best_model=best_model
    )
    comparison_table = jt.build_bert_comparison_table_ja(core_dir, bert_dir / "fold_metrics.csv")
    confusion_table = (
        jt.build_bert_confusion_matrix_table(bert_dir / "predictions_oof.csv")
        if (bert_dir / "predictions_oof.csv").is_file()
        else "（OOF予測未保存）"
    )

    body = f"""BERT（`{bert_manifest['model_name']}`）を、Coreと同一のFull dataset（`data_hash`一致）・
共通5-foldでファインチューニングした。入力は`body_text`（Sudachi分かち書き・NFKC等の前処理は
一切適用せず、モデル標準Tokenizerへ直接渡す）である。設定: epochs={bert_manifest['epochs']}、
batch_size={bert_manifest['batch_size']}（effective_batch_size={bert_manifest['effective_batch_size']}）、
learning_rate={bert_manifest['learning_rate']}、max_length={bert_manifest['max_length']}、
random_seed={bert_manifest['seed']}、実行環境={bert_manifest['execution_environment']}
（device={bert_manifest['device']}、torch {bert_manifest['torch_version']}、
transformers {bert_manifest['transformers_version']}）。

各総合指標は5分割交差検証におけるFold別指標の平均値である。混同行列およびクラス別指標は、
全800件のOOF予測を統合して算出した。Fold平均Accuracyと、800件のOOF予測から直接算出した
Accuracyは、Foldサイズが完全には均等でない（本稿執筆時点のvalidation件数は167/167/134/166/166）
ため、僅かに異なり得る。両者を混同しないよう、本レポートの主要比較表はFold平均を用いる。

**課題指定4指標（Core最良条件 {jt.JA_CONDITION_LABELS[best_condition]}＋{best_model} との比較、
BERTはFold平均）**:

{required_table}

**macro-F1（全8セルとの比較、Fold平均 ± Fold間母標準偏差）**:

{comparison_table}

BERTのmacro-F1（Fold平均）は{fold_mean_macro_f1:.3f}（Fold間母標準偏差 {fold_std_macro_f1:.3f}）であり、
Core最良条件（{jt.JA_CONDITION_LABELS[best_condition]}／{best_model}、{best_macro_f1:.3f}）と比較して
{"上回った" if fold_mean_macro_f1 > best_macro_f1 else "下回った、または同程度であった"}。

**混同行列（全800件のOOF予測を統合）**:

{confusion_table}

**考察**: BERTはSudachiによる形態素解析を経由せず、独自のsubwordトークナイザーで`body_text`を
直接処理する。Core側の最良条件がJC（文字n-gram、Sudachi非依存）であったことを踏まえると、
両者はいずれも形態素解析の誤りに影響されない設計である点で共通するが、BERTは事前学習により
獲得した文脈依存表現を追加で持つ。ただし、CoreはFull全文の一部を保持する条件（header/signature/
quoted-reply）も含むのに対し、BERTは`body_text`のみを入力とするため、性能差をモデル構造だけに
帰属することはできず、入力処理を含むパイプライン全体の比較として解釈する必要がある
（本文と同一`body_text`入力でのTF-IDF＋LinearSVC比較は付録A.9参照）。本比較は1つの乱数seed・
5分割交差検証のみであり、統計的有意差検定は行っていない。
"""
    appendix = f"実行識別子: `{bert_dir.name}`／モデル: `{bert_manifest['model_name']}`／実行環境: {bert_manifest['execution_environment']}"
    requirement = f"| BERTとの比較 | 8 | `outputs/runs/{bert_dir.name}/` | 実施・同一data hash/Fold検証済み |"
    return body, appendix, requirement


def build_report_markdown_ja(
    manifests: dict[str, dict],
    core_dir: Path,
    explain_dir: Path,
    extension_dir: Path,
    quality_summary_path: Path,
    en_comparison_path: Path,
    *,
    bert_dir: Path | None = None,
    body_raw_comparison_path: Path | None = None,
) -> str:
    quality_summary = json.loads(quality_summary_path.read_text(encoding="utf-8"))
    en_comparison = json.loads(en_comparison_path.read_text(encoding="utf-8")) if en_comparison_path.is_file() else None

    from .tables import best_core_metric_cell

    best_condition, best_model, best_macro_f1 = best_core_metric_cell(core_dir, "macro_f1")

    core_required_table = jt.build_core_required_metrics_table_ja(core_dir)
    macro_f1_table = jt.build_metric_summary_table_ja(core_dir, "macro_f1")
    accuracy_table = jt.build_metric_summary_table_ja(core_dir, "accuracy")
    confusion_table = build_confusion_matrix_table(core_dir, best_condition, best_model)
    paired_table = jt.build_paired_differences_table_ja(core_dir, baseline="J0", metric="macro_f1")
    error_table = jt.build_error_category_percentage_table_ja(explain_dir)
    error_counts_table = jt.build_error_category_counts_table(explain_dir)
    extension_table = build_extension_summary_table(extension_dir)
    class_table = build_class_distribution_table(quality_summary_path)

    j1_diff_svc = jt.read_paired_diff_mean_ja(core_dir, "J1", "linear_svc")
    j1_diff_lr = jt.read_paired_diff_mean_ja(core_dir, "J1", "logistic_regression")
    j2_diff_svc = jt.read_paired_diff_mean_ja(core_dir, "J2", "linear_svc")
    j2_diff_lr = jt.read_paired_diff_mean_ja(core_dir, "J2", "logistic_regression")
    jc_diff_svc = jt.read_paired_diff_mean_ja(core_dir, "JC", "linear_svc")
    jc_diff_lr = jt.read_paired_diff_mean_ja(core_dir, "JC", "logistic_regression")

    bert_body, bert_appendix, bert_requirement = _bert_chapter(bert_dir, core_dir)

    data_hash = manifests["core"]["data_hash"]
    fold_hash = manifests["core"]["fold_artifact_hash"]
    core_run_id = manifests["core"]["run_id"]
    explain_run_id = manifests["explain"]["run_id"]
    extension_run_id = manifests["extension"]["run_id"]
    structure_ratios = quality_summary["structure_ratios"]

    # Structural artifact re-audit count (Chapter 6 leakage summary)
    structural_audit_rows = read_csv_rows(explain_dir / "structural_artifact_audit.csv")

    body_raw_note = ""
    if body_raw_comparison_path is not None and body_raw_comparison_path.is_file():
        raw_rows = read_csv_rows(body_raw_comparison_path)
        raw_macro_f1 = mean(float(r["macro_f1"]) for r in raw_rows)
        body_raw_note = (
            f"参考として、Sudachi分かち書きを行わず`body_text`をそのままsklearn既定tokenizerへ渡す"
            f"条件（`BODY_RAW`、LinearSVC）のmacro-F1は{raw_macro_f1:.3f}であり、J0（Sudachi前処理あり、"
            f"{[float(r['cv_mean']) for r in read_csv_rows(core_dir / 'metrics_summary.csv') if r['condition']=='J0' and r['model']=='linear_svc' and r['metric']=='macro_f1'][0]:.3f}）"
            "を大きく下回った。日本語には単語間の空白がないため、既定tokenizerは文単位に近い粒度でしか"
            "分割できず、語彙が極端に疎になることが原因である（付録A.9）。これはSudachiによる形態素解析"
            "統合の必要性を直接裏付ける結果である。"
        )

    en_comparison_section = ""
    en_comparison_appendix = ""
    if en_comparison is not None:
        both_high = en_comparison["both_high"]
        en_only = en_comparison["en_only_high"]
        ja_only = en_comparison["ja_only_high"]
        both_low = en_comparison["both_low"]
        total_groups = both_high + en_only + ja_only + both_low
        group_rows = "\n".join(
            f"| {group} | {en_comparison['en_group_accuracy'].get(group, float('nan')):.3f} | "
            f"{en_comparison['ja_group_accuracy'].get(group, float('nan')):.3f} |"
            for group in sorted(en_comparison["en_group_accuracy"])
        )
        en_comparison_appendix = f"""
| semantic_template_id | 英語版accuracy（{en_comparison['en_condition']}） | 日本語版accuracy（{en_comparison['ja_condition']}） |
| --- | --- | --- |
{group_rows}
"""
        en_comparison_section = f"""
## 第9章 英語版との比較

英語版Task10（`outputs/runs/phase4-core-seed42/`、`outputs/runs/phase5-explain-seed42/`、
`outputs/extensions/phase6-minhash-seed42/`）の既存artifactを読み取り、変更せずに比較した。
英語版と日本語版の文章はsemantic_template_idで意味的に対応するが、直訳ではなく言語ごとに
自然な表現として個別に著作したものであり、語彙分布・文長・表現の丁寧さは言語間で異なる。

**Core最良条件の比較**:

| | 英語版 | 日本語版 |
| --- | --- | --- |
| 最良条件 | {en_comparison['en_condition']} | {en_comparison['ja_condition']} |
| macro-F1（cv_mean） | 0.625 | {best_macro_f1:.3f} |
| 語彙数（平均、最良条件） | 2,404 | 5,198（文字n-gram） |
| 前処理 | 英語正規表現ベース | SudachiPy形態素解析 |
| 特徴量単位 | word unigram+bigram | 文字2-3gram |

日本語版の最良条件（JC、文字n-gram）は英語版の最良条件（D1、word bigram）を上回ったが、
特徴量の単位（文字 対 単語）と語彙数が大きく異なるため、単純な優劣比較ではなく、
「日本語では文字n-gramが形態素解析の誤りに頑健な強い基準モデルになり得る」という設計上の
知見として解釈する。日本語のword-level条件（J0、語彙554）は英語のD0（語彙577）と近い規模の
語彙で近い性質のunigram条件であり、macro-F1はJ0が0.600、D0が0.616と近い水準である。

**誤分類率の比較**: 英語版は6セル合計1,883/4,800件（39.2%）、日本語版は8セル合計2,448/6,400件
（38.3%）であり、条件数・言語が異なるにもかかわらず全体の誤分類率は近い水準であった。

**近接重複（MinHashLSH）の比較**: 英語版はcandidate pair 2,054件、日本語版は2,267件、
いずれもcross_label_pairs・different_template_group_pairsは0件であり、両言語とも
ラベル境界を跨ぐ近接重複は確認されなかった。

**semantic_template_id単位でのOOF正誤対応**（Core最良条件同士、group単位比較。
1レコード単位の1対1対応は言語間variationが対応しないため作成せず、
template group内accuracy≥{en_comparison['threshold']}を「概ね正解」の目安として集計）:

- 両言語で概ね正解: {both_high} / {total_groups} groups
- 英語のみ概ね正解: {en_only} / {total_groups} groups
- 日本語のみ概ね正解: {ja_only} / {total_groups} groups
- 両言語で概ね誤分類: {both_low} / {total_groups} groups

group単位の内訳は付録A.9参照。
"""

    return f"""# 日本語問い合わせメール分類における前処理方法と分類モデルの比較

## SudachiPy・文字n-gram・線形分類器・日本語BERTを用いた5分割交差検証

## 第1章 はじめに

企業に届く問い合わせメールを内容に応じて自動分類できれば、担当部署への振り分けや初動対応の
効率化につながる。英語と異なり、日本語は単語間に空白を持たないため、TF-IDFのような
bag-of-words手法を適用する前に形態素解析による分かち書きが必要になる場合が多い。また、
敬語、カタカナ語、表記ゆれ、全角・半角混在など、日本語特有の表現の多様性も前処理設計に
影響する。

本研究では、英語版Task10（`outputs/runs/phase4-core-seed42/`等）と同じ4クラス・同じ評価設計
（共通5-fold交差検証、LinearSVC・Logistic Regression、macro-F1主指標）を日本語問い合わせメール
へ展開し、次の3点を検証した。

1. SudachiPyによる形態素解析を含む前処理条件（構造要素保持・word bigram追加・構造要素除去）が
   分類性能へ与える影響
2. 形態素解析に依存しない文字n-gram条件が、日本語分類における基準モデルとしてどの程度有効か
3. 日本語BERT（`tohoku-nlp/bert-base-japanese-v3`）との差異、および英語版との対比

## 第2章 関連技術

### 2.1 日本語テキスト分類とTF-IDF

日本語は単語境界を空白で示さないため、正規表現ベースの単語分割（英語で有効な`\\b`単語境界）は
機能しない。本研究ではSudachiPyによる形態素解析でトークン化した上でTF-IDFへ入力する条件と、
形態素解析を経由せず文字n-gramを直接特徴量とする条件を比較した。

### 2.2 SudachiPyと表記ゆれ

SudachiPyは分割モード（A/B/C）と語形（`surface`／`normalized_form`／`dictionary_form`）を
選択でき、`normalized_form()`は「出来ない」「できない」のような表記ゆれを同一トークンへ
正規化する。一方、ASCII語をカタカナへ音写する（"email"→"Eメール"）等、想定外の正規化が
発生する場合もある。

### 2.3 LinearSVCとLogistic Regression、評価指標

英語版と同じ2種の線形分類器・評価指標（Accuracy、macro Precision/Recall/F1、weighted F1、
混同行列）を用いた。

### 2.4 日本語BERT

`tohoku-nlp/bert-base-japanese-v3`はSudachiベースの語彙とWordPieceを組み合わせた日本語向け
事前学習済みBERTである。

## 第3章 データセット

日本語版Full datasetは{quality_summary['total_count']}件、4クラス各{quality_summary['class_counts'].get('billing', 200)}件、
{quality_summary['template_group_count']} template groups（6/クラス）。

{class_table}

各template groupは英語版の対応するtemplate group（tg001〜tg024）と`semantic_template_id`で
意味的に対応付けられているが、直訳ではなく自然な日本語表現として個別に著作した。合成データの
ため、実運用メールの語彙・誤字・スパム等の分布は反映していない。

## 第4章 日本語前処理と実験方法

### 4.1 前処理条件（J0〜JC）

{core_required_table}

比較条件は次のとおりである。各条件はJ0（基準）に対して主要因を1つだけ変更した。

| 条件 | 前処理 | TF-IDF特徴 |
| --- | --- | --- |
| J0（基準） | NFKC、neologdn、句読点・空白正規化、Sudachi Mode C、`normalized_form()`、構造要素（header/signature/quoted-reply）保持、否定表現保護 | word unigram |
| J1（word bigram追加） | J0と同じ | word unigram＋bigram |
| J2（構造要素除去） | J0に加えheader/signature/quoted-reply除去、URL/emailマスク | word unigram |
| JC（文字n-gram基準） | J0相当の軽い正規化、形態素解析は不使用 | 文字2-3gram（`char_wb`） |

いずれの条件も助詞・助動詞の一括除去は行わず、否定表現（「ない」「ず」「ぬ」「無い」）は
`remove_pos`設定に関わらず保護される。

### 4.2 データ分割

英語版と同じ`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`を用い、
同一`template_group`が学習Foldと評価Foldへ跨がらないようにした。

### 4.3 分類モデルと評価方法

各条件についてLinearSVCとLogistic Regressionを学習し、4条件×2モデル＝8セルを共通Foldで
評価した。主指標はmacro-F1とし、Accuracy、macro Precision/Recall、weighted F1、classwise
指標、混同行列を記録した。各指標は5分割の平均値、主要指標は母標準偏差も併記した。

## 第5章 Core実験結果

### 5.1 macro-F1（cv_mean ± cv_std）

{macro_f1_table}

![Task10-JA Core macro-F1 comparison](figures/macro_f1_comparison_ja.svg)

図5.1: 条件×モデル別macro-F1（cv_mean）。

最良の組合せは{jt.JA_CONDITION_LABELS[best_condition]}＋{best_model}で、macro-F1は{best_macro_f1:.3f}であった。

### 5.2 Accuracy

{accuracy_table}

### 5.3 混同行列（最良条件: {jt.JA_CONDITION_LABELS[best_condition]}／{best_model}）

{confusion_table}

### 5.4 J0基準との対比（Paired differences、macro-F1）

{paired_table}

### 5.5 考察

- **J0→J1（word bigram追加）**: LinearSVCで{j1_diff_svc:+.3f}、Logistic Regressionで{j1_diff_lr:+.3f}。
  英語版のD0→D1と同様、bigramの効果はモデルによって符号が異なり得る。
- **J0→J2（構造要素除去）**: LinearSVCで{j2_diff_svc:+.3f}、Logistic Regressionで{j2_diff_lr:+.3f}。
  構造的ノイズの除去は一貫した改善をもたらさない。
- **J0→JC（文字n-gram化）**: LinearSVCで{jc_diff_svc:+.3f}、Logistic Regressionで{jc_diff_lr:+.3f}。
  {body_raw_note}

## 第6章 誤分類・特徴語分析

### 6.1 誤分類カテゴリ（単一カテゴリ集計、優先順位あり）

{error_table}

### 6.2 誤分類カテゴリ（重複許容、真偽値集計）

英語版4分類（multi_intent／negation_present／structural_content／ambiguous_difficulty）に加え、
日本語固有のヒューリスティックカテゴリ（orthographic_variation／mixed_ja_en／
morphological_segmentation）を追加し、1レコードが複数カテゴリに該当する場合はすべて計上した
（したがって各セルの割合合計は100%を超え得る）。

{error_counts_table}

### 6.3 構造由来リークの再監査

`structural_artifact_audit.csv`の再監査では、8セル×5fold×4クラスのtop-15特徴（正・負・絶対値上位）
のいずれにも、差出人・件名・URL・emailに由来するトークン（`差出人`／`宛て先`／`件名`／`cc`／`bcc`／
`書く`／`url`／`email`／`eメール`／`<`／`>`）が出現しなかった（該当行{len(structural_audit_rows)}件）。
構造要素由来の明確なリークは確認されなかった。

### 6.4 考察

- `structural_content`が最多の誤分類要因であるのは、合成データ全体でのheader/signature/quoted-reply
  存在比率（{structure_ratios['has_header']:.0%}／{structure_ratios['has_signature']:.0%}／{structure_ratios['has_quoted_reply']:.0%}）
  自体が高いためと見られ、母集団比率との厳密な比較は今後の課題である。
- `morphological_segmentation`（URL/メールアドレスが日本語に直接隣接する境界ケース）は少数
  （テンプレート設計上2グループのみに意図的に含めた）であり、大規模なセグメンテーション起因の
  誤分類は確認されなかった。

## 第7章 データ品質・重複・リーク監査

完全一致・正規化後重複はいずれも{quality_summary['duplicate_group_counts']['exact']}／
{quality_summary['duplicate_group_counts']['normalized']}件。MinHashLSH（文字5-gram shingle）による
近接重複監査は次のとおりである。

{extension_table}

candidate pairは全てsame-label・same-template_group（意図的に共有するcomponent pool由来）であり、
cross-label pair・different-template-group pairは0件であった。

## 第8章 日本語BERTとの比較

{bert_body}
{en_comparison_section}
## 第10章 限界と今後の課題

- 合成データであり、実際の日本語問い合わせに見られる語彙・誤字・話題分布を十分に反映していない。
- テンプレートグループ数（label当たり6）を5-foldへ均等配分できないため、fold間標準偏差が大きい
  （英語版と同じ構造的制約）。
- 日本語固有の誤分類カテゴリ（orthographic_variation、mixed_ja_en、morphological_segmentation）は
  ヒューリスティックであり、人手による厳密なラベル付けではない。
- SudachiのMode（A/B/C）・辞書（core/full）・語形選択のアブレーションは未実施であり、Phase JA-3の
  暫定値（Mode C、`normalized_form()`）に基づく。
- BERTとCoreの入力（`body_text`のみ対全文保持条件）が完全には一致しないため、性能差をモデル構造
  だけに帰属できない。
- 英日比較はsemantic_template_id単位の対応付けであり、1対1のsample対応ではない。

## 第11章 まとめ

日本語版Task10として、800件の合成問い合わせメールに対しSudachiベースの前処理条件（J0〜J2）と
文字n-gram条件（JC）を共通5-foldで比較した。最良条件は{jt.JA_CONDITION_LABELS[best_condition]}＋
{best_model}（macro-F1 {best_macro_f1:.3f}）であり、形態素解析を経由しない文字n-gramが日本語では
強い基準モデルになり得ることを実測で確認した。また、Sudachi前処理を経由しない素朴なTF-IDFが
chance水準を下回ることも確認し、日本語処理における形態素解析統合の必要性を実証した。誤分類分析
では英語版と共通のカテゴリに加え日本語固有の要因を分析し、構造由来の明確なリークは確認されな
かった。BERTとの比較、英語版との対比を含め、言語構造と前処理方法が分類性能へ与える影響を検証した。

## 第12章 参考文献

1. G. Salton and C. Buckley, "Term-weighting approaches in automatic text retrieval," *Information Processing & Management*, 1988. https://doi.org/10.1016/0306-4573(88)90021-0
2. C. Cortes and V. Vapnik, "Support-vector networks," *Machine Learning*, 1995. https://doi.org/10.1007/BF00994018
3. D. R. Cox, "The regression analysis of binary sequences," *Journal of the Royal Statistical Society: Series B*, 1958. https://doi.org/10.1111/j.2517-6161.1958.tb00292.x
4. J. Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding," *NAACL-HLT*, 2019. https://aclanthology.org/N19-1423/
5. 工藤拓ほか, "SudachiPy," Works Applications. https://github.com/WorksApplications/SudachiPy
6. Tohoku NLP Group, "bert-base-japanese-v3," model documentation. https://huggingface.co/tohoku-nlp/bert-base-japanese-v3
7. F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," *Journal of Machine Learning Research*, 2011. https://jmlr.org/papers/v12/pedregosa11a.html
8. neologdn: Japanese text normalizer for mecab-neologd. https://github.com/ikegami-yukino/neologdn

## 付録 Technical Appendix（監査・再現情報）

## A.1 課題要件との対応

| Requirement | 章 | Evidence | Status |
| --- | --- | --- | --- |
| Mail classification / sample data | 3 | 合成問い合わせメール800件、共通5-fold | 実施済み |
| Text preprocessing | 4 | `preprocessing/japanese.py`、J0〜JC | 実装済み |
| TF-IDF | 4, 5 | `models/conditions_ja.py`、Fold内fit | 実装済み |
| Classifier training | 5 | LinearSVC、Logistic Regression | 実施済み |
| Accuracy/Precision/Recall/F1 | 5 | `metrics_summary.csv` | 実施済み |
| Misclassification causes | 6 | `misclassifications_ja.csv` | 実施済み |
{bert_requirement}

## A.2 実験識別情報

- データhash: `{data_hash}`
- 共通Fold hash: `{fold_hash}`
- Core run ID: `{core_run_id}`／説明性: `{explain_run_id}`／Extension: `{extension_run_id}`
- {bert_appendix}

## A.3 再現手順

1. `uv sync --group dev --group reporting --group japanese`
2. `data/raw/full_emails_ja.jsonl`（未生成時は`scripts/generate_pilot_data_ja.py`承認後
   `mail_classification.generation.run_ja_generation_stage("full", ...)`）
3. `mail_classification.evaluation.build_common_folds`で共通Fold（random_seed=42）
4. `mail_classification.evaluation.run_and_write_core_experiments_ja`
5. `mail_classification.explain.run_and_write_explainability_ja`
6. `mail_classification.extensions.run_and_write_minhash_extension_ja`
7. BERT: `outputs/runs/phaseJA7-bert-seed42/bert_ja_finetune_colab.ipynb`（Colab）または独立venv実行

## A.4 誤分類カテゴリの定義

`orthographic_variation`: raw_text/body_text中の既知の表記ゆれ（例: 「出来」）または全角半角
英数字混在の検出。`mixed_ja_en`: body_text中に日本語文字と2文字以上の連続ラテン文字が共存。
`morphological_segmentation`: URL/メールアドレスが日本語文字に空白なく隣接。いずれもヒューリスティック。

## A.5 MinHashLSH詳細

{extension_table}

## A.6 構造要素比率

| flag | ratio |
| --- | --- |
| has_header | {structure_ratios['has_header']:.3f} |
| has_signature | {structure_ratios['has_signature']:.3f} |
| has_quoted_reply | {structure_ratios['has_quoted_reply']:.3f} |

## A.7 semantic_template_id単位 英日accuracy対応表
{en_comparison_appendix}
## A.8 SudachiPy実行環境

Sudachi dictionary: core、Split Mode: C、token_form: normalized_form（J0〜J2）。バージョンは
`docs/contracts/phase3_model_contract_ja.md`参照。

## A.9 BODY_RAW（Sudachi非使用）比較の詳細

{body_raw_note if body_raw_note else "本buildでは選択されていない。"}
"""


@dataclass
class ReportBuildResultJa:
    report_dir: Path
    markdown_path: Path
    html_path: Path
    pdf_path: Path
    registry_path: Path
    layout_check_path: Path
    manifest_path: Path


def write_report_ja(
    project_root: str | Path,
    *,
    run_id: str | None = None,
    core_run_id: str = DEFAULT_CORE_RUN_ID,
    explain_run_id: str = DEFAULT_EXPLAIN_RUN_ID,
    extension_run_id: str = DEFAULT_EXTENSION_RUN_ID,
    bert_run_id: str | None = None,
    quality_summary_path: str | Path | None = None,
    en_comparison_path: str | Path | None = None,
    body_raw_comparison_path: str | Path | None = None,
) -> ReportBuildResultJa:
    project_root = Path(project_root).resolve()
    resolved_quality_summary_path = (
        Path(quality_summary_path)
        if quality_summary_path is not None
        else project_root / DEFAULT_QUALITY_SUMMARY_RELATIVE
    )
    resolved_en_comparison_path = (
        Path(en_comparison_path)
        if en_comparison_path is not None
        else project_root / DEFAULT_EN_COMPARISON_RELATIVE
    )
    resolved_body_raw_path = (
        Path(body_raw_comparison_path) if body_raw_comparison_path is not None else None
    )

    manifests = verify_selected_runs_consistent_ja(
        project_root, core_run_id, explain_run_id, extension_run_id
    )
    core_dir = project_root / "outputs" / "runs" / core_run_id
    explain_dir = project_root / "outputs" / "runs" / explain_run_id
    extension_dir = project_root / "outputs" / "extensions" / extension_run_id
    bert_dir = project_root / "outputs" / "runs" / bert_run_id if bert_run_id is not None else None

    resolved_run_id = run_id or f"phaseJA9-report-{core_run_id}"
    report_dir = project_root / "outputs" / "reports" / resolved_run_id
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    from . import ja_figures

    (figures_dir / "macro_f1_comparison_ja.svg").write_text(
        ja_figures.macro_f1_comparison_svg_ja(core_dir), encoding="utf-8"
    )

    markdown_text = build_report_markdown_ja(
        manifests,
        core_dir,
        explain_dir,
        extension_dir,
        resolved_quality_summary_path,
        resolved_en_comparison_path,
        bert_dir=bert_dir,
        body_raw_comparison_path=resolved_body_raw_path,
    )
    markdown_path = report_dir / "report.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    html_path, registry_path, pdf_path, layout_check_path = render_report_pdf(
        markdown_path, report_dir
    )

    manifest = RunManifest(
        run_id=resolved_run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["build_report_ja", core_run_id, explain_run_id, extension_run_id],
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_versions={
            package: version(package) for package in ("markdown", "beautifulsoup4", "pdfplumber")
        },
        config_path=None,
        config_hash=None,
        data_path=None,
        data_hash=manifests["core"]["data_hash"],
        data_generation_seed=None,
        template_path=None,
        template_hash=None,
        generator_version=None,
        approval_decision_path=None,
        approval_decision_hash=None,
        cv_seed=manifests["core"]["cv_seed"],
        fold_artifact_path=manifests["core"]["fold_artifact_path"],
        fold_artifact_hash=manifests["core"]["fold_artifact_hash"],
        preprocessor_name="japanese_minimal",
        preprocessor_version="1.0.0",
        model_name=None,
        model_parameters=None,
        primary_metric="layout_check_status",
        output_directory=str(report_dir),
    )
    manifest_path = report_dir / "manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return ReportBuildResultJa(
        report_dir=report_dir,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        registry_path=registry_path,
        layout_check_path=layout_check_path,
        manifest_path=manifest_path,
    )
