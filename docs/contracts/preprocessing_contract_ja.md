# Preprocessing contract (Japanese track)

## Scope

Companion to `docs/contracts/preprocessing_contract.md` for the Japanese
("Task10-JA") track. Does not modify or supersede the English contract; both
tracks are independently versioned and independently importable
implementations of the same `Cleaner`/`Normalizer`/`Segmenter`/`Preprocessor`
interfaces (`src/mail_classification/preprocessing/base.py`).

Implementation: `src/mail_classification/preprocessing/japanese.py`.

## Interfaces and flow

Same three-layer composition as English:

1. `JapaneseCleaner.clean(text)` removes header/signature/quoted-reply
   structure and replaces URL/email spans.
2. `JapaneseNormalizer.normalize(text)` applies optional NFKC, neologdn,
   punctuation, whitespace, and lowercase normalization, in that order.
3. `JapaneseSegmenter.segment(text)` tokenizes with SudachiPy and applies
   optional part-of-speech removal with negation protection.
4. `JapanesePreprocessor.transform(raw_text)` composes the stages and
   returns the same `PreprocessingResult`/`ProcessingStats` types the
   English track uses (language-neutral, `src/mail_classification/
   preprocessing/stats.py`, unchanged).

## Current behavior

- Headers use Japanese labels (`差出人`, `宛先`, `件名`, `送信日時`, `Cc`,
  `Bcc`) rather than English's `From`/`To`/`Subject`/etc.
- `--` signature delimiter and reply-block detection
  (`...次のように書きました:` / `...次のように送信しました:`) mirror the
  synthetic generator's own component pools (`assets/templates/
  email_templates_ja.yml`); this is a controlled-corpus assumption, not a
  claim of covering arbitrary real Japanese mail client quoting conventions.
- Quoted lines are recognized with either `>` or the full-width `＞`.
- URL/email masking deliberately does **not** use a `\b` word-boundary
  assertion the way the English patterns do: Python's Unicode-aware `\b`
  treats CJK characters as `\w`, so a URL/email glued directly to Japanese
  text with no separating space (the common case in real Japanese
  sentences, since Japanese does not use inter-word spaces) would silently
  fail to match if `\b` were required. The URL body is further restricted to
  RFC 3986 URI characters (all ASCII) rather than "not whitespace", because
  a whitespace-delimited class would keep consuming through Japanese
  punctuation/text and through an immediately following email address as one
  runaway match — this was caught empirically while validating the fixture
  cases below (see `url_masking_no_space_before_japanese` and
  `url_query_string_and_email_do_not_merge`).
- NFKC covers full-width Latin letters/digits and half-width katakana
  (`ｶﾀﾅ` → `カタカナ`). NFKC can also collapse circled/formatted characters
  (e.g. `①` → `1`), which loses information; no fixture currently exercises
  that case because the synthetic templates do not use such characters, but
  this is a known limitation to test before trusting NFKC on out-of-corpus
  text.
- `neologdn.normalize()` runs after NFKC and collapses repeated long-vowel
  marks (`すごーーく` → `すごーく`) and similar orthographic noise. It is an
  independently toggleable step (`apply_neologdn`), not bundled into NFKC.
- Tokenization uses `sudachipy` with a configurable split mode
  (`split_mode`: `A`/`B`/`C`, default `C`) and dictionary (`dictionary`:
  `core`/`full`, default `core`). The Sudachi `Tokenizer` object is process-
  cached by `(dictionary,)` via `functools.lru_cache` in
  `_load_sudachi_tokenizer`, never rebuilt per document or per
  `JapanesePreprocessor` instance, per `project_rules.md` §5's ban on
  initializing analyzer resources inside a document loop.
- `token_form` selects which Sudachi morpheme attribute becomes the emitted
  token: `surface` (as-written), `normalized_form` (default; canonicalizes
  orthographic variants — `出来ない`/`できない` both become
  `[出来る, ない]`), or `dictionary_form` (citation form). This is an
  ablation knob (`docs/audits/task10_ja_reuse_matrix.md`'s J0 uses
  `normalized_form`), not a fixed choice.
- `remove_pos` takes a tuple of Sudachi major part-of-speech categories
  (e.g. `("助詞",)` for particles only, `("助詞", "補助記号")` for
  particles + auxiliary symbols) to drop from segmentation output. Default
  is `()` (no removal), matching the project rule that stopword/POS removal
  is never assumed beneficial and must be ablated (`project_rules.md` §5).
- `protect_negation` (default `True`) exempts any morpheme whose
  `normalized_form()` is in `{ない, 無い, ず, ぬ}` from `remove_pos`
  filtering, regardless of its part-of-speech category. `ない`/`ず`/`ぬ`
  cover the auxiliary-verb (助動詞) negation family; `無い` covers the same
  negation used adjectivally (e.g. `〜ではない`), which Sudachi tags as
  形容詞 rather than 助動詞. This is the Japanese analogue of English's
  `PROTECTED_NEGATIONS`, needed because inquiry-mail intent frequently
  hinges on negation (`ログインできない` vs `ログインできる`) and blanket
  助動詞 removal would silently destroy it — the fixture case
  `auxiliary_removal_without_negation_protection_drops_negation`
  demonstrates the failure mode this setting exists to prevent.
- Empty and whitespace-only input is accepted and produces empty
  text/tokens. A non-string is rejected with `TypeError`.
- `raw_text` is never modified. A disabled layer passes text through;
  disabling segmentation returns no tokens. Module import performs no
  download, dictionary load, network access, or file generation (the
  Sudachi dictionary loads lazily on first `_load_sudachi_tokenizer` call).

## Known limitation: placeholder tokens are not stable literals

Because `<URL>`/`<EMAIL>` placeholders are inserted by the cleaner and then
re-tokenized by Sudachi like any other text, the emitted tokens for a masked
URL/email are not always the literal strings `<url>`/`<email>`. With the
default `token_form="normalized_form"`, Sudachi's dictionary maps the ASCII
word `email` to the loanword `Eメール`, so a masked email becomes the tokens
`<`, `Eメール`, `>` rather than a single stable placeholder token. This is
real, deterministic SudachiPy dictionary behavior, not a bug in this module,
but it means any leakage/explainability audit that looks for structural
placeholder tokens (mirroring English Phase 5's `structural_artifact_audit`)
must account for `token_form`-dependent placeholder splitting rather than
assuming a fixed `<url>`/`<email>` token — tracked as a TODO for Phase JA-5.

## Validation and examples

`tests/fixtures/preprocessing_cases_ja.yml` contains 39 concrete,
data-driven cases (project minimum is 30) covering headers, signatures,
quoted lines/reply blocks (including the regression case that a naive
Japanese port of the English reply-block regex would incorrectly delete
preceding lines — see the comment above `REPLY_BLOCK_PATTERN` in
`japanese.py`), HTML, URL/email masking (including the no-space-before-
Japanese-text and URL-swallows-email regressions), NFKC, neologdn,
whitespace, punctuation, empty input, emoji, mixed language, orthographic-
variant (表記ゆれ) equivalence, negation (auxiliary, adjectival, polite
`〜ません`), katakana loanwords, full/half-width alphanumeric, and the
`remove_pos`/`protect_negation`/`token_form` ablation knobs. `tests/
test_preprocessing_ja.py` also verifies determinism, raw-text preservation,
per-layer disabling, statistics, unsupported-version handling, rejected
non-string input, and that the Sudachi tokenizer is process-cached rather
than reloaded per instance.

Example:

```python
from mail_classification.preprocessing import JapanesePreprocessor

result = JapanesePreprocessor().transform("件名: ログインについて\nログインできません。")
assert result.raw_text.startswith("件名:")
assert "ない" not in result.tokens  # "できません" -> normalized_form "ず", not "ない"
assert "ず" in result.tokens
```

## Future extension

Sudachi Mode A/B/C and core/full dictionary selection are Phase JA-1
defaults (`C`, `core`), not final choices; `docs/audits/
task10_ja_reuse_matrix.md` records these as unresolved pending a Phase
JA-6-equivalent ablation. A character n-gram condition (JC in the reuse
matrix) bypasses this module's segmentation entirely by using
`TfidfVectorizer(analyzer="char", ngram_range=(2, 3))` directly on
`clean_text`, so it does not require any change here. As with the English
contract: any semantic change increments `SUPPORTED_VERSION` and adds
fixtures before use, and classical-model preprocessing settings must not be
applied automatically to a Japanese BERT-family model in a later phase.
