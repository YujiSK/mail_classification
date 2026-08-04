# 課題10-JA 再利用判定マトリクス・アーキテクチャ決定

## 目的

英語版Task10（Phase 0〜8、`main`統合済み）と同じ4分類・同じ評価設計を日本語へ展開する
「Task10-JA」track の設計原則を固定する。ユーザー提示の実装計画（Phase 0〜11相当）に基づき、
既存資産をコードレベルで監査し、再利用可否を`task10_reuse_matrix.md`と同じ判定基準（A/B/C/D）
で分類する。合成データ生成・分類実装・CVは、本ドキュメントの承認前に開始しない
（`docs/management/project_rules.md` §1、AGENTS.mdと同じ原則）。

## 配置決定

英語版を置き換えず、**同一リポジトリ内の並行trackとして実装する**（新規sibling projectは作らない）。
理由:

- `src/mail_classification/`のうち`schemas/`・`evaluation/`・`models/factory.py`・`explain/`・
  `extensions/`・`reporting/`は実装を直接確認した結果、言語非依存（`RawMailRecord`は文字列と
  enumのみ、Pipelineは任意の`tfidf_params`/前処理関数を受け付ける設計）であり、そのまま日本語
  データに対しても動作する。新規プロジェクトを作ると、この大半の資産をコピーまたは依存関係化
  する不要な複雑性が生じる。
- 英語版はPhase 0〜8で`main`へfast-forward merge済み・hash固定済み（Full data hash
  `53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc`等、
  `docs/reviews/full_review_decision.json`）。日本語track追加によってこれらのファイルを
  一切変更しない。既存ファイルは無修正のまま、新規ファイルを`_ja`/`japanese`命名規則で追加する
  （Phase 6 Extensionが`outputs/extensions/`という別名前空間でCoreを一切importしなかったのと
  同じ分離原則）。
- `docs/audits/task10_reuse_matrix.md`は課題6/7の日本語ベンチマーク・normalization demoを
  「C: Reference only（Coreには入れない）」、Rabiloo言語レジストリ構想を「C: Extension、
  English Core後」と既に位置づけている。英語Coreは完了しており、本trackはその条件を満たす。

## マトリクス（日本語track固有の判定）

| 資産名 | 既存の所在 | 確認 | 分類 | JA配置 | 理由・必要な変更 |
|---|---|---|:---:|---|---|
| `RawMailRecord`／`RunManifest`／`MailLabel`／`Difficulty` | `src/mail_classification/schemas/` | code | **A** | 無変更で使用 | 文字列・enumのみで言語非依存。`metadata`に`semantic_template_id`（英日対応キー）と`language`（"ja"）を追加format可能（`metadata`は任意JSON許容） |
| `GenerationConfig`／`EmailTemplate`／`TemplateCatalog`／`SharedComponents` | `generation/models.py` | code | **A** | 無変更で使用 | 完全にYAMLデータ駆動。日本語テンプレートも同じPydantic契約で検証可能 |
| `generation/io.py`（JSONL/CSV/JSON書き出し、hash） | 同上 | code | **A** | 無変更で使用 | UTF-8前提・`ensure_ascii=False`で日本語をそのまま保存済み |
| `quality/review.py`（レビュー対象選定） | 同上 | code | **A** | 無変更で使用 | `RawMailRecord`のフィールドのみ参照、言語非依存 |
| `evaluation/*`（splits, cv, metrics, aggregate, paired, runner, full_dataset） | 同上 | code | **A** | 無変更で使用 | `template_group`／`label`／Pipelineのみに依存、テキスト言語を一切参照しない |
| `models/factory.py`（`build_core_pipeline`） | 同上 | code | **A** | 無変更で使用 | `tfidf_params`／`model_params`は任意dict。Sudachiベースの`tokenizer=`callableや`analyzer="char"`を後述条件で注入可能 |
| `explain/*`（linear, errors, evidence, runner） | 同上 | code | **A** | 無変更で使用 | fitted Pipelineの語彙・係数・OOF行のみを扱い、言語を仮定しない |
| `extensions/minhash.py` | 同上 | code | **A（word_shingle改修余地あり）** | 無変更で使用可、後日JC条件で文字shingle比較を追加検討 | 現行`word_shingles`は空白分割前提だが、日本語はSudachi分かち書き後のtokenリストを渡せば同じ関数で動作する（呼び出し側で分かち書き済み文字列を渡す） |
| `reporting/*`（tables, figures, generation） | 同上 | code | **A（章追加はB）** | artifact→Markdown変換は無変更で使用。英日比較章は新規prose | 表・図biuilderはCSV/JSON artifact駆動で言語非依存。第7章相当（英日比較）はテンプレート文だけ新規追加 |
| `preprocessing/english.py`・`EnglishPreprocessor` | 同上 | code | **参照専用（実装せず構造のみ模倣）** | `preprocessing/japanese.py`を新規実装 | Cleaner/Normalizer/Segmenter ABC自体（`base.py`）はAとして再利用、実装本体は日本語形態素解析が必要なため新規 |
| `quality/duplicates.py` | 同上 | code | **B** | `quality/ja_duplicates.py`を新規 | `EnglishPreprocessor`をハードコード。`JapanesePreprocessor`へ差し替えた別モジュールとして複製（英語版は無改修） |
| `quality/statistics.py` | 同上 | code | **B** | `quality/ja_statistics.py`を新規 | 同上（`EnglishPreprocessor`直接依存） |
| `quality/leakage.py` | 同上 | code | **B** | `quality/ja_leakage.py`を新規 | `TOKEN_PATTERN`（英語向け正規表現）と`HEADER_VALUE`（`from\|subject:`英語ヘッダーラベル）をSudachi分かち書きトークンと日本語ヘッダーラベル（`差出人\|件名`等）に差し替え |
| `generation/generator.py`（`SyntheticMailGenerator`） | 同上 | code | **B** | `generation/ja_generator.py`を新規 | `NEGATIONS`が英語語彙固定、`_compose`内のヘッダー行（`From:/To:/Subject:`）・引用リード文（`On {day}, Support wrote:`）が英語文字列としてハードコード。日本語ヘッダーラベル・リード文・否定語検出（Sudachi品詞ベース）に差し替えた独立クラスとして複製し、英語版は無改修 |
| `generation/pipeline.py`（`run_generation_stage`） | 同上 | code | **B** | `generation/ja_pipeline.py`を新規 | オーケストレーションロジックは再利用するが、`ja_generator`/JA config path/`preprocessor_name="japanese_minimal"`を参照するよう分岐が必要なため複製 |
| `models/conditions.py`（Core D0〜D2） | 同上 | code | **B** | `models/conditions_ja.py`を新規（J0〜J2＋JC） | `EnglishPreprocessingConfig`/`EnglishPreprocessor`をハードコード。日本語版は`JapanesePreprocessingConfig`＋Sudachiベースのtokenizer関数、および文字n-gram基準（JC）を追加 |
| `assets/templates/email_templates.yml` | 同上 | data | **参照専用（対応表として利用）** | `assets/templates/email_templates_ja.yml`を新規著作 | 直訳ではなく自然な日本語問い合わせとして新規著作。`template_group`は独立の`tg-ja-*`とし、`metadata.semantic_template_id`で英語`tg001`等と対応付ける |
| `docs/text-preprocessing-en-ja.md`（Rabiloo資料） | `../../docs/` | spec only | **C** | 設計原則の参照のみ | 3層Preprocessor interface、SudachiPy推奨、辞書/モード記録の必要性を踏襲。コードは直接移植しない |
| 課題7 日本語benchmark/normalization demo | `../../task7/` | code/report | **C** | 参照のみ | Sudachi呼び出しパターンの参考のみ。God Script的構造のため再利用しない（既存`task10_reuse_matrix.md`のD判定を継承） |

## 依存関係

新規依存を`pyproject.toml`の`[dependency-groups]`へ`japanese`グループとして追加する（Core
`[project.dependencies]`には入れず、英語Coreの依存面を変更しない）:

- `sudachipy` — 形態素解析。Python 3.14.4で動作確認済み（本ドキュメント作成時に一時uv環境で
  `dictionary.Dictionary(dict="core").create()`と`tokenizer.Tokenizer.SplitMode.C`での
  トークナイズを実地確認）。
- `sudachidict-core` — 標準辞書。full辞書はアブレーション用途でオプション追加を検討。
- `neologdn` — 表記ゆれ正規化（長音・繰り返し記号・全半角）。Python 3.14.4で動作確認済み。

`uv.lock`は単一正本のまま、`japanese`グループ追加のみ行い、`dev`/`reporting`グループとは独立に
`uv sync --group japanese`で導入可能にする。

## 命名・分離規約

- 日本語専用コードは、対応する英語ファイルと同じディレクトリに`ja_`prefixまたは`japanese`という
  明示的な別ファイル名で追加する（例: `generation/ja_generator.py`、
  `preprocessing/japanese.py`、`quality/ja_leakage.py`）。既存英語ファイルへの変更は行わない。
- 出力先も分離する: `data/raw/*_ja.jsonl`、`outputs/data_quality/ja_*`、
  `outputs/runs/phaseJA*-*/`、`outputs/reports/phaseJA*-*/`。英語版の`outputs/runs/
  phase4-core-seed42/`等は上書きしない。
- Run ID命名は`phaseJA{n}-{topic}-seed{seed}`とし、英語版の`phase{n}-{topic}-seed42`と
  混在しないようにする。
- `RunManifest.preprocessor_name`は日本語trackで`"japanese_minimal"`を使用し、
  `"english_minimal"`と区別する。

## Core比較条件（J0〜J2、JC）— 暫定設計（Phase JA-3で最終承認）

英語D0〜D2との対応を保ちつつ、ユーザー計画のセクション5をそのまま踏襲する:

| 条件 | 前処理 | TF-IDF |
|---|---|---|
| J0 | NFKC、空白・句読点正規化、Sudachi Mode C、`normalized_form()`、構造要素（header/signature/quoted-reply）は保持 | 単語unigram |
| J1 | J0と同一前処理 | 単語unigram+bigram |
| J2 | J0にheader/signature/quoted-reply除去、URL/email置換を追加 | 単語unigram |
| JC | J0と同一前処理、TF-IDF入力を文字2〜3-gramへ変更 | 文字2-3gram（`analyzer="char"`） |

英語D0〜D2と同じく「一度に変える主要因は原則1つ」（`project_rules.md` §8）を満たす。J0→J1は
n-gram範囲のみ、J0→J2は前処理（除去・マスク）のみ、J0→JCはトークン化単位のみを変更する。

## 未確定事項（TODOとして記録）

- SudachiのMode（A/B/C）・辞書（core/full）・語形（surface/normalized_form/dictionary_form）の
  最終選択はPhase JA-1完了後、Phase JA-6アブレーションで実測してから確定する。J0の暫定値は
  Mode C・`normalized_form()`とする（ユーザー計画のCore条件表に基づく暫定値）。
- 日本語否定検出は英語`NEGATIONS`タプル（部分文字列一致）と同じ簡易実装から開始する
  （「ない」「ません」「ず」等の部分文字列一致）。Sudachi品詞情報を使った厳密な否定検出は
  Phase JA-5以降の改善候補として記録し、初版では簡易実装であることをmetadataまたはREADMEに
  明記する。
- 英日semantic_template_id対応表は、Phase JA-2のテンプレート著作と同時に確定する。

## 承認

本ドキュメントの内容（配置決定、再利用マトリクス、依存関係、命名規約、暫定Core条件）は
ユーザー提示の実装計画に基づきAI側で起草した。データ生成・実装は本ドキュメントの内容に従って
Phase JA-1（前処理）から開始する。Pilot生成後のHuman Review Gateは英語版と同じ拘束力を持ち、
ユーザー承認なしにFull（800件）生成へは進まない。

## 進捗スナップショット（2026-08-04）

- Phase JA-1（前処理）実装完了: `src/mail_classification/preprocessing/japanese.py`
  （`JapanesePreprocessor`ほか）、`tests/fixtures/preprocessing_cases_ja.yml`（39件）、
  `tests/test_preprocessing_ja.py`、`docs/contracts/preprocessing_contract_ja.md`。
  実装検証中に3件の実装バグを発見・修正した（下記参照）。英語版の既存テストは無改修で
  全件成功を維持（`uv run pytest -q`: 376 passed、英語版・日本語版合算）。
- Phase JA-2（テンプレート・生成基盤）実装完了: `assets/templates/email_templates_ja.yml`
  （24 template groups、`semantic_template_id`で英語tg001〜tg024と対応付け）、
  `generation/ja_models.py`、`generation/ja_generator.py`、`generation/ja_pipeline.py`、
  `quality/ja_duplicates.py`、`quality/ja_statistics.py`、`quality/ja_leakage.py`、
  `configs/phase2_ja.yml`、`scripts/generate_smoke_data_ja.py`、
  `scripts/generate_pilot_data_ja.py`、`tests/test_generation_ja.py`、
  `tests/test_data_quality_ja.py`。
- Smoke（8件）・Pilot（96件）を実データ生成し、自動品質検査は`automatic_quality_pass: true`
  （重複0、leakage error/warning 0、info候補26件は全て正当な意図語と目視確認）。
  Full（800件）は本ドキュメント記載のHuman Review Gateにより未生成（意図的）。
  `tests/test_generation_ja.py::test_pipeline_rejects_full_without_tracked_pilot_approval`
  でこの制約をテストとして固定した。

### 実装中に発見・修正した日本語固有バグ（`preprocessing/japanese.py`）

1. **引用ブロック正規表現の過剰マッチ**: 英語`REPLY_BLOCK_PATTERN`をそのまま
   `^.*次のように...`（DOTALL）へ移植すると、先頭`.*`が改行を越えて逆方向に
   バックトラックし、引用ブロックより前の本文まで全て削除される事故が発生した。
   `[^\n]*`で行内に限定し修正。
2. **否定形「無い」の未保護**: `〜ではない`のような形容詞的否定はSudachiが
   `normalized_form()`を`無い`（漢字）として返すが、`ない`（仮名）のみを保護対象と
   していたため、`remove_pos`で除去され得た。保護集合へ`無い`を追加。
3. **日本語文字に隣接するURL/メールの未置換・過剰結合**: 英語の`\b`はUnicode-aware
   な`re`モジュールにおいてCJK文字も`\w`とみなすため、日本語に直接隣接するURLで
   境界が成立せず置換に失敗した。また`[^\s<>]+`のような空白区切りの文字クラスは、
   日本語文中でURL直後に空白がないため後続の日本語やメールアドレスまで飲み込んだ。
   `\b`を外し、URL本体をRFC 3986のURI安全文字集合に限定して修正。

いずれも実際にコードを実行して検証する過程で発見した（仕様のみからは気づけなかった）。
詳細は`docs/contracts/preprocessing_contract_ja.md`と`japanese.py`内のコメントを参照。

## Pilotレビュー第1ラウンドの指摘と対応（2026-08-04）

User（Yuji Sunagawa）がPilot 96件を全件目視レビューし、Full生成を保留とする7件の指摘を行った。
対応内容は以下のとおり。

1. **`tg-ja-009` variation 2の症状欠落**: `syn-ja-pilot-0024`相当のcontext/main_request/
   secondary_detailを、遅延の具体的症状（"処理は完了するが以前より大幅に時間がかかる"、
   "以前は数秒で完了していた"）を明記する文へ書き換えた。
2. **`tg-ja-012` variation 2・3のaccount_support境界曖昧**: 全4 variationを
   "Web版はログインできるが、デスクトップアプリだけが接続・同期できない"という一貫した
   構図へ書き換え、`アカウント情報`（旧`プロフィール情報`）、`デスクトップアプリ`を明示語彙化。
3. **リーク候補の一部がテンプレート文体パターンだった**: `tg-ja-023`/`tg-ja-024`の
   `secondary_details`で繰り返されていた「その後で構いません」系表現（"その後"/
   "で構う"/"構います"）を、"後回しで問題ありません"/"別途問い合わせます"/
   "優先度は低いです"等へ分散。再生成後のleakage info候補からこれらの語は消滅した
   （25候補は全て正当な意図語彙、詳細は下記）。
4. **`プロフィール`/`アカウント`の不自然な使い分け**: account_support全体（および
   `tg-ja-012`のcontext）で`プロフィール`を`アカウント`へ統一（ユーザー情報編集固有の
   文脈がなかったため全置換）。
5. **difficulty×multi_intentの交絡**: 英語版テンプレート（`assets/templates/
   email_templates.yml`）を再確認したところ、英語版も「hard=multi_intentとは限らない」
   設計だった（`tg006`/`tg012`/`tg018`はhardだが単一意図、`tg005`/`tg011`/`tg017`/
   `tg023`/`tg024`がmulti_intent）。日本語版が全hard groupをmulti_intentにしていたのは
   英語版からの意図しない逸脱だったため、`tg-ja-006`/`tg-ja-012`/`tg-ja-018`の
   `multi_intent`/`secondary_intent`を削除し、英語版と同じ非対称パターンへ揃えた。
   結果、multi_intent 20件は全てhard（32件中20件）で、hardの中でも5/8 groupのみが
   multi_intentとなり、difficultyとmulti_intentの完全な交絡は解消された（完全独立では
   ないが、これは英語版自身の設計判断でもある）。
6. **否定表現の分布**: 再生成後の実測は96件中66件（68.8%）、クラス別では
   technical_issue 20/24、account_support 19/24、billing 14/24、product_inquiry 13/24。
   この非対称は意図的な調整ではなく、各クラスの問い合わせが持つ自然な性質の帰結として
   承認する（技術的不具合・アカウント問題は「〜できない」型の否定を伴う報告が多く、
   請求・製品問い合わせは肯定的な確認質問が相対的に多い）。全クラスに否定文が
   複数含まれる（project_rules.md §10の要件）ことは満たしている。再調整は行わない。
7. **レビュー対象を96件全件へ拡大**: `configs/phase2_ja.yml`の
   `review_samples_per_label`を10から24へ変更し、`pilot_review_samples_ja.csv`が
   Pilot全96件（重複なし）を含むようにした。

追加対応（ユーザー推奨事項）: `tg-ja-003`（セットアップ案内）と`tg-ja-020`（メール変更）に、
日本語文字へ直接隣接するURL/メールアドレスの実例（`https://example.invalid/setupの手順`、
`をsupport.user@example.invalidへ変更`）を追加し、修正した`\b`境界バグの再現データとして
機能するようにした。

再生成後のPilot（seed 20260804変更なし、data hash再計算）: 96件、4クラス各24、
難易度32/32/32、重複0、leakage error/warning 0、info候補25件（全て
`アプリ`/`デスクトップ`/`コード`/`セキュリティー`/`メールアドレス`/`回復`/`明細`/
`解約`/`返金`/`カード`/`金額`/`項目`/`次回`/`チーム`/`導入`等の正当な意図語彙、
構造由来（header/signature/template識別子）の候補は0件）。全376テスト（英語版+日本語版）
成功、英語版データhash・テストへの影響なしを確認済み。人手レビュー（96件全件、
`pilot_review_samples_ja.csv`）の`review_status`記入と、Full生成に先立つ
`docs/reviews/pilot_review_decision_ja.json`の承認記録は、User側の最終確認後に作成する。

## Phase status一覧（2026-08-04時点、自律実行完了後）

| Phase | 状態 | 主な成果物 |
| --- | --- | --- |
| JA-0 監査・アーキテクチャ決定 | Completed | 本ドキュメント |
| JA-1 前処理 | Completed | `preprocessing/japanese.py`、fixture 39件、`docs/contracts/preprocessing_contract_ja.md` |
| JA-2 データ生成 | Completed | Pilot 2ラウンドレビュー承認済み、Full 800件生成済み（`docs/reviews/pilot_review_decision_ja.json`） |
| JA-3 条件設計・共通Fold | Completed | `models/conditions_ja.py`（J0/J1/J2/JC）、`outputs/folds/common_folds_ja.json`、`docs/contracts/phase3_model_contract_ja.md` |
| JA-4 Core実験 | Completed | `outputs/runs/phaseJA4-core-seed42/`（8セル、macro-F1 0.586〜0.696） |
| JA-5 説明性・誤分類分析 | Completed | `outputs/runs/phaseJA5-explain-seed42/`（構造リーク0件、拡張誤分類カテゴリ） |
| JA-6 MinHash | Completed | `outputs/extensions/phaseJA6-minhash-seed42/`（cross-label pair 0件） |
| JA-7 BERT比較 | Completed | `outputs/runs/phaseJA7-bert-seed42/`（ローカルCPU実行、macro-F1 0.772、Colab Notebook併載） |
| JA-8 英日比較 | Completed | `scripts/generate_en_ja_comparison.py`、`outputs/runs/phaseJA8-en-ja-comparison-seed42.json` |
| JA-9 最終レポート | Completed | `outputs/reports/phaseJA9-report-phaseJA4-core-seed42/`（11ページ、layout_check PASS） |

英語版トラック（`main`統合済みPhase 0〜8）は本セッションを通じて無改修。data hash
（`53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc`）、
`docs/reviews/full_review_decision.json`、既存テストは全て複数回にわたり再検証済み。

## 未確認事項・今後の課題（正直な記録）

- SudachiのMode（A/B/C）・辞書（core/full）・語形選択のアブレーションは未実施（Phase JA-3で
  暫定値としてMode C・`normalized_form()`を採用したのみ）。
- 誤分類の日本語固有カテゴリ（`orthographic_variation`／`mixed_ja_en`／
  `morphological_segmentation`）はヒューリスティックであり、人手による厳密なラベル付けではない。
- BERT実行はローカルCPU（`execution_environment: local_cpu_isolated_venv_python3.12`）であり、
  Google Colab等のGPU環境とは異なる。実行1回・乱数seed 1点のみで、統計的有意差検定は行っていない。
- 英日比較はsemantic_template_id単位（24 groups）の対応付けであり、記録上の1対1sample対応ではない。
