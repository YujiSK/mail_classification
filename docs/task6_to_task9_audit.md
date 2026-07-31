# 課題6〜9 実装・知見監査

## 1. 結論

課題9には、課題10へ引き継ぐ価値の高い評価・監査基盤が実在する。ただし課題10へそのままコピーすべきなのは限定的であり、評価レコード、Fold共有、Pipeline内fit、Core/Extension分離、PDFの非破壊ビルドという設計原則を中心に移植する。課題6〜8の「古典モデルには強い前処理が有効」は仮説であり、課題9の日本語実測では高度前処理がmacro-F1を改善せず処理時間を増やした。課題10では全前処理を採用前提ではなくアブレーション対象にする。

## 2. 課題6

### コードで確認できたこと

- `text_preprocessing.py`: NLTKとspaCyのtokenizer、lowercase、stopword、Porter stemming、WordNet/spaCy lemmatizationの表示比較。
- `text_preprocessing_extension.py`: NLTK bigram/trigram、`bert-base-uncased` WordPieceの既知語・未知語分割。

### レポート上の知見

- 否定語を含む既定stopwordの危険性。
- 学習時と推論時のPreprocessing Skew防止と前処理バージョン管理。
- BERTでは強い削除処理を避け、対応tokenizerを使う。

### Gapと過度な一般化

- コードは既定stopword集合から`not`等を保護していない。
- extensionはimport時にdownload/model load/実行を行うため再利用不可。
- n-gram/Subwordはデモであり分類精度の比較ではない。
- 「BoW/TF-IDFではstopword除去が必須」は絶対規則にしない。問い合わせの`not`、`no`、`never`、`without`、`cannot`は意味を反転・限定し得る。

## 3. 課題7

### コードで確認できたこと

- MeCabのIPAdic/UniDic/NEologd、Sudachi Mode A/B/C、Janome標準/ユーザー辞書を同一短文で比較。
- NFKCとneologdnを段階分離し、文字数・Sudachi token数を比較。
- 解析器を100回ループの外で初期化。

### レポート上の知見

- 辞書・分割単位・表層形/原形/正規化形・品詞処理で出力が変わる。
- NFKCには情報を潰す場合があり、適用はタスク依存。
- 日本語・英語混在、表記ゆれ、辞書バージョンが再現性に重要。

### Gap

- 固定短文中心で分類性能を測っていない。
- 初期化コスト、分位点、プロセス/thread safety、辞書バージョンを成果物に保存していない。
- 課題10は英語合成メールが前提なので、日本語解析コードの直接再利用は不要。設計上の「初期化をループ外」「バージョン保存」のみ引き継ぐ。

## 4. 課題8

PDFでBoW、TF-IDF、Embedding、Transformer、BERT、Hugging Face、LLMのコスト・説明性・文脈理解を比較し、メール分類にはTF-IDF＋LinearSVC/Logistic RegressionをCore、BERTを発展候補とする案を確認した。

ただし実装は存在しない。「TF-IDF＋線形モデルが最適」「強い前処理で精度が向上」は事前仮説に留める。BERTはCore完成後のみExtensionで比較し、同じraw data・Fold/group policy・指標で比較する。

## 5. 課題9の実装監査

### 5.1 コード構造

- 再利用可能ロジックは`src/experiments/`と`src/utils.py`、入口は`scripts/core`/`scripts/extra`、reportingは`src/reporting`に分離。
- 各実験の図・説明用全データfitはCLI側に残り、共通評価コードとは分離されている。
- `if __name__ == "__main__"`があり、共通モジュールimport時に実験は走らない。
- CLIは`sys.path`へrootを挿入し、rootを`__file__`から解決する。動くがパッケージングとしては暫定的。
- 絶対的なユーザー環境パスはソースにない。一方、既存layout JSONには生成時の絶対パスが保存され、ポータビリティが低い。
- `scripts/extra`には実験固有の集約・Markdown生成が大きく残り、一部重複がある。

### 5.2 評価基盤

| 機能 | 実装 | 入力 | 出力 | 監査結果 |
|---|---|---|---|---|
| 共通Fold | `src/utils.py:get_outer_splits` | X, y, seed, n_splits | index tuple list | A〜Dで1回生成し全条件・モデルへ渡す |
| モデルfactory | `src/experiments/models.py:build_model` | model name, overrides | 未学習estimator | 4モデル、seed設定、class_weight制約 |
| Fold評価 | `src/experiments/evaluation.py:evaluate_pipeline_cv` | factory, data, splits, metrics | Long records | Foldごとにclone/fit/predict、時間保存 |
| CV集約 | `summarize_cv` | Long records | mean/std/count | 実装・CSVあり |
| ペア差 | `paired_fold_diff` | conditions付きLong records | mean/std/改善・悪化数 | 同一model/metric/fold indexで差分 |
| 線形係数 | `extract_linear_coefficients` | fitted pipeline, names, class index | 正/負/絶対値上位 | 多クラスは呼出側でclass indexを選択 |
| 木重要度 | `extract_tree_importances` | fitted pipeline, names | impurity importance上位 | バイアス注意を計画・報告に記載 |
| 出力dir | `ensure_output_dir` | experiment id | `outputs/exp_*` | mkdirを自動化 |
| 環境保存 | `collect/save_environment_info` | experiment id | JSON | Python/OS/主要packageを保存 |

Gap:

- `paired_fold_diff`は欠落・重複FoldやNaNを明示検証しない。
- Fold定義そのものを独立artifactとして保存せず、seedから再生成する。
- fit/predictは単回計測。前処理単独、中央値・分位点、warm-upは基本実験で未実施。
- 環境JSONに実行日時、Git hash、コマンド、設定hash、データhash、辞書version/path、前処理versionがない。
- 依存関係lockがない。

### 5.3 統計的リーク

確認できた防止策:

- A: `StandardScaler`をPipeline内に配置。
- B: `SimpleImputer`、`OneHotEncoder`、`StandardScaler`を`ColumnTransformer`/Pipeline内に配置し、欠損注入はouter trainだけ。
- C: `StandardScaler`→`SMOTE`→modelを`imblearn.Pipeline`に配置。
- D: `TfidfVectorizer`をPipeline内に配置しFold trainだけで語彙・IDFをfit。
- threshold Extension: outer testを閾値選択に使わずinner OOFで閾値を決定。
- Permutation Importance Extension: 各held-out Fold上で算出。

留保:

- Dの全データ語彙数計測は記述統計であり評価には使っていない。
- 説明用係数・重要度は全データfitで、評価値ではなく記述的分析とコメントされている。
- ハイパーパラメータvalidation curveは同じCV結果を一般化性能として別holdoutで再評価していない。課題10では探索と最終性能評価を分離する。

### 5.4 内容・メタデータリーク

- livedoor本文末尾の`■関連リンク`/`■関連記事`を`_strip_footer`で除去。
- own category literal件数をCSV保存。
- `raw_text` SHA-256完全一致を6件除去。
- URL/filename/date/group構造監査をExtensionで保存。

不足:

- header、署名、引用、URL、固定記号、投稿者、テンプレート語を包括的には検査していない。
- exact duplicateはあるがnear duplicate/MinHashは未実装。
- 「明示group IDがない」ことは潜在的な内容類似groupがない証明ではない。
- Pipelineは統計的リークを防ぐが内容リークは防がない。この2種類を課題10では別チェックにする。

### 5.5 実験設計

- Core/Extensionを出力先とスクリプトで分離。
- A〜Cは主要因を比較的分離。
- D Coreはcleaning、analyzer、dictionaryが同時に変わるため「パイプライン全体比較」とコードに明記。
- D ExtensionはD0〜D3の2×2でcleaning/analyzerを分離。
- 不均衡実験はAccuracyだけでなくPR-AUC、Recall、Precision、F1、Balanced Accuracy、MCC、混同行列を保存。
- Before/Afterは共通Foldでペア化し、Foldを独立標本とみなす有意差検定は行っていない。

課題10への注意:

- primary metricを実行前にmacro-F1へ固定。
- 前処理の主要因は原則1つずつ変更。複数変更ならpipeline comparisonと明記。
- template groupがあれば`StratifiedGroupKFold`、なければ`StratifiedKFold`。無条件にどちらかへ固定しない。

### 5.6 説明性

- 正係数、負係数、絶対値上位を区別。
- TF-IDFは`get_feature_names_out()`で語彙へ戻す。
- 多クラスDは代表3クラスだけ抽出しており全クラス網羅ではない。
- Foldごとの語彙・係数は保存せず、説明用全データモデル中心。
- 課題10では全クラス、Fold-awareな特徴量名、性能評価モデルと説明専用モデルの区別、誤分類ごとの寄与を追加する。

### 5.7 処理時間

- `time.perf_counter()`でFold fit/predictを計測。
- Cのfit時間はScaler/SMOTE/modelを含むEnd-to-Endで、SMOTE単独ではない。
- Dは形態素解析とcleaningを全コーパス単回計測。
- D Coreでは`cleaned_text`を作った後に`SudachiTokenizer.tokenize`が再度`clean()`するため、Sudachi側計測に再cleaningが混入する。報告値を単純加算すると範囲が分かりにくい。
- D Extensionはcleaningとtokenizationをより明示的に分離したが、反復1回。

### 5.8 再現性

実装済み:

- seed 42、Python/OS/主要package versions、データ元・条件、出力CSV。

不足:

- pinned requirements/lock、Git commit、実行コマンド、実行日時（Core JSON）、設定snapshot/hash、dataset generation manifest/hash、辞書version/path、前処理version。

### 5.9 PDF生成・検査

確認できた機能:

- Markdown→HTML→Chrome PDF。
- CSS、相対画像用document root、中間HTML、source registry。
- 見出し孤立、図/キャプション分断、短い表/コード分断、margin overflow。
- CJK glyph差をNFKC/既知置換/tri-gramで照合。
- `PASS`/`FAIL`/`INDETERMINATE`を分離。
- 通常ビルドは設定非更新、自動修復は`--auto-repair` opt-in。
- manual/generatedとmain/extraを分離。
- 最大3回、改善しない候補をrollback。
- lock、temp file、fsync、`os.replace`で対象generatedのみatomic保存。
- 本文Markdownを変更せずCSS class overrideだけ適用。
- 全28テストのうちサンドボックス内で27件成功し、HTTPソケット制限で実行失敗したPDF E2E 1件は制限のない環境で個別成功。コード起因の失敗は確認されていないが、同一環境での一括28 passedではない。

制約:

- checkerはテキストマッチとPDF画像数によるheuristicで、視覚品質の完全証明ではない。
- 図ページに別画像があっても誤って同一図とみなす可能性がある。
- Chrome binary、localhost、Linux `fcntl`に依存する元実装は移植調整が必要。
- 課題10へは既に`tools/pdf_renderer`としてパス・Chrome検出・file URIを修正済み。layout pipeline/checker全体の再統合は文書/設定名を汎用化してから行う。
- 現在のPDF/layout JSONは20/30ページだが、`execution_plan.md`には18/34ページと残る。これは結果と説明の世代不一致であり、課題10でrun ID・hash照合を導入する直接の根拠となる。

## 6. 課題間の矛盾・重複

- 課題6/8・Rabilooの「古典モデルには重い前処理」が、課題9 Dの実測では支持されなかった。
- 課題7は日本語正規化が語彙を整理する一般論を示すが、課題9 DではAfter語彙数が42,123→46,936へ増えた。
- 課題6 extensionとRabilooはSubwordの利点を説明するが、課題10でのBERT性能は未実測。
- 課題6/7のデモコードと課題9 preprocessingにはtokenizer初期化・正規化ロジックの重複がある。古いデモを統合せず、課題10用interfaceを新規設計する。

## 7. 課題10へ引き継ぐ原則

1. 前処理は採用前提ではなくアブレーション条件。
2. raw textを不変に保持し、body/clean等を派生列にする。
3. 統計的リークと内容リークを別々に監査。
4. 全条件・全モデルで共通Fold。
5. template groupがある場合はgroupを跨がせない。
6. Fold Long、集約、ペア差、時間、語彙、環境を機械可読保存。
7. Core完了前にBERT/MinHash/language detectionへ進まない。
8. 説明用全データfitと評価用Fold fitを混同しない。
9. レポートは結果artifactから生成し、手動転記しない。
10. PDF通常ビルドは非破壊、自動修復はopt-in。

## 8. 課題10で再検証する仮説

- lowercase、stopword、lemmatization、word n-gramはmacro-F1を改善するか。
- 否定語保護がbilling/account/technical intentの混同を減らすか。
- word TF-IDFとcharacter n-gramのどちらが合成表記ゆれに頑健か。
- template-aware splitでrandom splitより性能が低下するか。
- metadata/header/signatureを除くと見かけの性能がどれだけ下がるか。
- LinearSVCとLogistic Regressionの性能・確率/score・説明性・時間の差。
- 高度前処理の差がFold変動を超えるか。超えない場合、速度・保守性で簡素な条件を選ぶべきか。
