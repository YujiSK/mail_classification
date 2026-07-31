# 課題6〜9・Rabiloo資産インベントリ

## 1. 監査条件

- 監査日: 2026-07-31（Asia/Bangkok）
- 課題10リポジトリ: `task10`
- 課題10ブランチ: `agent/pdf-renderer-port`
- 課題9ローカルリポジトリ: `../task9`
- 課題9 remote: `git@github.com:YujiSK/nlp-preprocessing-eval.git`
- 課題9監査コミット: `969fdb01ae9ac63239327ca122918f791631877b`
- 課題9ブランチ: `main`（`origin/main`と一致）
- 課題9作業ツリー: 提出PDF `課題９：NLP比較.pdf` のみ未追跡。監査では変更していない。

最初に `git status`、`git branch --show-current`、`git log -5 --oneline`、`git ls-files` を実行し、その後ワークスペース、親・兄弟ディレクトリ、Git管理ファイルと非管理ファイルを検索した。大規模データの再取得と実験再実行は行っていない。

## 2. 確認できた資産

### 2.1 課題6

| 種別 | 所在 | 確認内容 |
|---|---|---|
| コード | `../task6/text_preprocessing.py` | NLTK/spaCyのtokenize、lowercase、stopword、stemming、lemmatization比較 |
| コード | `../task6/text_preprocessing_extension.py` | NLTK bigram/trigram、BERT WordPieceの既知語・未知語分割デモ |
| レポート | `../task6/課題６：英語テキストの前処理.pdf` | 英語前処理、否定語、n-gram、Subword、Preprocessing Skewの説明 |

実装上の注意:

- `text_preprocessing.py` は関数化されているが、spaCyモデルを関数呼び出しごとに初期化する。
- `text_preprocessing_extension.py` はimport時にNLTKデータ取得、出力、Hugging Faceモデル取得を実行するGod Scriptであり、再利用可能モジュールではない。
- 課題6固有のテスト、設定、依存固定、機械可読出力は見つからなかった。
- `not`、`no`、`never`の危険性はレポートで確認したが、コードは既定stopword集合をそのまま使い、保護していない。

### 2.2 課題7

| 種別 | 所在 | 確認内容 |
|---|---|---|
| コード | `../task7/benchmark_ja_nlp.py` | MeCab/IPAdic・UniDic・NEologd、Sudachi A/B/C、Janome標準/ユーザー辞書の比較と100回平均 |
| コード | `../task7/benchmark_ja_normalization.py` | Raw/NFKC/NFKC+neologdn、Sudachi Mode C、文字数・トークン数比較 |
| レポート | `../task7/課題７：日本語テキストの前処理.pdf` | 正規化、辞書、分割モード、原形/正規化形、品詞等の考察 |

実装上の注意:

- 解析器は各比較グループまたはモジュールで1回初期化され、計測ループ内の再初期化は避けている。
- ベンチマークは固定の短文1件が中心で、初期化時間を含まず、ウォームアップ・分位点・環境メタデータを保存しない。
- `benchmark_ja_nlp.py` はJanomeユーザー辞書の一時ファイルを通常経路では削除するが、例外時の確実なcleanupではない。
- テスト、依存固定、CSV/JSON出力は見つからなかった。

### 2.3 課題8

| 種別 | 所在 | 確認内容 |
|---|---|---|
| レポート | `../task8/課題８：AI・NLP技術.pdf` | BoW、TF-IDF、Embedding、Transformer、BERT、Hugging Face、LLM、メール分類案 |

課題8には対応するPython、テスト、設定、実行結果を確認できなかった。したがってTF-IDF＋LinearSVC/Logistic RegressionやBERT比較は「設計知見」であり、「既存実装」ではない。

### 2.4 課題9

| 種別 | 所在 | 確認内容 |
|---|---|---|
| 説明 | `../task9/README.md` | 構成、実行方法、Core/Extension、PDF、既知の制約 |
| 計画 | `../task9/docs/execution_plan.md` | 評価・リーク・出力・再現性計画と実施チェック |
| 共通コード | `../task9/src/utils.py` | 共通Fold、時間、Long保存、出力先、環境情報 |
| 共通コード | `../task9/src/experiments/evaluation.py` | Fold評価、集約、Before/Afterペア差 |
| 共通コード | `../task9/src/experiments/models.py` | 4モデルファクトリ |
| 共通コード | `../task9/src/experiments/explainability.py` | 係数と木重要度 |
| 共通コード | `../task9/src/experiments/preprocessing.py` | livedoor読込、フッター除去、完全重複、形態素解析器 |
| CLI | `../task9/scripts/core/` | 実験A〜D |
| Extension | `../task9/scripts/extra/` | PI、coverage、nested threshold、D 2×2、構造監査、図・レポート補助 |
| PDF基盤 | `../task9/src/reporting/` | Markdown→HTML→PDF、source registry、検査、修復 |
| 設定 | `../task9/configs/layout_overrides.yml` | manual/generated・main/extra分離 |
| テスト | `../task9/tests/` | 共通基盤とPDF検査・修復 |
| 実行結果 | `../task9/outputs/exp_*` | Fold Long、集約、ペア差、説明性、時間、図、環境 |
| レポート | `../task9/outputs/SUMMARY_REPORT*.md/.pdf` | CoreおよびExtension報告 |
| PDF監査結果 | `../task9/outputs/reports/` | レイアウトJSON/Markdown、設計監査 |
| キャッシュ | `../task9/data_cache/` | livedoor/OpenMLのローカルキャッシュ。Git非管理 |

課題9のテスト結果:

- 全28テストのうち、サンドボックス内では27件成功し、HTTPソケット制限によりPDF E2Eテスト1件が実行失敗した。
- 当該テストを制限のない環境で個別に再実行し、成功を確認した。
- コード起因のテスト失敗は確認されなかった。同一環境で一括28 passedしたという意味ではない。
- 6件の`ConvergenceWarning`は未標準化Logistic Regressionの想定された収束上限到達。
- テスト実行前後で課題9の作業ツリーに新規変更なし。

成果物世代の注意:

- 現在の`outputs/reports/layout_summary_report*.json`とPDFは本編20ページ・発展版30ページ。
- `docs/execution_plan.md`の完了記録には18ページ・34ページとあり、過去世代の記述が残っている。
- layout JSON内のPDF pathは生成ホストの絶対パス。現在ファイルは存在するが、課題10ではrun manifest/hashによる世代一致と相対pathを必須にする。

### 2.5 Rabilooオンボーディング

| 種別 | 所在 | 確認内容 |
|---|---|---|
| 原文 | `../docs/text-preprocessing-en-ja.md` | 英日テキスト前処理の原則と3日演習 |
| 日本語版 | `../docs/text-preprocessing-en-ja.ja.md` | 原文の日本語訳 |

Cleaning／Normalization／Segmentation、独立ON/OFF、`Preprocessor`＋registry、raw保持、処理統計、30件以上のテスト、exact/near duplicate、MinHashLSH、language detection、古典/BERT比較、解析器再利用、Notebook/実行コード共通importを確認した。ただし後半の`preprocess/`構成やMinHash等は「演習の要求仕様」であり、実装コードは資料内に存在しない。

## 3. 調査できなかった・存在しなかった資産

| 資産 | 状態 | 判断への影響 |
|---|---|---|
| 課題6のテスト・設定・実行結果CSV/JSON | 見つからない | 動作範囲と再現性は未確認 |
| 課題7のテスト・設定・実行結果CSV/JSON | 見つからない | 表示結果以外の再現性は未確認 |
| 課題8のソースコード・テスト | 見つからない | 全項目をReference onlyとして扱う |
| Rabiloo資料で要求する完成済み`preprocess/` package | 見つからない | 要求仕様は参考にするが既存資産とはみなさない |
| Rabilooの30件以上のtest cases | 見つからない | 課題10で新規作成が必要 |
| RabilooのMinHashLSH/language detection実装・結果 | 見つからない | Extension候補、未確認 |
| 課題9のpinned requirements/lock | 存在しない（READMEにも明記） | 課題10で解消必須 |
| 課題9の実行時Git hash・実行コマンド・辞書バージョンを一括保存したmanifest | 存在しない | 課題10で新規manifestが必要 |
| ワークスペース既存AIエディタ規約 | `.cursorrules`、`.cursor/rules`、Copilot instructions、`AGENTS.md`とも見つからない | 課題10ではCodex/汎用エージェント向け`AGENTS.md`を採用 |

## 4. 証拠レベル

本監査では以下を区別する。

1. **コード確認**: 関数・クラス・CLI・テスト本体を読んで確認。
2. **実行確認**: 軽量テストまたは既存の機械可読成果物で確認。
3. **レポート確認**: PDF/Markdownの説明のみ。コード確認がなければ実装済みとはしない。
4. **未確認**: 資産が見つからず推測できない。

PDF内のコード断片やRabilooの演習用疑似構成は、再利用可能な既存モジュールには数えていない。
