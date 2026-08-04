# Phase JA-3 model contract (Japanese track)

Companion to `docs/contracts/phase3_model_contract.md` for the Japanese
track. Independent module set; does not modify the English contract's
implementation (`models/conditions.py`, `evaluation/cv.py`,
`evaluation/runner.py`) or its Phase 4 output.

## Dependencies

`sudachipy`/`sudachidict-core`/`neologdn` (added in the `japanese`
dependency group during Phase JA-1) are the only new runtime dependencies
this phase relies on; no new third-party package was added for modeling
itself (`scikit-learn` is shared with the English track, already Core).

## Common Fold

`outputs/folds/common_folds_ja.json` (gitignored, reproducible):

- Splitter: `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`,
  chosen by `evaluation.audit_template_groups`/`recommend_splitter_name`
  (reused unmodified from the English track — both are language-neutral)
  after confirming, on the real 800-record Full dataset, that all 24
  `template_group` values belong to exactly one label each (`has_group_structure:
  true`, `groups_spanning_multiple_labels: {}`), the same structural
  precondition the English track found for its own 24 groups.
- `fold_artifact_hash`: `41a10ce176bcf1f0c545a4b41a144e2e449c11dc0f3d7756460af680076c3ffb`
  (recorded at generation time; `FoldMetadata.created_at` makes this hash
  change on every regeneration even though the fold *assignment* is
  seed-deterministic — same caveat the English track documents).
- Coverage: all 800 records appear exactly once as validation across the
  5 folds; `FoldArtifact`'s own cross-record validators reject any
  same-fold train/validation split of a `template_group`.
- Known imbalance (inherited from the same 6-groups-per-label ÷ 5-folds
  arithmetic the English track already documents): one fold per label
  necessarily receives 2 template groups (66-67 records) while the other
  four receive 1 group each (33-34 records), so per-fold validation counts
  range roughly 134-167 rather than an even 160. This is a property of the
  data's group cardinality, not a splitter defect.

## Core conditions J0-JC (approved)

Approved 2026-08-04 by User (Yuji Sunagawa), specified verbatim in the
autonomous-execution instruction that authorized Phase JA-3 onward (not an
AI-drafted proposal subject to a separate review round, unlike the English
D0-D2 sequence). Each condition changes exactly one factor relative to J0
(`project_rules.md` §8):

- **J0 (baseline)**: cleaning leaves header/signature/quoted-reply/URL/email
  untouched; normalization applies NFKC, neologdn, punctuation/whitespace,
  and lowercase; segmentation uses SudachiPy `SplitMode.C` with
  `normalized_form()` tokens, no POS removal, negation protected. TF-IDF
  word unigram (`tokenizer=str.split` over the pre-segmented, space-joined
  Sudachi token string; `lowercase=False` since normalization already
  lowercased ASCII substrings).
- **J1**: identical preprocessing to J0; TF-IDF extended to word
  unigram+bigram (`ngram_range=(1, 2)`).
- **J2**: identical TF-IDF to J0 (word unigram); cleaning enhanced to
  remove headers/signatures/quoted-reply and mask URLs/emails (mirrors
  English D2).
- **JC (character n-gram baseline)**: J0-equivalent light cleaning and
  normalization, but Sudachi segmentation is bypassed entirely — the
  `TfidfVectorizer` reads `clean_text` (post-normalization, pre-tokenization)
  directly with `analyzer="char_wb"`, `ngram_range=(2, 3)`. `char_wb` was
  compared against plain `char` on the real 800-record Full dataset before
  approval: `char_wb` vocabulary size 5,968 vs `char` 6,201, mean nonzero
  features/document 308.3 vs 315.5 — no pathological behavior (vocabulary
  explosion, near-empty rows) in either; `char_wb`'s clause-boundary marker
  features (e.g. `' お'`) come from real whitespace already present after
  `normalize_whitespace` collapses newlines between body segments (greeting/
  context/request/detail/closing), not from added tokenization spaces, so
  it behaves as intended rather than degenerating the way naive
  space-delimited `char_wb` would on unsegmented running Japanese text.
  `char_wb` was kept as specified.

No condition removes 助詞 (particles) or 助動詞 (auxiliary verbs)
(`remove_pos=()` in every condition) and every condition keeps
`protect_negation=True`; POS-removal ablation is deliberately left for a
future Extension rather than folded into Core, matching the explicit
instruction that blanket particle/auxiliary removal risks destroying
negation and intent information central to inquiry classification.

Model axis (`LinearSVC`/`LogisticRegression`, both `C=1.0`, matching the
English track's Core parameters verbatim — no language-specific
hyperparameter change) is orthogonal to and crosses every condition: 4
conditions × 2 models = 8 Core cells.

## Known behavior: token-form transliteration of ASCII loanwords

Sudachi's `normalized_form()` can transliterate embedded ASCII words into
katakana (e.g. "example" → "エグザンプル", "email" → "Eメール", both observed
empirically — see `tests/test_conditions_ja.py` and
`docs/contracts/preprocessing_contract_ja.md`). J0/J1/J2 do not lose this
content (it survives as a different token), but any explainability/leakage
inspection of top features must expect katakana-transliterated ASCII terms,
not the original Latin spelling. JC (character n-grams over untokenized
text) is unaffected since it never invokes Sudachi.

## Implementation

- `src/mail_classification/models/conditions_ja.py`: `JA_CORE_CONDITIONS`,
  `JA_CORE_MODEL_PARAMS`, `apply_condition_preprocessing_ja`,
  `build_condition_pipeline_ja`.
- `src/mail_classification/evaluation/ja_cv.py`,
  `src/mail_classification/evaluation/ja_runner.py`: forked from
  `cv.py`/`runner.py` only because those import the English condition
  functions at module level; `metrics.py`/`aggregate.py`/`paired.py` are
  reused unmodified (duck-typed over `FoldFitResult`-shaped rows, no
  English-specific assumption).
- Tests: `tests/test_conditions_ja.py`, `tests/test_cv_ja.py`,
  `tests/test_runner_ja.py` (31 cases, including a real-Full-data smoke
  test of all 8 cells).
