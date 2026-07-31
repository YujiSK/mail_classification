# Phase 3 dependency, Fold, and model contract

## Scope

Phase 3 fixes the Core scikit-learn dependency, the one shared Fold
assignment every condition and model reuses, and the TF-IDF + linear-model
Pipeline factory, then closes the ablation-condition decision that Phase 2
left open. It does not implement experiment execution, OOF collection,
aggregation, or reporting; those are Phase 4. Implementations are in
`src/mail_classification/evaluation/` and `src/mail_classification/models/`.

## Dependency contract

- `scikit-learn>=1.7,<2` is a Core runtime dependency in `pyproject.toml`
  (`[project.dependencies]`), not `dev`/`reporting`, following the Phase 1
  Core/reporting boundary.
- Verified on Python 3.14.4: `uv lock --check` passes; resolved versions are
  scikit-learn `1.9.0`, numpy `2.5.1`, scipy `1.18.0`, joblib `1.5.3`,
  threadpoolctl `3.6.0`, narwhals `2.24.0`.
- `joblib`'s backend imports the stdlib `socket` module for local
  multiprocessing plumbing, not network I/O. `tests/test_import_safety.py`
  checks for `requests`/`urllib.request` only, not `socket`.

## Full dataset input contract

Implementation: `src/mail_classification/evaluation/full_dataset.py`.

- `approved_full_data_hash(decision_path)` reads `full_data_hash` from the
  tracked `docs/reviews/full_review_decision.json`. That file, not a literal
  in code, is the single source of truth, so a future legitimately
  regenerated and re-approved Full dataset is picked up without a code
  change.
- `verify_full_dataset_hash(data_path, decision_path)` computes the exact-byte
  SHA-256 of `data_path` (via the Phase 1 `sha256_file` helper) and raises
  `ValueError` on any mismatch, including a single-bit difference, before any
  Fold generation or training can run.
- `load_verified_full_dataset(data_path, decision_path)` returns
  `list[RawMailRecord]` only after the hash check passes.
- Verified against the real `data/raw/full_emails.jsonl`: 800 records, hash
  `53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc`, matching
  `docs/reviews/full_review_decision.json` and the Full generation manifest.

## Fold artifact contract

Implementation: `src/mail_classification/evaluation/splits.py`. Schema:
`docs/schemas/fold_artifact_schema.md` (`FoldArtifact`, `metadata` + `records`,
one UTF-8 JSON object — see "Fold storage format" below).

- `audit_template_groups(records)` reports unique group count, per-group
  size, groups per label, and any group spanning more than one label.
- `recommend_splitter_name(audit)` returns `StratifiedGroupKFold` only when
  group structure is real (more than one sample per group on average) and
  clean (no group spans more than one label); otherwise `StratifiedKFold`.
- `build_common_folds(records, data_hash, *, n_splits=5, random_seed=42)`
  builds one long-format `FoldArtifact`: every sample gets exactly one row
  per fold (`n_samples * n_splits` rows total), with `split_role` `train` in
  `n_splits - 1` folds and `validation` in exactly one. `FoldArtifact`'s own
  cross-record validation independently confirms no `(fold_id, sample_id)`
  duplicate and no `(fold_id, template_group)` splits between roles.
- `write_fold_artifact(path, artifact)` writes the artifact as one JSON file
  and returns its SHA-256.
- On the real Full dataset: 24 template groups, each confined to a single
  label (0 spanning), so `StratifiedGroupKFold(n_splits=5, shuffle=True,
  random_state=42)` is selected — the same parameters already named in
  `docs/architecture/task10_architecture.md`.
- Reproducibility: identical `records`/`data_hash`/`random_seed` produce an
  identical `(sample_id, fold_id) -> split_role` assignment across runs
  (`metadata.created_at` is the only field that legitimately varies).

### Fold storage format

`folds.json` (single shared file), not `folds.csv`. Resolved 2026-07-31: the
schema doc had already specified one JSON object since Phase 1, and
`RunManifest` carries a single `fold_artifact_path`/`fold_artifact_hash` pair,
which a two-file CSV+metadata split would not fit. Stale `folds.csv`
references in `project_rules.md` and `task10_architecture.md` were updated to
match.

### Canonical shared path

`outputs/folds/common_folds.json` — one file shared by every condition and
model, not duplicated under `outputs/runs/<run_id>/`. Each experiment run's
manifest is expected to record this shared path and its hash via the
existing `RunManifest.fold_artifact_path`/`fold_artifact_hash` fields
(wiring deferred to Phase 4, when runs first exist). The file is
regenerable from the tracked Full dataset and code, so it is listed in
`.gitignore` (`outputs/folds/`) rather than committed, matching the existing
`outputs/data_quality/`/`outputs/manifests/` convention.

### Known limitation carried into Phase 4

Each label has 6 template groups; 6 does not divide evenly by `n_splits=5`.
Per label, exactly one fold necessarily receives a double-sized group share
(66 records) while the other four receive one group each (33/34 records).
`StratifiedGroupKFold` spreads this imbalance across different folds for
different labels rather than concentrating it in one fold, but per-fold
validation set sizes still range 134-167 (an even split would be 160). This
is a consequence of the approved Full dataset's group count interacting with
the chosen fold count, not an implementation defect. Phase 4's macro-F1
aggregation and any written limitations section should account for the
resulting per-fold sample-size variation.

## Model factory contract

Implementation: `src/mail_classification/models/factory.py`.

- `build_core_pipeline(model_name, *, tfidf_params=None, model_params=None)`
  returns an unfit `sklearn.pipeline.Pipeline` with steps `("tfidf",
  TfidfVectorizer(**tfidf_params))` and `("clf", <classifier>(**model_params))`.
- `CORE_CLASSIFIERS = {"linear_svc": LinearSVC, "logistic_regression":
  LogisticRegression}`. An unknown `model_name` raises `ValueError`.
- Binding rule: TF-IDF must be fit only inside this Pipeline's own `.fit`,
  called on one Fold's train rows only, never on the full dataset ahead of a
  split. Bundling the vectorizer and classifier in one `Pipeline` is what
  makes a caller's `pipeline.fit(train)` / `pipeline.predict(validation)`
  respect that rule as long as Fold boundaries are respected; the factory
  itself does not enforce Fold usage, since no Fold-consuming caller exists
  yet (Phase 4).

## Core ablation conditions (D0-D2)

Implementation: `src/mail_classification/models/conditions.py`.

Approved 2026-07-31 16:13:05 +07 by User (Yuji Sunagawa), per the
`approval_authority: User` contract set at the start of Phase 3 and the
Phase 2 Human Review Gate principle of not conflating AI-assisted drafting
with human sign-off. An earlier draft of D2 held TF-IDF at D1's bigram
range while also changing cleaning, confounding two factors against the D0
baseline (`project_rules.md` §8: change one factor at a time). It was
corrected before approval so D2 changes only cleaning.

| Condition | Preprocessing (`cleaning`) | Preprocessing (`normalization`) | TF-IDF `ngram_range` |
|---|---|---|---|
| D0 (baseline) | `remove_headers/signatures/quoted_reply/replace_urls/replace_emails` all `False` | defaults (NFKC, punctuation, whitespace, lowercase all `True`) | `(1, 1)` |
| D1 | identical to D0 | identical to D0 | `(1, 2)` |
| D2 | `remove_headers/signatures/quoted_reply/replace_urls/replace_emails` all `True` (`CleaningConfig()` defaults) | identical to D0 | `(1, 1)` (identical to D0) |

`remove_html` is `True` in every condition; it is basic hygiene, not one of
the three approved ablation factors, so it is held constant rather than
varied.

Model choice is an orthogonal axis crossing every condition:
`CORE_MODEL_PARAMS = {"linear_svc": {"C": 1.0}, "logistic_regression": {"C":
1.0}}`. Core therefore compares 3 conditions × 2 models = 6 cells on the same
Fold artifact.

- `apply_condition_preprocessing(condition_name, raw_texts)` deterministically
  cleans/normalizes text for one condition (no fitting; safe to precompute
  once for all records before any Fold split).
- `build_condition_pipeline(condition_name, model_name)` returns the
  `build_core_pipeline` result for that cell. Unknown condition or model name
  raises `ValueError`.

## Validation

- `tests/test_evaluation.py` (Full-dataset hash contract, 9 cases),
  `tests/test_splits.py` (Fold audit/build/write, 14 cases, including a real
  Full-dataset end-to-end case), `tests/test_models.py` (factory smoke fits,
  9 cases, including a real Fold-artifact train/validation case),
  `tests/test_conditions.py` (D0-D2 factor isolation and 6-cell smoke fits,
  15 cases).
- Full suite: `173 passed`; `uv lock --check` and `git diff --check` clean at
  time of writing.

## Future extension (Phase 4)

- Wire `RunManifest.fold_artifact_path`/`fold_artifact_hash` to
  `outputs/folds/common_folds.json` when the first experiment run is
  implemented.
- Implement the Core aggregate/OOF/paired-difference artifacts described in
  `docs/architecture/task10_architecture.md` on top of the 6 (condition,
  model) Pipelines defined here.
- Decide, before Core execution, how the Phase 3 Fold-size imbalance (see
  "Known limitation" above) is reported alongside macro-F1 results.
