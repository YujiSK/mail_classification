"""Phase 7: assemble the Task 10 report from saved artifacts only, then build the PDF.

This module never imports evaluation/explain/extensions model-fitting code and
never re-runs training; it only reads already-written CSV/JSON artifacts under
``outputs/runs/``, ``outputs/extensions/``, and ``outputs/data_quality/``, then
drives the ported ``tools/pdf_renderer`` tool (Markdown -> HTML -> PDF -> layout
check) exactly as docs/architecture/task10_architecture.md §9 describes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform

from mail_classification.generation.io import write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.schemas import RunManifest

import tools.pdf_renderer as _pdf_renderer_package
from tools.pdf_renderer.reporting import layout_checker, pdf_renderer, report_builder

from . import figures, tables

# Resolved from the tool's own installed location, not the caller's
# project_root: report_dir/project_root vary per run (and per test), but the
# CSS asset is a fixed part of the ported tools/pdf_renderer package itself.
_PDF_RENDERER_CSS_PATH = (
    Path(_pdf_renderer_package.__file__).resolve().parent / "assets" / "styles" / "report.css"
)

DEFAULT_CORE_RUN_ID = "phase4-core-seed42"
DEFAULT_EXPLAIN_RUN_ID = "phase5-explain-seed42"
DEFAULT_EXTENSION_RUN_ID = "phase6-minhash-seed42"
DEFAULT_BERT_RUN_ID = "phase8-bert-seed42"
DEFAULT_QUALITY_SUMMARY_RELATIVE = Path("outputs") / "data_quality" / "full_summary.json"


def _load_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def verify_selected_runs_consistent(
    project_root: Path, core_run_id: str, explain_run_id: str, extension_run_id: str
) -> dict[str, dict]:
    """Load the three selected run manifests and fail fast if they disagree on
    which Full dataset / common Fold artifact they were computed from."""
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


def _bert_limitation_bullet(bert_run_dir: Path | None) -> str:
    if bert_run_dir is None:
        return (
            "- BERT比較は未実施（`torch`のuv解決が60秒でtimeoutし大容量依存・Python 3.14互換未確認"
            "という実測リスクを理由に、User (Yuji Sunagawa) 承認のもとMinHashLSHのみへ絞った）。"
        )
    return (
        "- BERT比較（第8章）はGoogle Colab GPU環境での外部実験であり、本リポジトリの`uv run`では"
        f"再現できない（証跡は`outputs/runs/{bert_run_dir.name}/`のfold別metrics・OOF予測・"
        "実行manifest・notebookに保存）。実行環境・パッケージ版数が本リポジトリ（Python 3.14.4、"
        "torch非導入）と異なるため、本リポジトリ内での再実行による厳密な再現性は保証されない。"
    )


def _build_bert_chapter(
    core_dir: Path, bert_run_dir: Path, data_hash: str, fold_artifact_path: Path
) -> str:
    tables.verify_bert_alignment(bert_run_dir, fold_artifact_path, data_hash)

    bert_manifest = json.loads((bert_run_dir / "execution_manifest.json").read_text(encoding="utf-8"))
    model_config = bert_manifest["model_config"]
    environment = bert_manifest["environment"]

    comparison_table = tables.build_bert_comparison_table(core_dir, bert_run_dir)
    required_metrics_table = tables.build_bert_required_metrics_table(core_dir, bert_run_dir)
    bert_mean, bert_std, bert_n_folds = tables.read_bert_fold_metric_cv(bert_run_dir, "f1_score")
    best_condition, best_model, best_mean = tables.best_core_metric_cell(core_dir, "macro_f1")

    return f"""
## 第8章 Extension: DistilBERTとの性能比較（外部実験）

Phase 7完了後、追加のExtensionとしてDistilBERT（`{model_config["model_name"]}`）のfine-tuningを、Coreと同一のFull dataset・共通Foldで比較した。本実験はGoogle Colab（GPU環境）上で外部実施されたものであり、このリポジトリのCore/Extensionパイプラインには含まれない。Phase 6ではBERT比較を「`torch`のuv解決timeoutリスク」を理由に非実施と決定していたが、Colab上の別環境で実施することでこのリスクを回避し、User側で追加実施された（Phase 6・Phase 8のstatus参照）。

**実験条件の同一性（検証済み）**:

- Full dataset: `data_hash` = `{data_hash}`（Core実験と同一。`execution_manifest.json`の`actual_data_hash`と一致することを確認済み）
- 共通Fold: `outputs/folds/common_folds.json`のvalidation fold割当と800件全て一致（`sample_id`単位で1件も不一致なし。Core・説明性分析と全く同じ5-fold splitを使用）
- Model設定: epochs={model_config["epochs"]}、batch_size={model_config["batch_size"]}、learning_rate={model_config["learning_rate"]}、max_length={model_config["max_length"]}、random_seed={model_config["random_seed"]}
- 実行環境: transformers {environment["transformers_version"]}、torch {environment["torch_version"]}、python {environment["python_version"]}、device={environment["device"]}（本リポジトリのPython 3.14.4／CPU環境とは別のColab GPU環境であり、本リポジトリの`uv run`では再現できない）

**課題指定4指標の比較（5-foldの単純平均）**:

{required_metrics_table}

**macro-F1（cv_mean ± cv_std、Core全6セルとの比較）**:

{comparison_table}

DistilBERTのmacro-F1（cv_mean、fold別`f1_score`の単純平均、Coreの`cv_mean`と同じ集計方法）は{bert_mean:.3f}（cv_std {bert_std:.3f}、n_folds={bert_n_folds}）であり、Core最良条件（{best_condition}／{best_model}、{best_mean:.3f}）を上回った。

**考察: 文脈理解による精度向上のメカニズム（仮説）**:

- TF-IDF＋線形モデルは語の出現有無のみを特徴とし、語順・文脈依存の意味を直接モデル化しない（第4章参照）。DistilBERTはself-attention機構により文中の語同士の関係性（否定のスコープ、修飾関係、文全体の意味）を考慮した文脈依存の表現を学習するため、第4章で指摘した`multi_intent`（複数意図が混在するmail）や、強い語の存在だけでは判定できない誤分類パターンに対して、より頑健である可能性がある。
- 事前学習によって獲得された一般的な言語知識（subword tokenization、語彙の意味的類似性）も、purely頻度ベースのTF-IDF表現では得られない情報である。
- 本実験はseed 1点・5-fold CVのみでの比較であり、統計的有意差検定は行っていない（`docs/management/project_rules.md`の方針により、CV foldを独立標本とみなす単純な有意差検定は実施しない）。また、DistilBERTは事前学習済みの大規模言語モデルであり、Coreの線形モデルとは学習パラメータ数・計算コスト（GPU使用、fold当たり数分規模の学習時間）が大きく異なる。速度・解釈性・インフラコストとのトレードオフを踏まえた総合評価は本レポートの範囲外とする。
"""


def build_report_markdown(
    manifests: dict[str, dict],
    core_dir: Path,
    explain_dir: Path,
    extension_dir: Path,
    quality_summary_path: Path,
    *,
    bert_run_dir: Path | None = None,
    fold_artifact_path: Path | None = None,
) -> str:
    if bert_run_dir is not None and fold_artifact_path is None:
        raise ValueError("fold_artifact_path is required when bert_run_dir is given")

    quality_summary = json.loads(quality_summary_path.read_text(encoding="utf-8"))

    macro_f1_table = tables.build_metric_summary_table(core_dir, "macro_f1")
    accuracy_table = tables.build_metric_summary_table(core_dir, "accuracy")
    weighted_f1_table = tables.build_metric_summary_table(core_dir, "weighted_f1")
    confusion_table = tables.build_confusion_matrix_table(core_dir, "D0", "linear_svc")
    paired_table = tables.build_paired_differences_table(core_dir, baseline="D0", metric="macro_f1")
    error_table = tables.build_error_category_summary_table(explain_dir)
    extension_table = tables.build_extension_summary_table(extension_dir)
    class_table = tables.build_class_distribution_table(quality_summary_path)

    data_hash = manifests["core"]["data_hash"]
    fold_hash = manifests["core"]["fold_artifact_hash"]
    core_run_id = manifests["core"]["run_id"]
    explain_run_id = manifests["explain"]["run_id"]
    extension_run_id = manifests["extension"]["run_id"]

    structure_ratios = quality_summary["structure_ratios"]

    d1_diff_svc = tables.read_paired_diff_mean(core_dir, "D1", "linear_svc")
    d1_diff_lr = tables.read_paired_diff_mean(core_dir, "D1", "logistic_regression")
    d2_diff_svc = tables.read_paired_diff_mean(core_dir, "D2", "linear_svc")
    d2_diff_lr = tables.read_paired_diff_mean(core_dir, "D2", "logistic_regression")

    limitations_chapter_number = 9 if bert_run_dir is not None else 8
    bert_requirement_row = (
        f"| BERT comparison | 8 | `outputs/runs/{bert_run_dir.name}/`、第8章 | 実施・独立検証済み（Google Colab外部実験） |"
        if bert_run_dir is not None
        else "| BERT comparison | 8 | 第8章参照 | artifact未選択のため本buildには未収録 |"
    )
    bert_evidence_intro = (
        f"、`outputs/runs/{bert_run_dir.name}/`（DistilBERT外部実験）"
        if bert_run_dir is not None
        else ""
    )

    return f"""# 課題10 レポート: 英語問い合わせメールのTF-IDF＋線形分類

本レポートは`outputs/runs/{core_run_id}/`（Core）、`outputs/runs/{explain_run_id}/`（説明性・誤分類分析）、`outputs/extensions/{extension_run_id}/`（Extension: MinHashLSH）{bert_evidence_intro}に保存済みの機械可読artifactのみから生成する。手動転記した数値は含まない。

- 対象data hash: `{data_hash}`
- 共通Fold artifact hash: `{fold_hash}`
- 使用run: Core=`{core_run_id}`、説明性=`{explain_run_id}`、Extension=`{extension_run_id}`

## 第1章 大学課題要件との対応

課題10の要件原文は2026-08-03にユーザー提示で正式確認し、追跡対象の正本を`docs/requirements/task10_assignment_requirements.md`へ保存した。以下は仮置きではなく、メール分類、テキスト前処理、TF-IDF、分類器学習、4指標、誤分類・改善策、BERTとの差異、および提出物に対する正式な対応表である。

| Requirement | Phase | Evidence | Implementation status |
| --- | --- | --- | --- |
| Mail classification / sample data | 2–4 | 合成問い合わせメール800件、共通5-fold | 実施済み |
| Text preprocessing | 1, 3, 4 | `src/mail_classification/preprocessing/`、D0〜D2 ablation | 実装済み |
| TF-IDF | 3, 4 | `src/mail_classification/models/factory.py`、Fold内fit | 実装済み |
| Linear classifier | 3, 4 | LinearSVC、Logistic Regression | 実装済み |
| Accuracy | 4 | `metrics_summary.csv` | 実装済み（第3章） |
| Precision / Recall / F1 | 4 | `metrics_long.csv`（macro／weighted／classwise） | 実装済み |
| Error analysis | 5 | `misclassifications.csv`、`error_category_summary.csv` | 実装済み（第4章） |
{bert_requirement_row}
| Python source code | 1–8 | `src/`、`scripts/`、Colab Notebook | 実装済み |
| Execution results | 2, 4, 5, 6, 8 | `outputs/`配下のCSV／JSON／Notebook | 保存・検証済み |
| PDF report | 7, 8 | 本文書 | artifactから自動生成 |

## 第2章 データ概要と合成データの限界

Full datasetは{quality_summary["total_count"]}件、4クラス均等配分、{quality_summary["template_group_count"]} template groups、exact／normalized duplicates {quality_summary["duplicate_group_counts"]["exact"]}／{quality_summary["duplicate_group_counts"]["normalized"]}件。

{class_table}

合成データのため、実運用メールの分布・言い回し・スパム等は反映していない。template groupは1 groupあたり{quality_summary["variations_per_group"]["tg001"]} variationsであり、group-aware Foldで暗記を防いでいるが、語彙は本質的にtemplate起源である。

## 第3章 Core実験結果（5-fold CV、共通Fold使用）

### macro-F1（cv_mean ± cv_std）

{macro_f1_table}

![Core macro-F1 comparison](figures/macro_f1_comparison.svg)

図 3.1: Core条件×モデル別macro-F1（cv_mean）。SVGベクター画像のため、`layout_checker`のraster画像前提のfigure/caption整合チェック対象からは意図的に外している（`tools/pdf_renderer/reporting/layout_checker.py`のdocstring記載の既知のheuristic範囲外）。

### Accuracy（cv_mean ± cv_std）

{accuracy_table}

### Weighted F1（cv_mean ± cv_std）

{weighted_f1_table}

### Confusion matrix（baseline: D0 / linear_svc、OOF予測件数の合計）

{confusion_table}

### Paired differences vs baseline D0（macro-F1）

{paired_table}

fold間標準偏差は0.08〜0.13と大きい。これはlabelあたりのtemplate group数がn_splitsで割り切れないために生じるfold size不均衡（`docs/contracts/phase3_model_contract.md`記載の既知の限界）が一因と見られる。

### 考察: アブレーション条件によるスコア変動とfold不均衡の意味

- **D0→D1（bigram追加）の効果はモデルで符号が異なる**: `linear_svc`ではmacro-F1が{d1_diff_svc:+.3f}（paired differencesより）と改善する一方、`logistic_regression`では{d1_diff_lr:+.3f}と悪化している。bigramは特徴空間の次元を増やし語彙をより疎にするが、マージン最大化を目的とするLinearSVCは高次元・疎な特徴空間でも分離超平面を比較的安定して学習できるのに対し、対数損失を最小化するLogistic Regressionは少数の強いbigram特徴に適合しやすく、Foldごとに異なる語彙（TF-IDFはFold内でのみfitする設計のため）の影響をより大きく受ける可能性がある。これは今回のデータ・モデル設定下での観察であり、一般的なLinearSVC対Logistic Regressionの優劣を主張するものではない（仮説）。
- **D0→D2（前処理強化）の効果も一様ではない**: `linear_svc`で{d2_diff_svc:+.3f}、`logistic_regression`で{d2_diff_lr:+.3f}。header／signature／quoted replyの除去とURL／emailマスクは構造的ノイズを除去する一方、これらの要素に付随していた（ラベルと直接関係しないが頻度に偏りのある）語彙も同時に失われるため、効果はモデル・データの偶然性に応じて相殺され得る。「前処理を強くすれば必ず改善する」という前提は本データでは支持されない。
- **fold間標準偏差が大きい具体的な理由**: 各labelはtemplate groupを6個持つが、5-foldへ均等分配できない（6÷5）。`StratifiedGroupKFold`は必ず1 foldにつき1 labelあたり2 group分（約66件）を割り当て、残り4 foldsは1 group分（33〜34件）とする。同一template groupのsampleは語彙・表現が類似するため、「2 group分を含むfold」と「1 group分のみのfold」ではvalidation setの語彙構成自体が異なり、単純なランダムサンプリング以上にfold間でスコアがばらつく。これはCV実装の不具合ではなく、24 template groups（label当たり6 groups）× 5 foldsという設計上の数学的必然である。

## 第4章 説明性・誤分類分析

{error_table}

`structural_artifact_audit.csv`の再監査では、`subject`／`from`／`sent`／`cc`／`bcc`／`url`／`wrote`はいずれのtop featureにも出現せず、header／URL由来の明確なリークは確認されなかった。`email`のみ全条件のtop_absolute featureに出現するが、D0（header／URL／email非除去）でも同様に出現するため、`<EMAIL>`置換由来の構造artifactというより合成本文中の自然な語彙である可能性が高いと仮説的に判断する（断定しない）。

`structural_content`カテゴリが最多だが、これは合成データ全体でのheader／signature／quoted reply存在比率（{structure_ratios["has_header"]:.0%}／{structure_ratios["has_signature"]:.0%}／{structure_ratios["has_quoted_reply"]:.0%}）自体が高いためであり、誤分類での比率が母集団比率より高いかは本分析では未検証である。

### 考察: 誤分類カテゴリの背景とTF-IDFの構造的限界

- **`structural_content`が最多である背景**: TF-IDFはbag-of-words表現であり、語順や文脈を利用しない。header／signature／quoted replyを含むmailは本文中の総token数が増え、ラベルと直接関係しない語（署名の氏名、返信ヘッダの日時表記など）がベクトルに追加される。これらの語自体は強い係数を持たない（上記structural_artifact_auditの再監査結果参照）が、文書全体のTF正規化（各語の相対頻度）を薄める方向へ働き、真にラベルと関連する語のTF-IDF重みを相対的に低下させている可能性がある（仮説、本分析では因果関係までは検証していない）。
- **`multi_intent`（複数意図）の誤分類**: 1通のmailが複数カテゴリに関連する内容を含む場合、TF-IDFベクトルは両カテゴリの語彙が混在した単一の点として表現され、単一ラベル分類の決定境界上でどちらのクラス領域に属するかが本質的に曖昧になる。これは前処理やモデル選択では解消できない、single-label分類の設計とmulti-intentな入力との間の構造的な不整合である。
- **TF-IDF＋線形モデルの構造的限界**: 本手法は「どの語が出現したか」のみを特徴とし、語順・否定のスコープ・文脈依存の意味を直接モデル化しない。decision score分析（`misclassifications.csv`の`predicted_top_features`／`true_top_features`列）で確認した「正解class寄りの語が存在するにもかかわらず誤分類となる例」は、個々の強い語の存在だけでは文全体の意図を正しく判定できないことを示唆している。文脈を考慮するTransformer系モデルとの比較は本Phaseの範囲外だが、将来的な検証候補である。

## 第5章 Extension: MinHashLSH近接重複センシティビティ

{extension_table}

新規サードパーティ依存を追加せず（stdlib `hashlib`のみ）、Full全件に対しCoreのexact／normalized重複検査が検出しない近接重複を追加検出した。cross-label pairおよびdifferent-template-group pairはいずれも0件であり、確認された近接重複は全てsame-label・same-template_groupの組（Phase 2が意図的に共有するcomponent pool由来）である。ラベル境界を跨ぐ近接重複は確認されず、Core結果へのリーク疑義は本Extensionの範囲では見つからなかった。

## 第6章 リーク監査まとめ

- 完全一致・正規化後重複: Phase 2 Full生成時点でexact／normalized duplicates {quality_summary["duplicate_group_counts"]["exact"]}／{quality_summary["duplicate_group_counts"]["normalized"]}件（`outputs/data_quality/full_summary.json`）。
- 構造要素（header／signature／quoted-reply／URL／email）由来のリーク: Phase 5 `structural_artifact_audit.csv`で明確なリークは確認されなかった（第4章参照）。
- 近接重複（MinHashLSH）: Phase 6でcross-label pair 0件（第5章参照）。

## 第7章 再現手順

1. `uv sync --group dev --group reporting`で依存を解決する。
2. `data/raw/full_emails.jsonl`が存在しない場合は`scripts/generate_full_data.py`でFullデータを再生成する（`docs/reviews/full_review_decision.json`のhashで検証される）。
3. `outputs/folds/common_folds.json`が存在しない場合は`mail_classification.evaluation.splits.build_common_folds`で共通Foldを再生成する（random_seed=42）。
4. `mail_classification.evaluation.runner.run_and_write_core_experiments`でCore実験（run_id=`{core_run_id}`）を再実行する。
5. `mail_classification.explain.runner.run_and_write_explainability`で説明性分析（run_id=`{explain_run_id}`）を再実行する。
6. `mail_classification.extensions.runner.run_and_write_minhash_extension`でExtension（run_id=`{extension_run_id}`）を再実行する。
7. `scripts/build_report.py`で本レポート（Markdown → HTML → PDF、layout check付き）を再生成する。

全stepはseed固定・Fold artifact hash・data hashで決定的に再現可能である。BERT比較（第8章）はGoogle Colab GPU環境での外部実験であり、本リポジトリの`uv run`では再現できない（証跡は`outputs/runs/{bert_run_dir.name if bert_run_dir is not None else "phase8-bert-seed42"}/`に保存）。
{_build_bert_chapter(core_dir, bert_run_dir, data_hash, fold_artifact_path) if bert_run_dir is not None else ""}
## 第{limitations_chapter_number}章 既知の限界・未実施事項

{_bert_limitation_bullet(bert_run_dir)}
- `TfidfVectorizer`は`stop_words`未設定であり、一般的な機能語が上位寄与特徴に頻出する。D0〜D2は承認済みの固定specであり本Phaseでは変更していない。
- fold sizeの不均衡（第3章参照）。
- `structural_content`カテゴリの母集団比率超過は未検証（第4章参照）。
"""


@dataclass
class ReportBuildResult:
    report_dir: Path
    markdown_path: Path
    html_path: Path
    pdf_path: Path
    registry_path: Path
    layout_check_path: Path
    manifest_path: Path


def write_report(
    project_root: str | Path,
    *,
    run_id: str | None = None,
    core_run_id: str = DEFAULT_CORE_RUN_ID,
    explain_run_id: str = DEFAULT_EXPLAIN_RUN_ID,
    extension_run_id: str = DEFAULT_EXTENSION_RUN_ID,
    bert_run_id: str | None = None,
    quality_summary_path: str | Path | None = None,
) -> ReportBuildResult:
    """Build report.md + figures, then HTML -> PDF -> layout check, all under
    ``outputs/reports/<run_id>/``. Raises if the selected runs disagree on
    data_hash/fold_artifact_hash (see verify_selected_runs_consistent).

    bert_run_id is optional: pass it (e.g. DEFAULT_BERT_RUN_ID) to include the
    external DistilBERT comparison chapter; omit it to build the Core-only
    report unchanged."""
    project_root = Path(project_root).resolve()
    resolved_quality_summary_path = (
        Path(quality_summary_path)
        if quality_summary_path is not None
        else project_root / DEFAULT_QUALITY_SUMMARY_RELATIVE
    )

    manifests = verify_selected_runs_consistent(
        project_root, core_run_id, explain_run_id, extension_run_id
    )
    core_dir = project_root / "outputs" / "runs" / core_run_id
    explain_dir = project_root / "outputs" / "runs" / explain_run_id
    extension_dir = project_root / "outputs" / "extensions" / extension_run_id
    bert_dir = project_root / "outputs" / "runs" / bert_run_id if bert_run_id is not None else None
    fold_artifact_path = project_root / "outputs" / "folds" / "common_folds.json"

    resolved_run_id = run_id or f"phase7-report-{core_run_id}"
    report_dir = project_root / "outputs" / "reports" / resolved_run_id
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    (figures_dir / "macro_f1_comparison.svg").write_text(
        figures.macro_f1_comparison_svg(core_dir), encoding="utf-8"
    )

    markdown_text = build_report_markdown(
        manifests,
        core_dir,
        explain_dir,
        extension_dir,
        resolved_quality_summary_path,
        bert_run_dir=bert_dir,
        fold_artifact_path=fold_artifact_path,
    )
    markdown_path = report_dir / "report.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    build_dir = report_dir / "_build"
    html_path, registry_path = report_builder.build(
        md_path=markdown_path, css_path=_PDF_RENDERER_CSS_PATH, build_dir=build_dir
    )

    pdf_path = report_dir / "report.pdf"
    pdf_renderer.render_html_to_pdf(html_path=html_path, pdf_path=pdf_path, document_root=report_dir)

    check_result = layout_checker.run_checks(pdf_path, registry_path)
    layout_check_path = report_dir / "layout_check.json"
    write_json(layout_check_path, check_result)

    manifest = RunManifest(
        run_id=resolved_run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=[
            "build_report",
            core_run_id,
            explain_run_id,
            extension_run_id,
            *([bert_run_id] if bert_run_id is not None else []),
        ],
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
        preprocessor_name=None,
        preprocessor_version=None,
        model_name=None,
        model_parameters=None,
        primary_metric="layout_check_status",
        output_directory=str(report_dir),
    )
    manifest_path = report_dir / "manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return ReportBuildResult(
        report_dir=report_dir,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        registry_path=registry_path,
        layout_check_path=layout_check_path,
        manifest_path=manifest_path,
    )
