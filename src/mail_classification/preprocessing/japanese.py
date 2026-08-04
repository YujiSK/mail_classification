"""SudachiPy/neologdn-backed Japanese cleaning, normalization, and segmentation.

Mirrors the structure of ``english.py`` (three independently toggleable
layers implementing the ``base.py`` interfaces) but does not modify or import
executable logic from it, so the Phase 1-8 English track stays byte-for-byte
unchanged. Only the language-neutral regex constants
(``URL_PATTERN``/``EMAIL_PATTERN``/``HTML_PATTERN``/``PUNCTUATION_TRANSLATION``)
and the generic ``UnsupportedPreprocessorVersion`` exception are reused by
import, per ``docs/audits/task10_ja_reuse_matrix.md``.
"""

from __future__ import annotations

from functools import lru_cache
from html import unescape
import re
import unicodedata

import neologdn
from pydantic import BaseModel, ConfigDict, field_validator
from sudachipy import dictionary as sudachi_dictionary
from sudachipy import tokenizer as sudachi_tokenizer

from .base import Cleaner, Normalizer, Preprocessor, Segmenter
from .english import (
    HTML_PATTERN,
    PUNCTUATION_TRANSLATION,
    UnsupportedPreprocessorVersion,
)
from .stats import PreprocessingResult, ProcessingStats

__all__ = [
    "JapaneseCleaner",
    "JapaneseCleaningConfig",
    "JapaneseNormalizationConfig",
    "JapaneseNormalizer",
    "JapanesePreprocessingConfig",
    "JapanesePreprocessor",
    "JapaneseSegmentationConfig",
    "JapaneseSegmenter",
    "UnsupportedPreprocessorVersion",
]

HEADER_PATTERN = re.compile(
    r"(?im)^(?:差出人|宛先|件名|送信日時|Cc|Bcc)[:：][^\n]*(?:\n|$)"
)
SIGNATURE_PATTERN = re.compile(r"(?ms)^\s*--\s*$.*\Z")
QUOTED_LINE_PATTERN = re.compile(r"(?m)^\s*[>＞].*(?:\n|$)")
# The English REPLY_BLOCK_PATTERN anchors `^` directly to a required literal
# ("on "), so its `.+?` never crosses into an earlier line. A literal Japanese
# port that instead opened with `^.*` (DOTALL) would let that leading `.*`
# backtrack across newlines and swallow every earlier line too, so this
# pattern instead confines the pre-trigger scan with `[^\n]*` (no `\n` match
# regardless of DOTALL) and only lets `.*\Z` span lines after the trigger.
REPLY_BLOCK_PATTERN = re.compile(
    r"(?ims)^[^\n]*次のように(?:書きました|送信しました)[:：].*\Z"
)
# Deliberately no `\b` word-boundary: Python's Unicode-aware `\b` treats CJK
# characters as \w, so a URL/email glued directly to Japanese text with no
# separating space/punctuation (the common case in real Japanese mail) would
# silently fail to match if `\b` were required immediately before the
# literal trigger. The literal trigger itself is distinctive enough that
# dropping `\b` does not introduce meaningful false positives.
#
# The URL body is restricted to RFC 3986 URI characters (all ASCII) rather
# than English's "not whitespace" (`[^\s<>]+`): Japanese sentences rarely put
# a space after a URL before the next word, so a whitespace-delimited class
# would keep consuming through Japanese punctuation and text -- and through
# an immediately following email address -- as one runaway match.
JA_URL_PATTERN = re.compile(
    r"(?i)(?:https?://|www\.)[A-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
)
JA_EMAIL_PATTERN = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")

SPLIT_MODES = {
    "A": sudachi_tokenizer.Tokenizer.SplitMode.A,
    "B": sudachi_tokenizer.Tokenizer.SplitMode.B,
    "C": sudachi_tokenizer.Tokenizer.SplitMode.C,
}
TOKEN_FORMS = ("surface", "normalized_form", "dictionary_form")
# "ない"/"ず"/"ぬ" cover the auxiliary-verb (助動詞) negation family; "無い"
# covers the same negation used adjectivally (形容詞), e.g. "〜ではない".
# Sudachi's normalized_form() distinguishes these by part-of-speech context.
NEGATION_NORMALIZED_FORMS = frozenset({"ない", "無い", "ず", "ぬ"})
SUPPORTED_VERSION = "1.0.0"


@lru_cache(maxsize=None)
def _load_sudachi_tokenizer(dict_type: str):
    """Create (once per process, per ``dict_type``) and cache a Sudachi Tokenizer.

    Dictionary loading costs roughly a second; the project rule against
    initializing analyzer resources inside a document loop
    (``project_rules.md`` §5) makes process-wide caching mandatory rather
    than an optimization.
    """
    return sudachi_dictionary.Dictionary(dict=dict_type).create()


class JapaneseCleaningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    remove_headers: bool = True
    remove_signatures: bool = True
    remove_quoted_reply: bool = True
    remove_html: bool = True
    replace_urls: bool = True
    replace_emails: bool = True


class JapaneseNormalizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    unicode_nfkc: bool = True
    apply_neologdn: bool = True
    normalize_punctuation: bool = True
    normalize_whitespace: bool = True
    lowercase: bool = True


class JapaneseSegmentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    split_mode: str = "C"
    token_form: str = "normalized_form"
    remove_pos: tuple[str, ...] = ()
    protect_negation: bool = True

    @field_validator("split_mode")
    @classmethod
    def validate_split_mode(cls, value: str) -> str:
        if value not in SPLIT_MODES:
            raise ValueError(f"split_mode must be one of {sorted(SPLIT_MODES)}")
        return value

    @field_validator("token_form")
    @classmethod
    def validate_token_form(cls, value: str) -> str:
        if value not in TOKEN_FORMS:
            raise ValueError(f"token_form must be one of {TOKEN_FORMS}")
        return value


class JapanesePreprocessingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str = "japanese_minimal"
    version: str = SUPPORTED_VERSION
    dictionary: str = "core"
    cleaning: JapaneseCleaningConfig = JapaneseCleaningConfig()
    normalization: JapaneseNormalizationConfig = JapaneseNormalizationConfig()
    segmentation: JapaneseSegmentationConfig = JapaneseSegmentationConfig()

    @field_validator("dictionary")
    @classmethod
    def validate_dictionary(cls, value: str) -> str:
        if value not in {"core", "full"}:
            raise ValueError("dictionary must be 'core' or 'full'")
        return value


class JapaneseCleaner(Cleaner):
    def __init__(self, config: JapaneseCleaningConfig) -> None:
        self.config = config

    def clean(self, text: str) -> str:
        if not self.config.enabled:
            return text
        result = text
        if self.config.remove_quoted_reply:
            result = REPLY_BLOCK_PATTERN.sub("", result)
            result = QUOTED_LINE_PATTERN.sub("", result)
        if self.config.remove_signatures:
            result = SIGNATURE_PATTERN.sub("", result)
        if self.config.remove_headers:
            result = HEADER_PATTERN.sub("", result)
        if self.config.remove_html:
            result = unescape(HTML_PATTERN.sub(" ", result))
        if self.config.replace_urls:
            result = JA_URL_PATTERN.sub(" <URL> ", result)
        if self.config.replace_emails:
            result = JA_EMAIL_PATTERN.sub(" <EMAIL> ", result)
        return result


class JapaneseNormalizer(Normalizer):
    def __init__(self, config: JapaneseNormalizationConfig) -> None:
        self.config = config

    def normalize(self, text: str) -> str:
        if not self.config.enabled:
            return text
        result = text
        if self.config.unicode_nfkc:
            result = unicodedata.normalize("NFKC", result)
        if self.config.apply_neologdn:
            result = neologdn.normalize(result)
        if self.config.normalize_punctuation:
            result = result.translate(PUNCTUATION_TRANSLATION)
        if self.config.normalize_whitespace:
            result = re.sub(r"\s+", " ", result).strip()
        if self.config.lowercase:
            result = result.lower()
        return result


class JapaneseSegmenter(Segmenter):
    def __init__(self, config: JapaneseSegmentationConfig, dictionary: str) -> None:
        self.config = config
        self._tokenizer = _load_sudachi_tokenizer(dictionary)
        self._mode = SPLIT_MODES[config.split_mode]

    def segment(self, text: str) -> list[str]:
        if not self.config.enabled or not text:
            return []
        tokens: list[str] = []
        for morpheme in self._tokenizer.tokenize(text, self._mode):
            pos = morpheme.part_of_speech()[0]
            normalized = morpheme.normalized_form()
            is_negation = normalized in NEGATION_NORMALIZED_FORMS
            if pos in self.config.remove_pos and not (
                self.config.protect_negation and is_negation
            ):
                continue
            if self.config.token_form == "surface":
                tokens.append(morpheme.surface())
            elif self.config.token_form == "dictionary_form":
                tokens.append(morpheme.dictionary_form())
            else:
                tokens.append(normalized)
        return [token for token in tokens if token.strip()]


class JapanesePreprocessor(Preprocessor):
    """Stateless-per-call composition; the Sudachi Tokenizer is process-cached.

    One instance should be reused across an entire corpus/Fold rather than
    constructed per document: construction is cheap (the expensive Sudachi
    Dictionary load is memoized by ``_load_sudachi_tokenizer``), but re-running
    ``dictionary.Dictionary(...).create()`` inside a tight loop would still
    defeat that cache's purpose if a caller bypassed this class.
    """

    def __init__(self, config: JapanesePreprocessingConfig | None = None) -> None:
        self.config = config or JapanesePreprocessingConfig()
        if self.config.version != SUPPORTED_VERSION:
            raise UnsupportedPreprocessorVersion(
                f"unsupported preprocessor version: {self.config.version}"
            )
        self.cleaner = JapaneseCleaner(self.config.cleaning)
        self.normalizer = JapaneseNormalizer(self.config.normalization)
        self.segmenter = JapaneseSegmenter(
            self.config.segmentation, self.config.dictionary
        )

    def _raw_token_count(self, raw_text: str) -> int:
        tokenizer = _load_sudachi_tokenizer(self.config.dictionary)
        mode = SPLIT_MODES[self.config.segmentation.split_mode]
        return len(tokenizer.tokenize(raw_text, mode)) if raw_text else 0

    def transform(self, raw_text: str) -> PreprocessingResult:
        if not isinstance(raw_text, str):
            raise TypeError("raw_text must be a string")
        cleaned = self.cleaner.clean(raw_text)
        clean_text = self.normalizer.normalize(cleaned)
        input_token_count = self._raw_token_count(raw_text)
        tokens = self.segmenter.segment(clean_text)
        stats = ProcessingStats(
            input_char_count=len(raw_text),
            output_char_count=len(clean_text),
            input_token_count=input_token_count,
            output_token_count=len(tokens),
            chars_removed=max(0, len(raw_text) - len(clean_text)),
            tokens_removed=max(0, input_token_count - len(tokens)),
            urls_replaced=len(JA_URL_PATTERN.findall(raw_text))
            if self.config.cleaning.enabled and self.config.cleaning.replace_urls
            else 0,
            emails_replaced=len(JA_EMAIL_PATTERN.findall(raw_text))
            if self.config.cleaning.enabled and self.config.cleaning.replace_emails
            else 0,
        )
        return PreprocessingResult(
            raw_text=raw_text,
            clean_text=clean_text,
            tokens=tuple(tokens),
            stats=stats,
            preprocessor_name=self.config.name,
            preprocessor_version=self.config.version,
        )
