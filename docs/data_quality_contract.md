# Data quality contract

## Scope

Phase 2 quality checks inspect data content without fitting a model. They are
separate from future statistical Pipeline leakage controls. Implementations
are in `src/mail_classification/quality/`; thresholds are defined only in
`configs/phase2.yml`.

## Duplicate definitions

| Check | Definition |
|---|---|
| exact raw | byte-equivalent Python string value of `raw_text` |
| exact body | exact `body_text` |
| normalized raw | Phase 1 `EnglishPreprocessor` output after header, signature, quoted reply, HTML, Unicode, case, and whitespace handling |
| normalized body | the same canonicalization applied to `body_text` |

Each duplicate row records check type, source field, canonical SHA-256, record
count, IDs, labels, and template groups. Header/signature-only differences are
therefore detected as normalized duplicates. Phase 2 does not implement
MinHash, edit-distance clustering, embeddings, or semantic near duplicates.

## Content-leakage definitions

The audit checks:

- formal label names in raw/body/metadata;
- template IDs or group IDs in visible text;
- one template group carrying multiple labels;
- too few groups or concentration within one group;
- header/signature/sender-domain/subject values repeated in one class only;
- structure flags and difficulty values mapping to one class only;
- shared urgency component occurrence ratios differing by class;
- class-exclusive tokens and bigrams above the configured frequency;
- excessive class mean-length ratio.

Label/template literals and mixed-label groups are errors. Structural
one-to-one mappings, concentration, and extreme length differences are
warnings. Exclusive lexical features are informational review candidates
because legitimate intent vocabulary can be class-specific.

## Metrics

The summary stores total and class counts/ratios, difficulty counts,
class-by-difficulty counts, group/variation counts, exact and normalized
duplicate groups, per-class character/token/line mean, median, minimum,
maximum, and population standard deviation, structure counts/ratios, negation
count, multi-intent count, finding counts, warnings, hashes, and generator
version.

## Configured thresholds

- six template groups per class;
- class-ratio deviation no greater than 0.02 from equal balance;
- maximum ratio between class mean raw lengths of 2.0;
- no exact or normalized duplicate group;
- largest group share no greater than 0.25;
- exclusive token/bigram candidate frequency of at least four;
- maximum cross-class shared-component ratio deviation of 0.05;
- ten base review samples per class;
- Pilot must contain easy, medium, and hard examples.

Smoke relaxes template-count, concentration, difficulty, and small-sample
structural warnings. It still fails on duplicate groups, class imbalance, label
literal leakage, template literal leakage, or mixed-label groups.

## Hash contract

All hashes use exact-byte lowercase SHA-256 through the Phase 1 helper. Data
hash excludes run time because runtime provenance is stored in a separate
manifest. Two Pilot runs with identical inputs must have identical JSONL hash.

## Pilot automatic pass

Automatic Pilot quality passes only when:

- required counts, classes, difficulties, and groups are present;
- configured class balance is met;
- exact and normalized duplicate thresholds are met;
- the leakage audit has no error or warning;
- hashes and required artifacts are produced.

Informational lexical candidates do not automatically fail Pilot, but must be
included in human review.

Shared urgency components are recorded by index in generation metadata and
must have approximately equal occurrence ratios in every class. A larger
cross-class deviation is a warning and prevents automatic Pilot approval.

## Full-generation gate

`automatic_quality_pass: true` is necessary but not sufficient. Pilot summary
remains `human_review_status: pending` and
`full_generation_allowed: false`. A human must complete the review CSV,
evaluate informational candidates, and request any template/rule correction.
Only a later reviewed configuration change may enable Full generation. The
machine-readable approval source of truth is the tracked
`docs/reviews/pilot_review_decision.json`; ignored output-side evidence alone
cannot satisfy the Phase Gate.
