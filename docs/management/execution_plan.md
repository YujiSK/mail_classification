# 課題10 開発実行計画

| Item | Current snapshot |
| --- | --- |
| Project | Task 10: English synthetic inquiry-mail classification |
| Last verified | `2026-07-31T17:01:47+07:00` |
| Phase 2B implementation | `5fd02f4fed3b451d6e3fa4fd1c579fa7b808d254` |
| Phase 2C implementation | `e37ea0de86876c2b93ef1d91cb5cf4b611661002` |
| Phase 3 implementation | `1a44c81`（scikit-learn導入・Full hash契約・共通Fold・model factory・Core条件D0〜D2） |
| Phase 4 implementation | `9a6cf25`（Core実験runner、実データ実行結果`outputs/runs/phase4-core-seed42/`はGit非追跡・再現可能） |
| Phase 3〜4を`main`へ統合 | `77266ce`（`agent/task10-phase3-model-foundation`から`main`へfast-forward merge、push済み） |
| Phase 5 implementation | commit未確定（本コミット作成時に追記予定）。実データ実行結果は`outputs/runs/phase5-explain-seed42/`（Git非追跡・再現可能） |
| Branch | `agent/task10-phase5-explainability`（`main`＝`77266ce`から新規作成） |
| Current phase | Phase 2〜4 `Completed`（`main`へ統合・push済み）。Phase 5 `Completed`（本branch、pushはこの後実施） |
| Status sources | 実在するGit履歴、`docs/management/daily_report_20260731.md`、機械可読のSmoke/Pilot/Full manifest・品質artifact・追跡対象review decisions |
| Remote note | `main`は`77266ce`まで同期済み。`agent/task10-phase5-explainability`はPhase 5実装commit後にpush予定 |

Coreテーマ:

> TF-IDFと線形分類モデルを用いた問い合わせメールの自動振り分け、および前処理・データリーク・誤分類要因の評価

## 1. 正本文書と計画書の境界

本書はPhaseの目的、依存関係、主要作業、成果物、完了条件、移行Gateを管理する。詳細仕様は複製せず、次の実在する正本を参照する。

- プロジェクト規約: `docs/management/project_rules.md`
- Architecture: `docs/architecture/task10_architecture.md`
- 再利用判断: `docs/audits/task10_reuse_matrix.md`
- 前処理契約: `docs/contracts/preprocessing_contract.md`
- 合成データ設計: `docs/architecture/synthetic_data_design.md`
- データ品質契約: `docs/contracts/data_quality_contract.md`
- 人間レビュー手順: `docs/contracts/human_review_guide.md`
- Phase 3依存・Fold・model契約: `docs/contracts/phase3_model_contract.md`
- 実行履歴: `docs/management/daily_report_20260731.md`

Phase 4以降の詳細仕様書は現時点で確認できないため正本として扱わず、必要になったPhaseのPlanned成果物とする。古いbranch、HEAD、進捗値は本書へ履歴として蓄積せず、冒頭のcurrent snapshotだけを更新する。履歴の正本はGitと日報である。

## 2. 全体方針

- 課題9で確認した共通Fold、Fold Long結果、Pipeline内fit、Core/Extension分離、非破壊reportingを課題10向けに適応する。
- TF-IDF等の学習型処理は各学習FoldのPipeline内だけでfitし、統計的リークを防ぐ。
- metadata、template、header、signature、重複による内容リークは統計的リークと別に監査する。
- 全モデル・全比較条件は、一度保存・検証した共通Fold artifactを再利用する。
- Fold単位結果、CV平均・標準偏差、OOF予測を機械可読形式で保存する。
- 強い前処理を有効と決めつけず、主要因を分離したアブレーションで実測する。
- Core実験の主指標はmacro-F1とし、Phase 3完了前に評価契約へ固定する。Accuracy、macro／weighted指標、クラス別Precision・Recall・F1も併記する。
- Coreを優先し、BERT、MinHashLSH等のExtensionはCore完了後に別設定・別出力で実施する。
- レポートの数値・表・図は機械可読artifactから生成し、手動転記・手動修正を避ける。
- 最終的にMarkdown、図表、PDF、layout検査、config/data/result hashの世代照合まで再現可能にする。

## 3. Phase別ロードマップ

### Phase 0 — 課題6〜9資産監査・再利用設計

**Purpose（目的）**

過去資産を実コード、実行結果、レポート上の知見に分け、課題10へ安全に再利用する境界と規約を確立する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Completed`
- Actual: `Completed`
- Evidence: commits `db7b869`, `36a38f9`; `docs/audits/prior_artifacts_inventory.md`, `docs/audits/task6_to_task9_audit.md`, `docs/audits/task10_reuse_matrix.md`, `docs/architecture/task10_architecture.md`, `docs/management/project_rules.md`, `AGENTS.md`

**Prerequisites（前提条件）**

- 課題6〜9とRabiloo資料へアクセスできること。
- READMEの主張だけでなくコード、テスト、設定、出力を確認すること。

**Main tasks（主な作業）**

- 資産インベントリ、課題9コード・リーク・評価・PDF基盤監査。
- A/B/C/D再利用分類、Gap整理、Architecture・project rules策定。

**Main outputs（主な成果物）**

- 上記の実在する監査・設計文書とAI editor rules。

**Validation（検証方法）**

- 実在path、Git commit、テスト結果、機械可読出力との照合。
- Markdownと`git diff --check`の検証。

**Completion criteria（完了条件）**

- 主要資産の根拠付き分類、未確認事項、課題10設計原則が文書化される。
- 課題10本実装前の承認が得られる。

**Transition gate（次Phaseへの移行条件）**

- 監査・規約・Architectureが承認され、先行実装禁止が解除される。

**Main risks（想定リスク）**

- レポート記述を実装済みと誤認すること。
- 課題9固有コードや過去の前処理一般論を無条件コピーすること。

**Out of scope（今回実施しないこと）**

- データ生成、分類、CV、レポート本文の実装。

### Phase 1 — 基盤Schema・前処理契約・テスト

**Purpose（目的）**

raw data、run manifest、Fold artifactと、非破壊・決定的な英語3層前処理の契約をモデル実装より先に固定する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Completed`
- Actual: `Completed`
- Evidence: commits `80c5f52`, `a01d49a`, `8b78261`; `pyproject.toml`, `uv.lock`, `src/mail_classification/schemas/`, `src/mail_classification/preprocessing/`, `configs/phase1.yml`
- Historical Phase 1 gate: 77 tests passed。現baselineではPhase 2追加分を含む114 tests passed。

**Prerequisites（前提条件）**

- Phase 0完了。
- 依存管理方式、ラベル、raw非破壊、内容リークと統計的リークの分離が合意済み。

**Main tasks（主な作業）**

- Pydantic schema、SHA-256規則、timezone・JSON互換性検証。
- Cleaning／Normalization／Segmentation interfaceと英語最小実装。
- 36前処理fixture、schema/config/import副作用テスト。
- Core／Dev／Reporting依存group分離。

**Main outputs（主な成果物）**

- `pyproject.toml`, `uv.lock`
- `src/mail_classification/schemas/`
- `src/mail_classification/preprocessing/`
- `docs/schemas/`, `docs/contracts/preprocessing_contract.md`
- `tests/test_preprocessing.py`, `tests/test_schemas.py`, `tests/test_config.py`, `tests/test_import_safety.py`

**Validation（検証方法）**

- JSON round-trip、raw非破壊、決定性、否定語保護、未知値拒否、import副作用なし。
- Core-only/all-groups同期、pytest、lock、diff検査。

**Completion criteria（完了条件）**

- schema・前処理契約と文書が一致し、Phase 1テストが全件成功する。
- dependency source of truthが`pyproject.toml`＋`uv.lock`に一本化される。

**Transition gate（次Phaseへの移行条件）**

- Phase 1固定commitが公開され、作業ツリーcleanからPhase 2 branchを開始できる。

**Main risks（想定リスク）**

- raw上書き、未実装機能の黙認、import時download、依存正本の複数化。

**Out of scope（今回実施しないこと）**

- 合成データ、scikit-learn、学習、CV。

### Phase 2 — 合成メール生成・品質保証

**Purpose（目的）**

機密情報を使わず、seed再現可能でtemplate・内容リークを監査できる英語問い合わせデータを確定する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Completed`
- Actual: `Completed`
- Preparation: `Completed`
- Generator/quality implementation: `Completed` at local commit `a59d3a7`
- Smoke/Pilot and automatic quality gate: `Completed`
- Human Review Gate: `Approved` after source correction and regenerated review
- Full implementation: `Completed` at commit `e37ea0d`
- Full generation and automatic QA: `Completed`
- Full Human Spot Review: `Approved`
- Actual Pilot manifest: `outputs/manifests/phase2-pilot-seed20260731.json`
  - `git_commit`: `397683ce891a67884d158ac240e8c929aad2f48f`
  - `git_dirty`: `true`（Human Review修正のcommit前に再生成）
  - data hash: `a7679feb78155dbd8ee50b43ff78200bcc3117060ea0811d31cc1a2a7cb98a94`
- Actual Pilot summary: 96 records、4 classes各24、easy/medium/hard各32、24 groups、exact/normalized duplicates 0、leakage error 0/warning 0/info 10、automatic pass。自動生成summaryは設計上human review pending／Full不可を維持する。
- Tracked review decision: `docs/reviews/pilot_review_decision.json`。60件全pass、info候補10種類を意図語として確認し、Pilot data/template/review CSV/leakage findings/output-side decisionのhashを固定。Phase 2C ready。
- Actual Full manifest: `outputs/manifests/phase2-full-seed20260731.json`
  - `git_commit`: `e37ea0de86876c2b93ef1d91cb5cf4b611661002`
  - `git_dirty`: `false`
  - data hash: `53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc`
- Actual Full summary: 800 records、4 classes各200、class内urgency各50、24 groups各33/34、class内difficulty各67/67/66、exact/normalized duplicates 0、leakage error 0/warning 0/info 10、automatic pass。
- Tracked Full review decision: `docs/reviews/full_review_decision.json`。24 template groups各1件を含む24件全pass、info候補10種類を意図語として確認し、Full data/config/template/review/leakage/summary/manifest hashを固定。Phase 3 ready、未着手。

**Prerequisites（前提条件）**

- Phase 1固定済み。
- `docs/architecture/synthetic_data_design.md`, `docs/contracts/data_quality_contract.md`, `docs/contracts/human_review_guide.md`の実在と整合。

**Main tasks（主な作業）**

- 完了: 24 template groups×4 variations、共有surface components、seed固定generator。
- 完了: Smoke 8件、Pilot 96件、manifest・hash・品質summary・重複/leakage/review CSV。
- 完了: 初回63件reviewで`we`、urgency偏り、`tg024`不備を検出し、生成sourceを修正。
- 完了: 追加Punch Listに基づき`tg005`、`tg018`、`tg021`を自然な文脈へ修正し、`tg023`へ別intentの罠を加えてHard根拠を強化。
- 完了: 再抽出60件を全件確認。この60件にはinfo候補10種類の該当sampleを含み、全件pass。
- 完了: Full 800件のclass 200、urgency 50、group 33/34、difficulty 67/67/66の決定的配分、Pilot承認hash Gate、Full QA、24 group spot reviewを実装。
- 完了: clean・remote同期済み`e37ea0d`からFullを2回生成し、data/summary/review/leakage artifactの完全一致を確認。
- 完了: 24件spot reviewとinfo候補10種類を確認し、全件passとして機械可読な承認証拠へ固定。

**Main outputs（主な成果物）**

- Tracked: `configs/phase2.yml`, `assets/templates/email_templates.yml`
- Tracked: `src/mail_classification/generation/`, `src/mail_classification/quality/`
- Tracked: `scripts/generate_smoke_data.py`, `scripts/generate_pilot_data.py`, `scripts/generate_full_data.py`
- Tracked: Phase 2 tests and three Phase 2 contract documents。
- Generated/ignored but verified: `data/raw/smoke_emails.jsonl`, `data/raw/pilot_emails.jsonl`
- Generated/ignored but verified: `outputs/data_quality/`, `outputs/manifests/`
- Generated/ignored review evidence: `outputs/data_quality/pilot_review_decision.json`
- Generated/ignored but verified: `data/raw/full_emails.jsonl` and matching quality/manifest/review-decision artifacts。
- Tracked Full approval evidence: `docs/reviews/full_review_decision.json`

**Validation（検証方法）**

- Phase 2C実装後の`pytest -q`: 126 passed。
- 同一seedによるPilot hash一致、schema/JSONL round-trip、4 label・難易度・group/variation coverage。
- exact/normalized duplicate、label/template/header/signature/metadata/length監査。
- `outputs/data_quality/pilot_review_samples.csv`全60件とinfo候補10種類を目視確認。
- 一時directoryでFull 800件dry run: automatic pass、duplicate 0、error/warning 0、info 10、spot review 24 groups、Pilot approval hashをmanifestへ保存。
- clean commit `e37ea0d`からFullを2回生成し、data、summary、review CSV、leakage findingsのSHA-256一致を確認。
- Full manifestの`git_dirty: false`、commit/config/template/data/Pilot-approval hashを確認。
- Full review CSV 24件は24 groups、全class/difficulty、長短、構造、否定、multi-intent、info候補10種類を覆い、24/24 pass。

**Completion criteria（完了条件）**

- Human Review Gateを全件完了し、修正要求が残らない。
- 必要なtemplate/rule修正後もautomatic quality passを維持する。
- Fullを生成し、重複・内容リーク・balance・hash・manifest検査に合格する。
- Full data hashとtemplate groupを固定し、Phase 3入力として承認する。

**Transition gate（次Phaseへの移行条件）**

- Full生成、品質検査合格、人間レビュー完了、data/config/template hashとtemplate group確定。

**Main risks（想定リスク）**

- template暗記、class固有語・surface pattern、synthetic artifact、レビュー未完了でのFull実行。
- 自動検査合格を人間レビュー完了と誤認すること。

**Out of scope（今回実施しないこと）**

- scikit-learn、TF-IDF、分類器、Fold生成、CV、BERT、MinHashLSH。

### Phase 3 — scikit-learn導入・共通Fold・Coreモデル基盤

**Purpose（目的）**

Python 3.14上でCore依存を固定し、group-awareな共通Fold artifactと最小TF-IDF線形Pipelineを構築する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Planned`
- Actual: `Completed`
- 完了: scikit-learn `1.9.0`を`pyproject.toml`の`[project.dependencies]`（Core）へ追加し、Python 3.14.4でresolve/lock/import/最小`TfidfVectorizer→LinearSVC`・`LogisticRegression` Pipeline fitを検証済み（commit `9c08871`）。
- 完了: `src/mail_classification/evaluation/full_dataset.py`でFullデータhash契約の動的Fail-fast検証（`verify_full_dataset_hash`/`load_verified_full_dataset`）を実装。契約値は`docs/reviews/full_review_decision.json`の`full_data_hash`を実行時参照し、コードへ literal 複製しない。実データ（800件、hash `53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc`）での一致読込と1byte改変時の`ValueError`raiseを実地検証済み。
- 完了: `src/mail_classification/evaluation/splits.py`で`template_group`監査（`audit_template_groups`）、splitter推奨（`recommend_splitter_name`）、共通5-fold生成（`build_common_folds`）、JSON書き出し（`write_fold_artifact`）を実装。実データ800件は24 groups全て単一labelに属し（spanning 0件）group構造が実在するため`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`を採用（`task10_architecture.md`指定パラメータと一致）。`outputs/folds/common_folds.json`（hash `72a62dbffd23c38358744fb2a024a35a14b76747e264fc0abf7ce32c7f7e54c8`、生成物のため`.gitignore`管理・Git非追跡）へ書き出し済み。
- 既知の限界（Phase 4へ引継ぎ）: labelごとの template group数（6）がn_splits（5）で割り切れないため、各labelにつき必ず1 foldが2 group分（66件）を受け取り、他4 foldsは1 group分（33/34件）となる。`StratifiedGroupKFold`はこの負担をlabelごとに異なるfoldへ分散させ、fold単位validation件数は134〜167件（理想160件に対し約±20%）。データ形状とn_splits設定の数学的必然であり実装不具合ではないが、macro-F1解釈時に留意する。
- 完了: `src/mail_classification/models/factory.py`に`build_core_pipeline(model_name, *, tfidf_params, model_params)`（`TfidfVectorizer`＋`LinearSVC`/`LogisticRegression`の未fit Pipeline factory）を実装。未知の`model_name`は`ValueError`。TF-IDFはPipeline内でのみfitされ、`.named_steps["tfidf"].transform()`を事前に呼ぶと`NotFittedError`になることをtestで確認。
- 完了: Coreアブレーション条件D0〜D2を承認・確定（詳細は本節末尾「Core条件（D0〜D2）承認記録」）。承認過程で、初回提案のD2がD1のbigram設定を引き継いだままで前処理変更と同時に発生する主要因交絡（project_rules.md §8違反）を検出し、D2のTF-IDFをD0基準のunigramへ戻す修正（案A）を経て確定した。`src/mail_classification/models/conditions.py`に`CORE_CONDITIONS`（D0/D1/D2の`preprocessing_config`＋`tfidf_params`）、`CORE_MODEL_PARAMS`（`C=1.0`固定）、`apply_condition_preprocessing`、`build_condition_pipeline`を実装し、3条件×2モデル＝6通り全てのsmoke fit/predictをtestで確認。
- 完了: Phase 3 dependency/Fold/model契約文書`docs/contracts/phase3_model_contract.md`を作成し、上記全項目を正本として集約した。
- 既存の`src/mail_classification/schemas/folds.py`はschema/検証契約のみ。

**Prerequisites（前提条件）**

- Phase 2完了Gateを満たした固定Full dataset。
- Phase 1 schema/前処理契約とPhase 2 group情報。

**Main tasks（主な作業）**

- `uv`でscikit-learnを追加し、Python 3.14でresolve/import/minimal Pipelineを検証する。
- Fullの`template_group`を監査し、`StratifiedGroupKFold`採用可否をデータに基づき決定する。
- 一度だけ共通5-fold assignmentを生成し、全条件・全モデル用artifactとして保存する。
- 完了: TF-IDFをPipeline内に置き、LinearSVC／Logistic Regression factoryと最小smoke fitを実装した。
- 完了: Coreアブレーション条件D0〜D2を一主要因ずつの比較となるよう承認・確定した（本節末尾参照）。以後、D0〜D2は正式仕様として扱う。
- 解消済み: Fold保存形式は`docs/schemas/fold_artifact_schema.md`が定義する単一UTF-8 JSON（`FoldArtifact`＝`metadata`＋`records`）を正本とし、`folds.json`として保存する。`project_rules.md`と`task10_architecture.md`に残っていた`folds.csv`表記（旧`RunManifest`設計前の記述）は本方針へ更新済み。CSVへの派生出力は現時点で不要と判断する。

**Main outputs（主な成果物）**

- Completed: updated `pyproject.toml`, `uv.lock`（scikit-learn追加）
- Completed: `src/mail_classification/evaluation/full_dataset.py`とtest（Fullデータhash契約のFail-fast検証）
- Completed: `src/mail_classification/evaluation/splits.py`とtest（`template_group`監査、splitter推奨、共通5-fold生成、JSON書き出し）
- Completed: model-independent common Fold artifact at `outputs/folds/common_folds.json`（`fold_artifact_hash`は各experiment run生成時にmanifestへ記録予定、Phase 4で対応）
- Completed: `src/mail_classification/models/factory.py`（`build_core_pipeline`）
- Completed: `src/mail_classification/models/conditions.py`（`CORE_CONDITIONS`、`CORE_MODEL_PARAMS`、`apply_condition_preprocessing`、`build_condition_pipeline`）
- Completed: `docs/contracts/phase3_model_contract.md`

**Validation（検証方法）**

- Python 3.14 resolve/import/minimal Pipeline。
- Fold sample coverage、train/validation overlap 0、同一group跨ぎ0、同一seed再現。
- TF-IDFがPipeline外でfitされないこと、全条件が同じartifactを読むこと。

**Core条件（D0〜D2）承認記録**

- 承認日時: 2026-07-31 16:13:05 +07
- 承認者: User (Yuji Sunagawa)（`AI-assisted manual content review`によるAI側の起草・監査を経て、契約`approval_authority: User`に基づき本人が承認）
- 経緯: 初回AI起草案のD2は、特徴量をD1のbigram設定のまま前処理のみ変えていたため、D0基準で見るとn-gram要因と前処理要因が同時に変化する交絡があった（project_rules.md §8「一度に変える主要因は原則１つ」違反）。ユーザーへ確認したところ、修正案A（D2の特徴量をD0基準のunigramへ戻す）が選択され、この形で正式承認された。
- 確定条件:
  - **D0（baseline）**: 前処理はnormalizationのみ（NFKC・句読点・空白・lowercase）、header/signature/quoted-reply/URL/emailは変更しない。特徴量はTF-IDF unigramのみ（`ngram_range=(1,1)`）。
  - **D1（n-gram拡張）**: 前処理はD0と同一。特徴量をunigram+bigram（`ngram_range=(1,2)`）へ拡張。
  - **D2（前処理強化）**: 特徴量はD0と同一（unigramのみ）。前処理はheader/signature/quoted-reply除去とURL/emailマスクを有効化。
  - モデル軸（`LinearSVC`／`LogisticRegression`、共に`C=1.0`）は各条件と直交し、3条件×2モデル＝6通り全てを比較する。
- 実装: `src/mail_classification/models/conditions.py`のとおり実装済み、6通り全てのsmoke fit/predictを`tests/test_conditions.py`で確認済み。

**Completion criteria（完了条件）**

- scikit-learn互換確認とlock固定が成功する。
- 共通Fold artifactが保存・schema検証される。
- 最小LinearSVC/LR Pipelineが学習Foldだけでfitして成功する。

**Transition gate（次Phaseへの移行条件）**

- scikit-learn互換確認、共通Fold保存、Fold検証、最小Pipeline成功。

**Main risks（想定リスク）**

- Python 3.14 wheel/API互換、group/class balance不足、TF-IDFの全データfit、Fold形式の正本不一致。

**Out of scope（今回実施しないこと）**

- 全Core実験完走、結果解釈、BERT/MinHash、最終report。

### Phase 4 — Coreアブレーション実験・多クラス評価

**Purpose（目的）**

共通5-fold上で前処理・feature/model条件を公平に比較し、多クラス性能と計算コストを保存する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Planned`
- Actual: `Completed`
- 完了: `src/mail_classification/evaluation/cv.py`（`run_core_cell`/`run_core_experiments`）、`metrics.py`（`build_metrics_long`/`build_confusion_matrix_rows`）、`aggregate.py`（`build_metrics_summary`）、`paired.py`（`build_paired_differences`）、`runner.py`（`load_fold_artifact`/`run_and_write_core_experiments`）を実装。pandasは導入せず、既存モジュール（`quality/statistics.py`等）と同じstdlib（`statistics`、`collections.Counter`、`csv`）のみで集計する設計とした。
- 完了: 実データ（Full 800件、`outputs/folds/common_folds.json`）で3条件×2モデル＝6セル×5 foldを実行し、`outputs/runs/phase4-core-seed42/`へ`metrics_long.csv`、`metrics_summary.csv`、`predictions_oof.csv`（4800行＝6セル×800件、各セルで800件1:1 coverage）、`confusion_matrix.csv`、`paired_differences.csv`、`manifest.json`（`fold_artifact_path`/`hash`、`data_hash`は共通Fold契約経由で記録、`model_name`は複数モデルを跨ぐため`null`）を生成した。
- 実測結果（macro-F1 cv_mean、解釈はPhase 5へ委ねる）: D0 linear_svc 0.616、D0 logistic_regression 0.593、D1 linear_svc 0.625、D1 logistic_regression 0.575、D2 linear_svc 0.596、D2 logistic_regression 0.610。fold間標準偏差は0.08〜0.13と大きく、Phase 3で記録した既知の限界（labelあたり6 template groups÷5 foldsによるfold sizeの不均衡、134〜167件）が一因と見られるが、原因分析はPhase 5の役割とし本Phaseでは断定しない。
- `outputs/runs/`は生成物のため`.gitignore`へ追加し、Git非追跡とした（`outputs/folds/`等と同様の運用）。

**Prerequisites（前提条件）**

- Phase 3の固定Full data、共通Fold artifact、最小Pipeline、確定Core条件。

**Main tasks（主な作業）**

- 完了: 原則1主要因ずつのCoreアブレーションを5-foldで実行した。
- 完了: macro-F1を主指標とし、Accuracy、macro/weighted、classwise P/R/F1、confusion matrixを計算した。
- 完了: Fold Long、CV mean/std、fit/predict時間、Fold vocabulary sizeを保存した。
- 完了: 全OOF predictionとFold単位ペア差を1:1 coverage検証付きで保存した。

**Main outputs（主な成果物）**

- Completed: `outputs/runs/phase4-core-seed42/metrics_long.csv`
- Completed: `outputs/runs/phase4-core-seed42/metrics_summary.csv`
- Completed: `outputs/runs/phase4-core-seed42/predictions_oof.csv`
- Completed: `outputs/runs/phase4-core-seed42/confusion_matrix.csv`、`paired_differences.csv`、`manifest.json`（timing/vocabularyは`metrics_long.csv`の`fit_seconds`/`predict_seconds`/`vocabulary_size`列に保存）。

**Validation（検証方法）**

- sample×condition×modelのOOF件数一致、Fold欠落・重複0。
- 同一Fold hash、metric schema、NaN、label order、timing非負を検査。
- Markdownへ値を手動転記せずartifactを直接検証。

**Completion criteria（完了条件）**

- 全Core条件・モデルが同一Foldで完走する。
- Fold Long、集約、OOF、ペア差、confusion、timing、vocabularyが欠落なく保存される。

**Transition gate（次Phaseへの移行条件）**

- 全Core条件完走、Fold結果保存、OOF件数一致、欠落・重複なし。

**Main risks（想定リスク）**

- 複数要因の交絡、都合のよい主指標変更、Accuracy偏重、class order誤り、結果世代混在。

**Out of scope（今回実施しないこと）**

- 説明専用全データfitの解釈、Extension、最終PDF。

### Phase 5 — 説明性・誤分類分析

**Purpose（目的）**

Coreの性能差をクラス別係数とOOF誤分類から説明し、合成template/内容リークの影響を再点検する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Planned`
- Actual: `Completed`
- 完了: `src/mail_classification/explain/`へ`linear.py`（`extract_fold_coefficients`：Fold再fit＋クラス別top positive/negative/absolute係数と語彙、`extract_descriptive_full_fit_coefficients`：全データfit専用の別関数・別出力、`audit_top_features_for_structural_artifacts`：header/URL/email語の再監査）、`errors.py`（`build_misclassification_rows`：OOF true≠pred行をdifficulty/template_group/構造flag/`multi_intent`・`secondary_intent`・`contains_negation`（いずれもPhase 2 generatorが実際に記録するmetadata）と結合し`primary_category`を付与）、`evidence.py`（`enrich_misclassifications_with_evidence`：Fold再fitでdecision scoreと寄与特徴を追加、true/predicted labelはOOFの実測値を再利用し再計算しない）、`runner.py`（`run_and_write_explainability`）を実装した。
- 実データ（Full 800件、Phase 4の`outputs/runs/phase4-core-seed42/predictions_oof.csv`）で6セル分の係数抽出・誤分類分析を実行し、`outputs/runs/phase5-explain-seed42/`へ`fold_coefficients.csv`、`descriptive_full_fit_coefficients.csv`、`structural_artifact_audit.csv`、`misclassifications.csv`（decision score・寄与特徴付き、1883件）、`error_category_summary.csv`、`manifest.json`を生成した。
- 実測所見（仮説として記録、断定しない）:
  - 構造artifact再監査: `subject`/`from`/`sent`/`cc`/`bcc`/`url`/`wrote`はD0〜D2いずれのtop featureにも出現しなかった。`email`のみ全条件（D0/D1/D2）のtop_absolute featureに出現したが、D0（header/URL/email非除去）でも同様に出現するため、`<EMAIL>`置換由来の構造artifactというより、合成本文中の自然な語彙（"email"という単語自体が意図語として使われている）である可能性が高いと仮説的に判断する。header/URL由来の明確なリークは確認されなかった。
  - error taxonomy集計（6セル合計）: `structural_content`（header/signature/quoted-reply存在）が最多だが、これは合成データ全体でも該当record比率が高いため（Phase 2実測: header/signature/quoted replyは半数前後の記録に存在）、誤分類での比率が母集団比率より高いかは未検証であり、本Phaseでは「頻度が高い」以上の因果主張はしない。次点は`multi_intent`（62〜81件/セル）、`ambiguous_difficulty`（31〜41件/セル）。
  - decision score・寄与特徴の実例確認: 一部の誤分類で、正解class寄りの語（例: "cancellation"、"refund"）が誤答classの寄与特徴（例: "want"、"my"）より高いTF-IDF係数を持つにもかかわらず誤分類となる例を確認した。寄与特徴に一般的な機能語（"the"、"is"、"an"、"you"）が頻出することも確認した。これは`build_core_pipeline`の`TfidfVectorizer`が`stop_words`を設定していないため（Phase 3で承認されたD0〜D2はこの設定を変更していない）であり、将来的なablation候補として記録するが、本Phaseでは変更しない。

**Prerequisites（前提条件）**

- Phase 4の固定Core run、OOF prediction、Fold fitted Pipelineと語彙。

**Main tasks（主な作業）**

- 完了: 各Fold・各クラスで正係数、負係数、絶対値上位と対応語彙を抽出した。
- 完了: OOF誤分類をtrue/pred、decision score、difficulty、template group、構造flag、寄与特徴で出力した。
- 完了: 誤分類を曖昧性（difficulty）、複数意図（`multi_intent`/`secondary_intent`）、否定表現（`contains_negation`）、構造要素（header/signature/quoted-reply）で分析した。template・前処理・class境界別の追加分析はPhase 6以降の要否判断に委ねる（未実施）。
- 完了: `extract_fold_coefficients`（評価用Fold再fit）と`extract_descriptive_full_fit_coefficients`（全データ`descriptive_full_fit`）を別関数・別CSVとして明確に分離した。

**Main outputs（主な成果物）**

- Completed: `outputs/runs/phase5-explain-seed42/fold_coefficients.csv`、`descriptive_full_fit_coefficients.csv`
- Completed: `outputs/runs/phase5-explain-seed42/misclassifications.csv`（decision score・寄与特徴付き）
- Completed: `outputs/runs/phase5-explain-seed42/error_category_summary.csv`、`structural_artifact_audit.csv`、`manifest.json`

**Validation（検証方法）**

- coefficient class indexとfeature nameが同じfitted Pipeline由来であること（実装上、同一fit呼び出し内で`classifier.coef_`と`tfidf.get_feature_names_out()`を同時取得）。
- 全誤分類がOOF rowへ1:1対応し、説明専用fitを性能根拠に使っていないこと（`misclassifications.csv`行数と実際のOOF true≠pred行数の一致をtestで確認、`descriptive_full_fit`は別ファイル）。
- header/signature/template語が上位特徴にないか再監査（`structural_artifact_audit.csv`、上記実測所見）。

**Completion criteria（完了条件）**

- 全クラスの係数と全OOF誤分類が追跡可能。→ 実データで確認済み。
- 主要error category、原因仮説、リーク留保が文書化される。→ 上記実測所見に記載。

**Transition gate（次Phaseへの移行条件）**

- Core評価・説明性・誤分類分析が完了し、Extensionを実施するか明示判断する。

**Main risks（想定リスク）**

- Fold語彙差の無視、全データfitとの混同、係数を因果効果と解釈、都合のよいsample選択。

**Out of scope（今回実施しないこと）**

- Extensionを自動開始すること、最終reportの手動数値記入。

### Phase 6 — Extension実験

**Purpose（目的）**

Coreで答えられない明確な問いだけを、Core成果物を変更せず追加検証する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Optional`
- Actual: `Optional`
- MinHashLSH、BERT、language detection等は未実装・未選択。

**Prerequisites（前提条件）**

- Phase 5完了。
- 実施理由、計算予算、比較条件、停止条件が事前承認される。

**Main tasks（主な作業）**

- Optional: MinHashLSHによるnear-duplicate感度分析。
- Optional: BERT系とCore TF-IDF線形モデルを同じdata/Fold/metricで比較。
- Coreとは別config、CLI、run ID、output directoryを使用する。

**Main outputs（主な成果物）**

- Planned only if approved: Extension config/code/tests/artifacts/manifest。
- Core成果物への上書きは行わない。

**Validation（検証方法）**

- 同一data/Fold/metric、依存version、resource、時間、失敗状態を保存。
- CoreとExtensionのpath/hashが混在していないことを検査。

**Completion criteria（完了条件）**

- 選択したExtensionの問いに必要なartifactが揃い、Coreとの公平な比較が可能。
- 未選択の場合は「実施しない」判断と理由を記録すればPhase 7へ進める。

**Transition gate（次Phaseへの移行条件）**

- 実施時: 選択Extension完了かつCore非上書き。
- 非実施時: Phase 5で非実施判断済み。

**Main risks（想定リスク）**

- scope creep、重い依存・download、異なるFold/前処理による不公平比較、Core結果の上書き。

**Out of scope（今回実施しないこと）**

- 承認のない追加モデル、LLM外部serviceへのデータ送信。

### Phase 7 — レポート自動生成・PDF・ファイナライズ

**Purpose（目的）**

固定runの機械可読結果からMarkdown、図表、PDF、検査結果を再現し、課題要件への対応を確定する。

**Status（現在の状態／Expected vs Actual）**

- Expected: `Planned`
- Actual: `Planned`
- `tools/pdf_renderer/`の移植・単体PDF smokeは実在するが、課題10最終report本文・図表・世代検査・最終PDFは未作成。

**Prerequisites（前提条件）**

- Phase 5完了。Phase 6を実施する場合はPhase 6も完了。
- 採用run IDと全config/data/Fold/result hashが固定済み。

**Main tasks（主な作業）**

- artifactから表・図・Markdownを自動生成し、数値の手動転記を避ける。
- 大学要件mapping、合成データ限界、リーク、誤分類、再現性を記載。
- Markdown→HTML→PDFを実行し、layout・content・generation hashを検査する。
- 通常buildを非破壊とし、auto-repairは明示opt-in、manual設定を保護する。

**Main outputs（主な成果物）**

- Planned: report Markdown、generated tables/figures
- Planned: final PDF、layout/content check JSON、selected-run generation manifest
- Existing reusable tool: `tools/pdf_renderer/`

**Validation（検証方法）**

- report値とsource artifactの一致、selected run/hashの世代一致。
- PDF text/figure/table/layout検査、通常build非破壊、manual設定保持。
- 大学課題要件表を要件原本と照合する。

**Completion criteria（完了条件）**

- report、図表、PDF、検査JSONが同じ固定runから再生成できる。
- report内の数値とsource artifact、run/config/data/Fold/result hashが一致する。
- 必須要件、限界、未実施Extension、環境制約を偽りなく記載する。
- 全Core testsと、実施したExtensionのtestsが成功する。
- `uv lock --check`と`git diff --check`が成功する。
- READMEの再現手順がclean環境で実行可能である。
- working treeと最終成果物の追跡状態を確認する。
- 実メール、顧客情報、社内機密が成果物へ含まれていない。
- 最終PDFがlayout・content検査基準を満たす。

**Transition gate（次Phaseへの移行条件）**

- 最終提出物と検査結果の承認。これがプロジェクト完了Gateとなる。

**Main risks（想定リスク）**

- artifactの手動転記、結果/report世代不一致、PDF heuristicの見逃し、auto-repairによるmanual指定破壊。

**Out of scope（今回実施しないこと）**

- report生成中の学習再実行、未承認Extension、本文内容を変えるlayout修復。

## 4. 依存関係図

Mermaid対応は現在のMarkdown→PDF基盤で実測確認できていないため、追加依存なしのtext diagramを正本とする。

```text
Phase 0 Audit / Rules                         [Completed]
          |
          v
Phase 1 Schemas / Preprocessing              [Completed]
          |
          v
Phase 2A Generator + Smoke/Pilot + Auto QA   [Completed]
          |
          v
Phase 2B Human Review                        [Approved]
          |
          v
Phase 2C Full Generation + Final Data QA     [Completed / Approved]
          |
          v
Phase 3 Dependencies + Common Folds + Models [Ready; not started]
          |
          v
Phase 4 Core Ablation / Multiclass CV        [Planned]
          |
          v
Phase 5 Explainability / Error Analysis      [Planned]
          |
          +-------------------------------+
          |                               |
          v                               v
Phase 6 Extension [Optional]       Skip Extension [Decision recorded]
          |                               |
          +---------------+---------------+
                          |
                          v
Phase 7 Report / PDF / Finalization          [Planned]
```

## 5. 成果物一覧

| Phase | Status | Main outputs | Completion gate |
| --- | --- | --- | --- |
| 0 | Completed | Existing: inventory, audit, reuse matrix, architecture, rules | 根拠付き監査と設計承認 |
| 1 | Completed | Existing: `pyproject.toml`, `uv.lock`, schemas, preprocessing, contracts, tests | Phase 1 tests・lock・diff成功、固定commit公開 |
| 2 | Completed | Existing: generator/quality code, config/templates, reviewed Smoke/Pilot/Full, summaries/reports/manifests and tracked approvals | Human review完了＋Full品質・hash固定 |
| 3 | Ready | Planned: sklearn lock、common Fold artifact、minimal LinearSVC/LR Pipelines | dependency/Fold/Pipeline検証成功 |
| 4 | Planned | Planned: Fold Long、summary、OOF、confusion、paired differences、timing/vocabulary | 全Core完走、OOF coverage完全 |
| 5 | Planned | Planned: class/Fold coefficients、misclassification artifacts、error taxonomy | Coreの説明性・誤分類分析確定 |
| 6 | Optional | Planned only if approved: MinHashLSH/BERT等の別run | 選択Extension完了または非実施判断 |
| 7 | Planned | Existing tool: `tools/pdf_renderer/`; Planned: report、figures、PDF、checks | 同一runから再生成・要件照合・提出承認 |

## 6. Phase移行Gate一覧

| Transition | Required conditions |
| --- | --- |
| Phase 2 → Phase 3 | Fullデータ生成、品質検査合格、人間レビュー完了、data hash・template group確定 |
| Phase 3 → Phase 4 | scikit-learn互換確認、共通Fold artifact保存、Fold検証成功、最小Pipeline成功 |
| Phase 4 → Phase 5 | 全Core条件完走、Fold結果保存、OOF件数一致、欠落・重複なし |
| Phase 5 → Phase 6 (実施可否判断) | Core評価・説明性・誤分類分析完了。Extension実施可否を明示判断 |
| Phase 5 → Phase 7 | Extension非実施の場合。Core結果・説明性・誤分類分析が確定 |
| Phase 6 → Phase 7 | 選択Extension完了、Core成果物を上書きしていない |

## 7. リスク管理

| Risk | Detection | Mitigation |
| --- | --- | --- |
| 合成templateの暗記 | group-awareとrandom splitの差、係数上位、template別OOF | template groupをFold間で分離し、template語を人手監査 |
| 同一template groupのFold間混入 | Fold artifactのgroup×role検証 | group-aware split、共通artifactを全条件で再利用 |
| 完全一致・正規化後重複 | raw/body exact・Phase 1 canonicalization監査 | Full前後に0件をGate化し、原因templateを修正 |
| header/signature/metadata内容リーク | class別頻度・one-to-one・係数上位 | 共有pool、除去ablation、内容リークartifactを別保存 |
| TF-IDFのCV外fit | test、code review、Fold vocabulary | `TfidfVectorizer`をPipeline内限定、validationはtransformのみ |
| Accuracy偏重 | metric schema、report要件検査 | macro-F1主指標、classwise P/R/F1とconfusionを必須化 |
| 前処理要因の交絡 | condition diff、config review | 原則1主要因、複合条件はpipeline比較と明記 |
| 不均衡classの見逃し | class ratio、classwise recall/F1 | data quality Gate、macro/classwise metrics |
| Foldごとの語彙差 | Fold vocabulary/feature name hash | 係数と語彙を同一Fold fitted Pipelineから抽出 |
| Python 3.14とpackage互換 | uv resolve/sync/import/minimal fit | Phase 3開始時に検証しlock、失敗を記録してversion判断 |
| 実験結果とreport世代不一致 | run/config/data/Fold/result hash照合 | selected-run manifestからのみ生成 |
| Core前のExtension scope creep | Phase Gate、path/config review | Phase 5判断までExtension依存・CLIを追加しない |
| PDF auto-repairがmanual指定を破壊 | diff、manual/generated分離test | opt-in、generatedのみatomic更新、rollback |
| 合成結果の過度な一般化 | report wording・limitations review | synthetic control上の結果と明記しproduction性能を主張しない |

## 8. 大学課題要件との対応

大学の課題10要件原本は今回確認対象の実ファイルに含まれていないため、下表は現プロジェクトとの予定対応であり、最終的な必須/任意判断はすべて要件原本で要確認とする。

| Requirement | Phase | Evidence / Output | Verification status |
| --- | --- | --- | --- |
| Text preprocessing | 1, 4 | Existing: 3層interface、contract、tests; Planned: ablation results | 基盤実装済み／要件原本で要確認 |
| TF-IDF | 3, 4 | Planned: Pipeline component、Fold vocabulary | 未実装／要件原本で要確認 |
| Linear classifier | 3, 4 | Planned: LinearSVC、Logistic Regression | 未実装／要件原本で要確認 |
| Accuracy | 4 | Planned: Fold Long/summary | 未実装／要件原本で要確認 |
| Precision | 4 | Planned: macro/classwise results | 未実装／要件原本で要確認 |
| Recall | 4 | Planned: macro/classwise results | 未実装／要件原本で要確認 |
| F1 | 4 | Planned: macro-F1、weighted/classwise F1 | 未実装／要件原本で要確認 |
| Error analysis | 5 | Planned: OOF errors、taxonomy、contributions | 未実装／要件原本で要確認 |
| BERT comparison | 6 | Optional/Planned only if approved | 実施要否を要件原本で要確認 |
| Python code | 1–5 | Existing: Phase 1/2 package、tests; Planned: model/evaluation modules | 一部実装済み／要件原本で要確認 |
| Result files | 2, 4, 5 | Existing: data-quality JSON/CSV/manifest; Planned: metrics/OOF/explanation | 一部実装済み／要件原本で要確認 |
| PDF report | 7 | Existing: renderer tool; Planned: final report/PDF/check JSON | 最終成果物未作成／要件原本で要確認 |

## 9. 実行上の原則

1. 各Phase開始前に前Phaseのcompletion criteriaとtransition gateを実測確認する。
2. 実装前に関連する正本文書とreuse matrixを読む。
3. 変更後はtests、`uv lock --check`、`git diff --check`、scope差分を確認する。
4. 既存成果物を無断で上書き・削除せず、run IDとhashで世代を分離する。
5. 実験結果を手動編集・Markdownへ手動転記しない。
6. 問題発見時は生成物でなく原因のcode/config/templateを修正して再生成する。
7. 未確認事項を推測で完了扱いしない。
8. CoreとExtensionをconfig、CLI、依存、出力先で混在させない。
9. 実メール、顧客情報、社内機密を使用せず、外部serviceへ送信しない。
10. 実行日時、Git hash/dirty、config/data/template/Fold/result hashをmanifestへ保存する。

## 10. 現在の未確認事項と直近アクション

### 未確認事項

- 大学課題10の要件原本。特にBERT比較の必須/任意、提出形式、評価指標の指定。
- Mermaidは現PDF基盤で未検証のため、本書では使用していない。
- Phase 4実測結果（macro-F1約0.58〜0.63、fold間標準偏差0.08〜0.13）の原因分析はPhase 5（説明性・誤分類分析）で行う。本書では断定していない。

### 直近アクション

1. 完了: Full承認証拠とPhase 2完了記録をcommit/pushし、local/remote同期とworking tree cleanを確認した。
2. 完了: scikit-learn `1.9.0`のPython 3.14.4互換性をlock・import・最小Pipelineで検証した（commit `9c08871`）。
3. 完了: Fold artifact正本形式をJSON（`folds.json`）に確定し、project rules/architectureの`folds.csv`表記を更新した。
4. 完了: 共通5-fold assignment生成とFold Artifact書き出し（`outputs/folds/common_folds.json`）を実装した。
5. 完了: Core条件D0〜D2をUser (Yuji Sunagawa)承認のもと確定し、TF-IDF/model factoryを実装した（commit `1a44c81`）。
6. 完了: Phase 4 Core実験（6セル×5-fold）を実データで実行し、Fold Long/集約/OOF/confusion/paired differences/manifestを`outputs/runs/phase4-core-seed42/`へ保存した。
7. 次: Phase 5（説明性・誤分類分析）着手前に、local 6 commits（`9c08871`以降）のpush、および本ドキュメント整理・Phase 4実装のcommit/push要否をユーザーへ確認する。
