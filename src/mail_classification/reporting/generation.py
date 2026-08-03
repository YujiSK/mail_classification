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


def build_report_markdown(
    manifests: dict[str, dict],
    core_dir: Path,
    explain_dir: Path,
    extension_dir: Path,
    quality_summary_path: Path,
) -> str:
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

    return f"""# 課題10 レポート: 英語問い合わせメールのTF-IDF＋線形分類

本レポートは`outputs/runs/{core_run_id}/`（Core）、`outputs/runs/{explain_run_id}/`（説明性・誤分類分析）、`outputs/extensions/{extension_run_id}/`（Extension: MinHashLSH）に保存済みの機械可読artifactのみから生成する。手動転記した数値は含まない。

- 対象data hash: `{data_hash}`
- 共通Fold artifact hash: `{fold_hash}`
- 使用run: Core=`{core_run_id}`、説明性=`{explain_run_id}`、Extension=`{extension_run_id}`

## 第1章 大学課題要件との対応

課題10の要件原本ファイルは本監査時点でリポジトリ内に確認できなかったため、以下は現在の実装状況に基づく対応表であり、必須／任意の最終判断は要件原本の確認を要する。

| Requirement | Phase | Evidence | Implementation status |
| --- | --- | --- | --- |
| Text preprocessing | 1, 3, 4 | `src/mail_classification/preprocessing/`、D0〜D2 ablation | 実装済み |
| TF-IDF | 3, 4 | `src/mail_classification/models/factory.py`、Fold内fit | 実装済み |
| Linear classifier | 3, 4 | LinearSVC、Logistic Regression | 実装済み |
| Accuracy | 4 | `metrics_summary.csv` | 実装済み（第3章） |
| Precision / Recall / F1 | 4 | `metrics_long.csv`（macro／weighted／classwise） | 実装済み |
| Error analysis | 5 | `misclassifications.csv`、`error_category_summary.csv` | 実装済み（第4章） |
| BERT comparison | 6 | 第8章参照 | 未実施（承認済みの判断） |
| Result files | 2, 4, 5, 6 | `outputs/`配下のCSV／JSON | 実装済み |
| PDF report | 7 | 本文書 | 本Phaseで生成 |

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

## 第4章 説明性・誤分類分析

{error_table}

`structural_artifact_audit.csv`の再監査では、`subject`／`from`／`sent`／`cc`／`bcc`／`url`／`wrote`はいずれのtop featureにも出現せず、header／URL由来の明確なリークは確認されなかった。`email`のみ全条件のtop_absolute featureに出現するが、D0（header／URL／email非除去）でも同様に出現するため、`<EMAIL>`置換由来の構造artifactというより合成本文中の自然な語彙である可能性が高いと仮説的に判断する（断定しない）。

`structural_content`カテゴリが最多だが、これは合成データ全体でのheader／signature／quoted reply存在比率（{structure_ratios["has_header"]:.0%}／{structure_ratios["has_signature"]:.0%}／{structure_ratios["has_quoted_reply"]:.0%}）自体が高いためであり、誤分類での比率が母集団比率より高いかは本分析では未検証である。

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

全stepはseed固定・Fold artifact hash・data hashで決定的に再現可能である。

## 第8章 既知の限界・未実施事項

- 課題10要件原本が本監査時点で確認できず、必須／任意の最終判断は要件原本確認後に要修正。
- BERT比較は未実施（`torch`のuv解決が60秒でtimeoutし大容量依存・Python 3.14互換未確認という実測リスクを理由に、User (Yuji Sunagawa) 承認のもとMinHashLSHのみへ絞った）。
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
    quality_summary_path: str | Path | None = None,
) -> ReportBuildResult:
    """Build report.md + figures, then HTML -> PDF -> layout check, all under
    ``outputs/reports/<run_id>/``. Raises if the selected runs disagree on
    data_hash/fold_artifact_hash (see verify_selected_runs_consistent)."""
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

    resolved_run_id = run_id or f"phase7-report-{core_run_id}"
    report_dir = project_root / "outputs" / "reports" / resolved_run_id
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    (figures_dir / "macro_f1_comparison.svg").write_text(
        figures.macro_f1_comparison_svg(core_dir), encoding="utf-8"
    )

    markdown_text = build_report_markdown(
        manifests, core_dir, explain_dir, extension_dir, resolved_quality_summary_path
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
        command=["build_report", core_run_id, explain_run_id, extension_run_id],
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
