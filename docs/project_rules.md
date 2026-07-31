# 課題10 プロジェクト規約

本ファイルを課題10の規約の正本とする。実装前に必ず読むこと。

## 1. 優先順位

1. 大学の課題10要件
2. 本プロジェクトの実験計画
3. `docs/project_rules.md`
4. 設定ファイル
5. 個別スクリプト

矛盾は上位を優先し、勝手に補完せず、日報・監査文書・TODOのいずれかへ記録する。

## 2. ディレクトリ配置

最終責務は`docs/task10_architecture.md`の推奨構成に従う。

- 原本・キャッシュ: `data/raw/`
- 再生成可能な派生データ: `data/derived/`
- 小規模fixture/sample: `data/samples/`
- 再利用可能コード: `src/task10/`
- CLI/entrypoint: `scripts/`
- 設定: `configs/`
- テスト: `tests/`
- 実験結果: `outputs/runs/<run_id>/`
- レポート原稿: `reports/`
- 最終PDF・図表: `artifacts/`
- 一時render: `tmp/renders/`
- 文書: `docs/`
- 外部・移植ツール: `tools/`

必要になる前に空ディレクトリを大量作成しない。生成物を`src/`や`scripts/`へ置かない。

## 3. コード配置

- 再利用可能な関数・クラスは`src/task10/`、CLIは`scripts/`へ置く。
- Notebook、CLI、テストは同じ前処理moduleをimportする。
- import時に学習、download、network、ファイル生成を実行しない。
- 実験固有orchestrationと共通ロジックを分離し、God Scriptを作らない。
- 絶対パスをハードコードしない。root解決は単一の`paths.py`または明示引数に統一する。
- 設定値をコード・複数YAMLへ重複記述しない。設定schemaと既定値の正本を一つにする。
- 既存資産を再実装する前に`docs/task10_reuse_matrix.md`を確認する。

## 4. データ管理

- `raw_text`を上書きしない。`body_text`、`clean_text`等は派生列。
- 想定基本列: `raw_text`, `body_text`, `clean_text`, `label`, `template_group`, `difficulty`。
- 大容量raw/cache/derivedはGit管理しない。必要な小規模sample/fixtureだけ管理する。
- 生成config、seed、生成器version、実行日時、件数、class比、template数、重複数を保存する。
- 削除・除外・正規化の文書数・文字数・token数を処理別に記録する。
- Rabilooの実メール、顧客情報、社内機密を使用しない。
- 合成データであることをREADMEとレポートへ明記する。

## 5. 前処理

- Cleaning／Normalization／Segmentationを分離し、それぞれ個別ON/OFF可能にする。
- 学習時と推論時は同じversioned implementationを使用し、versionをmanifestへ保存する。
- raw textを保持し、文字数in/out、token数、削除数、placeholder数を記録する。
- tokenizer/analyzer/model resourceを文書ループ内で初期化しない。
- lowercase、stopword、stemming/lemmatizationを正解として固定しない。全てablationで判断する。
- stopword使用時は最低限`not`, `no`, `never`, `without`, `cannot`を点検し、問い合わせintentを壊さないcustom listを比較する。
- BERT系に古典モデル用の強い前処理を無条件適用しない。

## 6. データリーク

### 6.1 統計的リーク

- `TfidfVectorizer`、Scaler、Imputer、Encoder、Sampler、学習型特徴選択はPipeline内。
- fit/resampleは学習Foldのみ。検証Foldはtransform/predictのみ。
- SMOTEは学習Foldのみで、必要なscale後に配置する。
- 全データで語彙・IDF・閾値・特徴量を選ばない。
- outer testでthreshold tuningしない。必要時はinner CV。
- `Pipeline`外fitを検出するテストを持つ。

### 6.2 内容・メタデータリーク

- header、footer、signature、quoted reply、URL、email、path、label名、固定記号、template固有語、user/thread情報を別途検査する。
- 完全一致と正規化後一致を検査し、near duplicateは少なくとも監査対象にする。
- template groupのtrain/validation跨ぎを禁止する。
- group構造が実在するときはgroup-aware split。ないことを監査で確認した場合のみ通常`StratifiedKFold`。
- Pipeline利用だけでは内容リークを防げないことを全実験文書に明記する。

## 7. 評価

主指標候補は実験前にmacro-F1として固定する。変更が必要なら実行前に理由を記録する。

最低限保存:

- Accuracy
- macro Precision、macro Recall、macro-F1
- weighted-F1
- classwise Precision、Recall、F1
- confusion matrix
- Fold Long results
- CV mean/std
- fit/predict時間
- Fold語彙数

全条件・全モデルで同じsample/Fold indexを共有し、`folds.csv`を保存する。欠落・重複Foldはerrorにする。

## 8. 比較実験

- 一度に変更する主要因は原則1つ。
- 複数要因変更は「pipeline全体比較」と明記し、可能ならfactorial ablationを追加する。
- CoreとExtensionを設定・CLI・出力先で分離する。
- Core完成前にBERT、MinHashLSH、language detection等へ進まない。
- 実行後に主指標を都合よく変更しない。
- CV Foldを独立標本とした安易な有意差検定をしない。
- 差がFold変動より小さい場合は、処理時間、依存、保守性を含め簡素な条件を優先検討する。

## 9. 説明性

- 多クラス線形モデルは全クラス別に係数を抽出。
- 正係数、負係数、絶対値上位を区別。
- TF-IDF語彙をfeature nameへ戻す。
- Foldごとの語彙差を考慮し、係数と語彙を同じfitted Pipelineから取得。
- 評価用Fold modelと説明専用全データmodelを混同しない。
- 全データfitは`descriptive_full_fit`と明記し、一般化性能の根拠にしない。
- header、signature、記号、template語が上位特徴にないか人間が確認し記録する。
- 誤分類出力にはtrue/pred、class decision score、主要寄与特徴、原因仮説、difficulty、template group、header/signature/quote flagsを含める。

## 10. 合成データ品質

- labelごとのtemplate数と`template_group`を保存。
- template group単位でsplitする。
- 各categoryに短文、長文、曖昧文、否定文を含める。
- labelごとの固定挨拶・署名・email・長さ・句読点・format・生成順を検査。
- label名の本文混入を検査。
- 完全一致・正規化後一致・near duplicate候補を検査。
- label別文書長分布を比較。
- 生成後にseed付きrandom sampleを人間が目視し、確認者・日時・判断を保存。
- 特定語1個だけで分類できるデータを避ける。

## 11. テスト

最低限:

- 前処理の決定性、raw text非破壊
- header、signature、quoted reply除去
- URL、email、HTML
- empty document
- 否定表現
- emoji
- full-width alphanumeric
- mixed language
- unknown label、unknown category
- group splitのtrain/validation重複なし
- Pipeline外fitなし
- output schema
- same seed reproducibility
- Foldの全条件一致
- duplicate/label-token/length audit

前処理は30件以上の具体的input/expected caseを持つ。

## 12. 出力・レポート

- 結果はCSV/JSON/Parquet等の機械可読形式。
- Markdownへ数値を手動転記しない。表・図はartifactからscript生成。
- report生成だけで実験を再実行しない。
- 中間renderと最終artifactを分離。
- 通常PDF buildはMarkdown・manual設定を変更しない。
- auto layout repairは明示opt-in。
- manual設定をauto処理で上書きしない。
- PDF check JSONを保存。
- 選択run ID、config/data/result hashで世代不一致を検査。

## 13. 再現性・依存関係

各run manifestに保存:

- 全seed
- Python version、OS、library versions
- 実行日時
- Git commit hashとdirty状態
- preprocessing version
- model/feature settings
- data generation settings
- 実行command
- config hash、data hash、Fold artifact
- tokenizer/dictionary/model resource名とversion（使用時）

課題9の不足を繰り返さず、`pyproject.toml`と選定package managerのlock fileを一種類採用する。未固定状態で正式結果を生成しない。

## 14. 機密性

- Rabiloo社内データ、顧客情報、実メールを使用しない。
- output、log、screenshotに機密情報を含めない。
- dataを外部serviceへ送信しない。
- 合成データであることを明記。
- Rabiloo内部資料の文章を大学提出物へそのまま転載せず、出典を区別して自分の検証結果として書き直す。

## 15. 作業記録と変更管理

- `docs/daily_report_20260731.md`および後続日報へ工程の開始・完了時刻と結果を記録する。
- 不明点は推測実装せず、TODOまたは未確認事項として記録する。
- 既存結果を監査中に削除・上書きしない。
- テスト失敗を隠さず、環境要因とコード要因を分けて記録する。
