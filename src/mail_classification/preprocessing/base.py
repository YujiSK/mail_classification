"""Interfaces shared by notebook, CLI, tests, and future inference."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .stats import PreprocessingResult


class Cleaner(ABC):
    @abstractmethod
    def clean(self, text: str) -> str:
        """Remove or replace message structure without normalization."""


class Normalizer(ABC):
    @abstractmethod
    def normalize(self, text: str) -> str:
        """Apply deterministic character-level normalization."""


class Segmenter(ABC):
    @abstractmethod
    def segment(self, text: str) -> list[str]:
        """Return tokens without fitting on a corpus."""


class Preprocessor(ABC):
    @abstractmethod
    def transform(self, raw_text: str) -> PreprocessingResult:
        """Transform one string while preserving it verbatim in the result."""
