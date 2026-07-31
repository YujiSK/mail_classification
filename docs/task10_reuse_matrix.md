# 課題10 再利用判定マトリクス

## 判定基準

- **A — Reuse as-is**: 変更せず利用可能。
- **B — Adapt and reuse**: 設計・ロジックは有効だが課題10向け修正が必要。
- **C — Reference only**: 知見・結果のみ参照し、コードを直接使わない。
- **D — Do not reuse**: 密結合、import副作用、リーク・再現性・保守性上の理由で利用しない。

Aは「課題9で使われた」だけでは付与しない。移植時にpath、画像解決方式、Chrome検出等を変更したtask10派生版は、動作確認済みでも定義上Bとする。元課題9版も課題10で変更が必要なためB、source registryや非破壊build等の設計思想はC（Reference only）として区別する。

表中の課題9相対パスはすべて実在するローカルコピー`../task9/`を基準とし、課題6〜8はそれぞれ`../task6/`〜`../task8/`、Rabiloo資料は`../docs/`を基準とする。

## マトリクス

| 資産名 | 元 | 実際の所在 | 確認 | 分類 | task10配置候補 | 理由・必要な変更 | リスク | 対応テスト・出典 |
|---|---:|---|---|:---:|---|---|---|---|
| Fold index生成 | 9 | `src/utils.py:get_outer_splits` | code/test/output | B | `src/task10/evaluation/splits.py` | group対応、Fold artifact保存、schema検証を追加 | template漏洩 | group非重複、seed再現。`tests/test_common_modules.py` |
| Fold評価Long records | 9 | `src/experiments/evaluation.py:evaluate_pipeline_cv` | code/test/CSV | B | `src/task10/evaluation/cv.py` | multiclass metrics、OOF predictions、config/data hash、例外schema追加 | score形状、二重transform | 出力schema、全Fold coverage |
| CV集約 | 9 | `summarize_cv` | code/test/CSV | B | `evaluation/aggregate.py` | classwise指標と時間集約を追加 | 欠落Foldの黙認 | 欠落/重複Fold拒否 |
| Before/Afterペア差 | 9 | `paired_fold_diff` | code/test/CSV | B | `evaluation/paired.py` | merge validation、全Fold同一性、raw fold differences保存 | NaN/不一致が隠れる | 1:1 validation、符号テスト |
| モデルfactoryの考え方 | 9 | `src/experiments/models.py` | code/test | B | `src/task10/models/factory.py` | CoreをLinearSVC/LR中心にし設定駆動化 | 不要モデル増加 | config→estimator |
| 線形係数抽出 | 9 | `extract_linear_coefficients` | code/test/CSV | B | `explain/linear.py` | 全クラス、Fold語彙、label mapping、誤分類寄与へ拡張 | class index誤対応 | multiclass正負絶対値 |
| 木importance抽出 | 9 | `extract_tree_importances` | code/test | C | なし（Extension判断後） | Coreが線形モデル中心。必要時のみ参照 | impurity bias | Extension専用 |
| 検証Fold PI | 9 | `scripts/extra/run_exp_a_permutation.py` | code/CSV/report | B | `src/task10/explain/permutation.py`（Extension） | sparse textの計算量制限、group fold対応 | 非常に高コスト | 小規模fixture |
| 環境情報収集 | 9 | `src/utils.py:collect_environment_info` | code/JSON | B | `src/task10/provenance.py` | datetime/git/config/data/command/dictionary/preprocess version追加 | 不完全再現 | manifest schema |
| timer | 9 | `src/utils.py:timer` | code/CSV | A | `src/task10/timing.py` | stdlibのみで副作用なし。配置時に名称だけ整理可 | 単回計測の誤解 | elapsed nonnegative |
| output directory helper | 9 | `ensure_output_dir` | code/test | B | `src/task10/io/artifacts.py` | run ID、atomic write、世代manifestを追加 | 上書き・世代混在 | temp run test |
| livedoor loader/footer規則 | 9 | `src/experiments/preprocessing.py` | code/result | C | なし | 日本語ニュース固有。内容リーク監査の発想のみ利用 | メールへ誤適用 | 直接再利用しない |
| exact hash dedup | 9 | `deduplicate_by_raw_text` | code/result | B | `src/task10/data/dedup.py` | raw/body/normalized別hashとcross-fold audit追加 | normalize後重複未検出 | exact/normalized duplicate |
| IPAdic/Sudachi tokenizer | 9 | 同上 | code/result | C | Extension候補のみ | task10 Coreは英語。初期化再利用原則だけ継承 | 重い依存 | Coreには入れない |
| D 2×2 ablation設計 | 9 | `scripts/extra/run_exp_d_ablation.py` | code/CSV/report | B | config/experiment matrix | cleaning×feature/tokenization条件へ一般化 | 要因の交互作用 | condition matrix test |
| nested threshold設計 | 9 | `run_exp_c_threshold.py` | code/CSV | C | 将来Extension | Coreの主目的ではない。test閾値調整禁止の参考 | complexity | Core後のみ |
| Core/Extension分離の設計思想 | 9 | `scripts/core`, `scripts/extra`, output dirs | code/tree | C | architecture/rules | 原則を参照し、task10のgate・設定・出力規約として新規適用 | 境界逸脱 | CLI guard |
| 課題9 Markdown→HTML builder | 9 | `../task9/src/reporting/report_builder.py` | code/test/PDF | B | `tools/pdf_renderer/` | report名、root、title、base URIのtask10対応が必要 | Markdown pattern依存 | builder fixture |
| Markdown→HTML builder（task10派生版） | 9→10 | `tools/pdf_renderer/reporting/report_builder.py` | code/run/git history | B | 現配置維持 | path/title/base URIを改修済み。task10 report fixtureとlayout統合検証は継続必要 | Markdown pattern依存 | `verify_pdf.py` |
| 課題9 Chrome PDF renderer | 9 | `../task9/src/reporting/pdf_renderer.py` | code/test/PDF | B | `tools/pdf_renderer/` | 旧HTTP server、固定binary、root制約の変更が必要 | socket/host依存 | PDF smoke |
| Chrome PDF renderer（task10派生版） | 9→10 | `tools/pdf_renderer/reporting/pdf_renderer.py` | code/run/git history | B | 現配置維持 | Chrome自動検出、file URI、exit code確認へ改修済み。host別検証は継続必要 | Chrome/host依存 | PDF smoke |
| source registry・非破壊build・opt-in repairの設計思想 | 9 | `../task9/src/reporting/` | code/test/report | C | architecture/rules | 設計原則を参照。task10コードは派生実装として個別評価 | heuristic/環境依存 | policy + integration |
| layout checker | 9→10 | `tools/pdf_renderer/reporting/layout_checker.py` | code/task9 tests | B | 現配置維持 | task10 report命名・path注入、heuristic留保、テスト移植 | false positive/negative | detector + E2E |
| safe layout pipeline | 9→10 | `tools/pdf_renderer/reporting/layout_pipeline.py` | code/task9 tests | B | 現配置維持 | configs作成はreport段階、root/path汎用化済みだがtask10統合未検証 | cleanup範囲、Linux lock | opt-in/atomic/manual preservation |
| task9 CSS | 9→10 | `tools/pdf_renderer/assets/styles/report.css` | code/PDF | B | 現配置維持 | 汎用化済みだが課題10本文で視覚確認が必要 | report固有page breaks | fixture visual |
| NLTK/spaCyデモ | 6 | `text_preprocessing.py` | code/report | C | なし | API比較知見のみ。task10 interfaceを新規設計 | model再初期化 | 直接再利用しない |
| n-gram/BERT extension script | 6 | `text_preprocessing_extension.py` | code/report | D | なし | import時download/model load/実行、固定sample、非module | network、副作用 | 再実装前に要件化 |
| 課題6既定stopword実装 | 6 | `text_preprocessing.py` | code | D | なし | 否定語を無条件除去 | intent破壊 | protected-negation test |
| 日本語benchmark | 7 | `benchmark_ja_nlp.py` | code/report | C | なし | 日本語Extensionの比較設計だけ参考 | 単文、環境未保存 | Coreには入れない |
| 日本語normalization demo | 7 | `benchmark_ja_normalization.py` | code/report | C | なし | staged designの参考 | NFKC情報損失 | Coreには入れない |
| TF-IDF＋線形モデル方針 | 8 | PDF | report only | C | Core experiment plan | 実装資産ではなく仮説 | 「最適」の先取り | ablationで検証 |
| BERT比較方針 | 8/Rabiloo | PDF/Markdown | report only | C | Extension | Core完了後、raw/light preprocessing | compute/privacy | Extension gate |
| 3層Preprocessor interface | Rabiloo | `docs/text-preprocessing-en-ja.md` | spec only | B | `src/task10/preprocessing/` | base protocol、stats、toggleを新規実装 | overengineering | 30+ cases |
| language registry | Rabiloo | 同上 | spec only | C | Extension | 現在英語のみ。interfaceを拡張可能に保つが先行実装しない | premature scope | English Core後 |
| MinHashLSH | Rabiloo | 同上 | spec only | C | Extension | near duplicateは必要だがCoreでは軽量類似監査から開始 | parameter sensitivity | held-out fixture |
| 30件以上の前処理テスト | Rabiloo | 同上 | requirement only | B | `tests/preprocessing/` | test suiteを新規作成 | missing coverage | 必須case一覧 |

## A判定の要約

変更なしでコード再利用できるAは、現時点ではstdlibだけで完結する汎用`timer`に限定する。Core/Extension分離やreportingの安全設計はコード資産ではなくCの参照原則、移植・改修済みtask10 builder/rendererはBである。その他の主要評価資産も、group-aware split、multiclass、provenance、schema validationのためB判定とする。

## 再利用禁止の要約

- 課題6 extension God Script。
- 既定stopwordを無条件採用する実装。
- 課題9の実験A〜D CLIを課題10へ丸ごとコピー。
- livedoor固有footer/category規則のメールへの流用。
- 課題9のハードコードされたレポート名・旧HTTP renderer。
- 課題8/Rabilooのコード断片を完成済みmoduleとみなすこと。
