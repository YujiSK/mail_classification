# 課題10 推奨アーキテクチャ

## 1. 導出根拠

この構成は課題9の実装監査から導出した。維持するのは、共通Fold、Pipeline内fit、Fold Long records、Core/Extension、実験とreportingの分離である。変更するのは、合成メールのtemplate group、multiclass説明性、二種類のリーク監査、完全なprovenance、前処理3層化、結果世代管理である。

ここに示すのは将来の推奨構成であり、今回ディレクトリや分類コードを作成する指示ではない。

現在のテーマ案は「TF-IDFと線形分類モデルを用いた問い合わせメールの自動振り分け、および前処理・データリーク・誤分類要因の評価」である。データは英語の合成問い合わせメール、候補ラベルは`product_inquiry`、`technical_issue`、`billing`、`account_support`だが、ラベルと件数は監査時点では未確定として設定へ外出しする。

## 2. 推奨ディレクトリ構成

```text
task10/
├── AGENTS.md
├── pyproject.toml                 # dependencies + tool configuration
├── lock file                     # 採用toolに応じて1種類
├── configs/
│   ├── data_generation.yml
│   ├── preprocessing.yml
│   ├── experiments_core.yml
│   └── experiments_extension.yml
├── data/
│   ├── raw/                       # immutable/generated source; large files ignored
│   ├── derived/                   # body/clean等; reproducible
│   └── samples/                   # small reviewed fixtures only
├── src/task10/
│   ├── paths.py
│   ├── provenance.py
│   ├── data/
│   │   ├── schema.py
│   │   ├── generation.py
│   │   ├── quality.py
│   │   └── dedup.py
│   ├── preprocessing/
│   │   ├── base.py
│   │   ├── cleaning.py
│   │   ├── normalization.py
│   │   ├── segmentation.py
│   │   └── english.py
│   ├── features/
│   │   └── tfidf.py
│   ├── models/
│   │   └── factory.py
│   ├── evaluation/
│   │   ├── splits.py
│   │   ├── cv.py
│   │   ├── metrics.py
│   │   ├── aggregate.py
│   │   └── paired.py
│   ├── explain/
│   │   ├── linear.py
│   │   └── errors.py
│   └── reporting/
│       ├── tables.py
│       ├── figures.py
│       └── generation.py
├── scripts/
│   ├── generate_data.py
│   ├── audit_data.py
│   ├── run_core.py
│   ├── run_extension.py
│   └── build_report.py
├── tests/
│   ├── data/
│   ├── preprocessing/
│   ├── evaluation/
│   ├── explain/
│   └── integration/
├── outputs/
│   └── runs/<run_id>/
│       ├── manifest.json
│       ├── folds.csv
│       ├── metrics_long.csv
│       ├── metrics_summary.csv
│       ├── predictions_oof.csv
│       ├── paired_differences.csv
│       ├── explanations/
│       ├── figures/
│       └── checks/
├── reports/
│   ├── report.md
│   └── generated/
├── artifacts/
│   ├── pdf/
│   └── figures/
├── tmp/
│   └── renders/
├── docs/
└── tools/pdf_renderer/            # external/ported standalone tool
```

`outputs/`、`data/`等は実装開始時に必要最小限だけ作る。今回この構成を先走って生成しない。

## 3. 責務

- `data`: raw生成・schema・品質・重複。モデルを知らない。
- `preprocessing`: Cleaning/Normalization/Segmentationとstats。labelを見ない。
- `features/models`: sklearn-compatible component。学習型処理はPipeline内。
- `evaluation`: Fold定義、fit/predict、metric、OOF、aggregate。reportを知らない。
- `explain`: fitted modelとFold vocabularyから係数・誤分類寄与を生成。
- `reporting`: 保存済みartifactを読むだけ。実験を再実行しない。
- `scripts`: config読込とuse-case orchestrationのみ。
- `tools/pdf_renderer`: 実験コードから独立した移植ツール。

## 4. データフロー

```text
generation config + seed
  → immutable raw_text + label + template_group + difficulty + generation metadata
  → content/duplicate/length/label-token audit
  → body_text extraction
  → derived clean_text and processing stats
  → split decision (group structureあり: StratifiedGroupKFold / なし: StratifiedKFold)
  → folds.csvを固定
  → condition × model が同じfolds.csvを利用
  → Pipeline fit(train only) / transform+predict(validation only)
  → metrics_long + OOF predictions + explanations + timing
  → aggregation / paired differences
  → report tables/figures
  → Markdown → HTML → PDF → layout check
```

`raw_text`は上書きしない。想定列は`raw_text`, `body_text`, `clean_text`, `label`, `template_group`, `difficulty`に加え、header/signature/quote flagとgeneration metadataである。

## 5. 前処理フロー

各層は独立ON/OFF可能にする。

1. Cleaning: HTML/control chars、header/signature/quoted reply等。処理ごとに削除量を記録。
2. Normalization: whitespace、Unicode、case、URL/email placeholder等。各処理をアブレーション化。
3. Segmentation/features: word/character n-gram、stopwords、lemmatization。TF-IDFの語彙/IDF fitはFold内。

否定語`not`, `no`, `never`, `without`, `cannot`は保護対象候補とし、「stopwordなし」「既定相当」「否定語保護custom」を比較する。BERT Extensionでは古典用stemming/stopwordを無条件適用しない。

## 6. 実験フロー

### Core

- 合成データ品質・リーク監査。
- template-aware splitの決定。
- TF-IDF＋LinearSVC/Logistic Regression。
- 最小前処理baselineと、主要因1つずつのablation。
- macro-F1を主指標として、同一Foldで比較。
- OOF prediction、誤分類、クラス別係数、時間、語彙数。

### Extension

- BERT/Transformer。
- MinHashLSH near duplicate。
- language detection。
- threshold/calibration、追加モデル、Permutation Importance。

Coreのartifact schema・テスト・再現性が完成するまでExtensionを実行しない。

## 7. 評価フロー

- Foldは一度生成し`folds.csv`として保存。
- group構造が実在するときのみ`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`。
- 各condition/modelはFold IDとsample IDの完全一致を検証。
- PipelineをFoldごとに新規生成。
- metrics: Accuracy、macro P/R/F1、weighted-F1、classwise P/R/F1、confusion matrix。
- fit/predict時間、語彙数をFold単位保存。
- paired differenceは1:1 mergeを強制し、欠落・重複をerrorにする。
- CV Foldを独立標本とみなす単純な有意差検定はしない。

## 8. 誤分類・説明性

`predictions_oof.csv`に最低限以下を保存する。

- sample ID、fold、condition、model
- true/pred label
- decision score（クラス別）
- difficulty、template_group
- header/signature/quote flags
- 上位正寄与・負寄与特徴
- error hypothesis（自動候補と人手注記を区別）

係数はクラス別に正・負・絶対値を保存する。FoldごとにTF-IDF語彙が違うため、係数とfeature nameを同じfitted Pipelineから取得する。全データ説明モデルは`descriptive_full_fit`と明記し、OOF性能と混ぜない。

## 9. レポートフロー

```text
selected run manifest
  → generation mismatch/hash check
  → tables/figures scripts
  → report Markdown
  → tools/pdf_renderer basic build
  → layout checker
  → optional auto-repair (explicit flag only)
  → final PDF + check JSON
```

report生成は学習をimport/実行しない。通常PDFビルドはMarkdown・manual layout設定を変更しない。手動設定とgenerated設定を分離する。

## 10. 課題9から維持・変更

### 維持

- 共通Fold、Fold Long、ペア差。
- Pipeline内fit。
- Core/Extension分離。
- 説明専用fitの明示。
- PDF source registry、検査、opt-in修復、atomic write。

### 変更

- `StratifiedKFold`固定からdata-driven group policyへ。
- 日本語ニュース固有preprocessingから英語問い合わせ3層interfaceへ。
- 代表クラス係数から全クラス・OOF誤分類寄与へ。
- seedだけのFold再現からFold artifact保存へ。
- package versionsだけから完全run manifestへ。
- 同一出力上書きからrun ID/世代整合性へ。
- stopword/強い前処理採用前提からablationへ。
