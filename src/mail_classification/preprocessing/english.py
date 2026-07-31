"""Dependency-light English cleaning, normalization, and segmentation."""

from __future__ import annotations

from html import unescape
import re
import unicodedata

from pydantic import BaseModel, ConfigDict

from .base import Cleaner, Normalizer, Preprocessor, Segmenter
from .stats import PreprocessingResult, ProcessingStats

URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+")
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
HTML_PATTERN = re.compile(r"(?s)<[^>]+>")
HEADER_PATTERN = re.compile(
    r"(?im)^(?:from|to|cc|bcc|subject|date|sent|reply-to):[^\n]*(?:\n|$)"
)
SIGNATURE_PATTERN = re.compile(r"(?ms)^\s*--\s*$.*\Z")
QUOTED_LINE_PATTERN = re.compile(r"(?m)^\s*>.*(?:\n|$)")
REPLY_BLOCK_PATTERN = re.compile(r"(?ims)^on .+? wrote:\s*$.*\Z")
TOKEN_PATTERN = re.compile(
    r"<(?:URL|EMAIL)>|[^\W_]+(?:'[^\W_]+)?", re.UNICODE | re.IGNORECASE
)

PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "…": "...",
    }
)

DEFAULT_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "please",
        "the",
        "to",
        "with",
    }
)
PROTECTED_NEGATIONS = frozenset({"not", "no", "never", "without", "cannot"})
SUPPORTED_VERSION = "1.0.0"


class UnsupportedPreprocessorVersion(ValueError):
    """Raised when configuration requests behavior this code cannot reproduce."""


class CleaningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    remove_headers: bool = True
    remove_signatures: bool = True
    remove_quoted_reply: bool = True
    remove_html: bool = True
    replace_urls: bool = True
    replace_emails: bool = True


class NormalizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    unicode_nfkc: bool = True
    normalize_punctuation: bool = True
    normalize_whitespace: bool = True
    lowercase: bool = True


class SegmentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled: bool = True
    remove_stopwords: bool = False
    lemmatize: bool = False


class EnglishPreprocessingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str = "english_minimal"
    version: str = SUPPORTED_VERSION
    cleaning: CleaningConfig = CleaningConfig()
    normalization: NormalizationConfig = NormalizationConfig()
    segmentation: SegmentationConfig = SegmentationConfig()


class EnglishCleaner(Cleaner):
    def __init__(self, config: CleaningConfig) -> None:
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
            result = URL_PATTERN.sub(" <URL> ", result)
        if self.config.replace_emails:
            result = EMAIL_PATTERN.sub(" <EMAIL> ", result)
        return result


class EnglishNormalizer(Normalizer):
    def __init__(self, config: NormalizationConfig) -> None:
        self.config = config

    def normalize(self, text: str) -> str:
        if not self.config.enabled:
            return text
        result = text
        if self.config.unicode_nfkc:
            result = unicodedata.normalize("NFKC", result)
        if self.config.normalize_punctuation:
            result = result.translate(PUNCTUATION_TRANSLATION)
        if self.config.normalize_whitespace:
            result = re.sub(r"\s+", " ", result).strip()
        if self.config.lowercase:
            result = result.lower()
        return result


class EnglishSegmenter(Segmenter):
    def __init__(self, config: SegmentationConfig) -> None:
        self.config = config
        if config.lemmatize:
            raise NotImplementedError(
                "lemmatization has no Phase 1 implementation; disable it explicitly"
            )

    def segment(self, text: str) -> list[str]:
        if not self.config.enabled:
            return []
        tokens = TOKEN_PATTERN.findall(text)
        if self.config.remove_stopwords:
            tokens = [
                token
                for token in tokens
                if token.casefold() not in DEFAULT_STOP_WORDS
                or token.casefold() in PROTECTED_NEGATIONS
            ]
        return tokens


class EnglishPreprocessor(Preprocessor):
    """Stateless composition of the three independently toggleable layers."""

    def __init__(self, config: EnglishPreprocessingConfig | None = None) -> None:
        self.config = config or EnglishPreprocessingConfig()
        if self.config.version != SUPPORTED_VERSION:
            raise UnsupportedPreprocessorVersion(
                f"unsupported preprocessor version: {self.config.version}"
            )
        self.cleaner = EnglishCleaner(self.config.cleaning)
        self.normalizer = EnglishNormalizer(self.config.normalization)
        self.segmenter = EnglishSegmenter(self.config.segmentation)

    def transform(self, raw_text: str) -> PreprocessingResult:
        if not isinstance(raw_text, str):
            raise TypeError("raw_text must be a string")
        cleaned = self.cleaner.clean(raw_text)
        clean_text = self.normalizer.normalize(cleaned)
        input_tokens = TOKEN_PATTERN.findall(raw_text)
        tokens = self.segmenter.segment(clean_text)
        stats = ProcessingStats(
            input_char_count=len(raw_text),
            output_char_count=len(clean_text),
            input_token_count=len(input_tokens),
            output_token_count=len(tokens),
            chars_removed=max(0, len(raw_text) - len(clean_text)),
            tokens_removed=max(0, len(input_tokens) - len(tokens)),
            urls_replaced=len(URL_PATTERN.findall(raw_text))
            if self.config.cleaning.enabled and self.config.cleaning.replace_urls
            else 0,
            emails_replaced=len(EMAIL_PATTERN.findall(raw_text))
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
