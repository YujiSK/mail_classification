# Preprocessing contract

## Scope

Phase 1 provides a deterministic, dependency-light English preprocessing
contract, not a claim that stronger preprocessing improves classification.
Cleaning, normalization, and segmentation are separate and independently
toggleable. Notebook, future CLI, tests, training, and inference must import
this same module.

Implementation: `src/mail_classification/preprocessing/`.

## Interfaces and flow

1. `Cleaner.clean(text)` removes message structure and replaces URL/email
   content.
2. `Normalizer.normalize(text)` applies optional NFKC, punctuation,
   whitespace, and lowercase normalization.
3. `Segmenter.segment(text)` performs stateless tokenization and optional
   stop-word removal.
4. `Preprocessor.transform(raw_text)` composes the stages and returns
   `PreprocessingResult`.

The result contains the exact `raw_text`, derived `clean_text`, immutable
`tokens`, `ProcessingStats`, and preprocessor name/version. Statistics include
input/output character and token counts, conservative removal counts, and
URL/email replacement counts. Counts describe the configured transformation;
they are not training metrics.

| Result field | Type | Required |
|---|---|---:|
| `raw_text` | string | yes |
| `clean_text` | string | yes |
| `tokens` | immutable sequence of strings | yes |
| `stats` | `ProcessingStats` | yes |
| `preprocessor_name` | string | yes |
| `preprocessor_version` | string | yes |

## Current behavior

- Headers (`From`, `To`, `Subject`, etc.), `--` signatures, quoted `>` lines,
  reply blocks, and HTML tags can be removed.
- URLs and email addresses can become `<URL>` and `<EMAIL>`.
- NFKC covers full-width Latin letters and digits.
- Smart punctuation and repeated whitespace can be normalized.
- Tokenization supports Unicode letters, numbers, contractions, and the two
  placeholders.
- Stop-word removal defaults off. When enabled, `not`, `no`, `never`,
  `without`, and `cannot` remain protected.
- Empty and whitespace-only input is accepted and produces empty text/tokens.
- A non-string is rejected.

`raw_text` is never modified. A disabled layer passes text through; disabling
segmentation returns no tokens. Module import performs no download, model
initialization, network setup, or file generation.

## Configuration and unsupported features

`configs/phase1.yml` is the minimal approved configuration. Unknown keys are
rejected by the Pydantic configuration models. Version `1.0.0` is the only
supported behavior. Requesting another version raises
`UnsupportedPreprocessorVersion`.

Lemmatization is a declared future switch but has no dependency or
implementation in Phase 1. Setting it to `true` raises `NotImplementedError`;
it is never silently ignored. Analyzer objects are created once per
`EnglishPreprocessor`, not inside each token loop.

## Validation and examples

`tests/fixtures/preprocessing_cases.yml` contains at least 30 concrete,
data-driven cases covering headers, signatures, quotes, HTML, URLs, email,
NFKC, whitespace, punctuation, empty input, emoji, mixed language,
contractions, stop words, and protected negation. Unit tests also verify
determinism, raw-text preservation, stage switches, statistics, unsupported
features, and import safety.

Example:

```python
from mail_classification.preprocessing import EnglishPreprocessor

result = EnglishPreprocessor().transform("Subject: Help\nI cannot log in.")
assert result.raw_text.startswith("Subject:")
assert "cannot" in result.tokens
```

## Future extension

Lemmatization, language detection, Japanese analyzers, learned tokenizers, and
model-specific preprocessing require explicit dependency, version, latency,
and ablation decisions. Classical-model settings must not be applied
automatically to BERT-family models. Any semantic change increments the
preprocessor version and adds fixtures before use.
