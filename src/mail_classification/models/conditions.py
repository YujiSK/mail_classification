"""Approved Core ablation conditions D0-D2.

Approved 2026-07-31 by User (Yuji Sunagawa) as the formal Phase 3 spec,
after fixing a factor confound in an earlier D2 draft (its TF-IDF range had
inherited D1's bigram change instead of holding at D0's unigram baseline).
Each condition changes exactly one factor relative to D0, per
project_rules.md §8 ("一度に変える主要因は原則１つ"):

- D0 (baseline): normalization only; TF-IDF unigram.
- D1: D0's cleaning, TF-IDF extended to unigram+bigram.
- D2: D0's TF-IDF (unigram), cleaning enhanced with header/signature/
  quoted-reply removal and URL/email masking.

Model choice (LinearSVC / LogisticRegression) is a separate, orthogonal
axis that crosses every condition; it is not part of this ablation set.
"""

from __future__ import annotations

from dataclasses import dataclass

from mail_classification.preprocessing import (
    CleaningConfig,
    EnglishPreprocessingConfig,
    EnglishPreprocessor,
)

from .factory import build_core_pipeline

_MINIMAL_CLEANING = CleaningConfig(
    remove_headers=False,
    remove_signatures=False,
    remove_quoted_reply=False,
    replace_urls=False,
    replace_emails=False,
)
_ENHANCED_CLEANING = CleaningConfig()  # defaults: header/signature/quoted-reply/URL/email all on


@dataclass(frozen=True)
class CoreCondition:
    name: str
    description: str
    preprocessing_config: EnglishPreprocessingConfig
    tfidf_params: dict[str, object]


CORE_CONDITIONS: dict[str, CoreCondition] = {
    "D0": CoreCondition(
        name="D0",
        description=(
            "Baseline: normalization only (NFKC/punctuation/whitespace/"
            "lowercase); header/signature/quoted-reply/URL/email untouched; "
            "TF-IDF unigram."
        ),
        preprocessing_config=EnglishPreprocessingConfig(cleaning=_MINIMAL_CLEANING),
        tfidf_params={"ngram_range": (1, 1)},
    ),
    "D1": CoreCondition(
        name="D1",
        description="D0 preprocessing; TF-IDF extended to unigram+bigram.",
        preprocessing_config=EnglishPreprocessingConfig(cleaning=_MINIMAL_CLEANING),
        tfidf_params={"ngram_range": (1, 2)},
    ),
    "D2": CoreCondition(
        name="D2",
        description=(
            "D0 TF-IDF (unigram only); cleaning enhanced with header/"
            "signature/quoted-reply removal and URL/email masking."
        ),
        preprocessing_config=EnglishPreprocessingConfig(cleaning=_ENHANCED_CLEANING),
        tfidf_params={"ngram_range": (1, 1)},
    ),
}

CORE_MODEL_PARAMS: dict[str, dict[str, object]] = {
    "linear_svc": {"C": 1.0},
    "logistic_regression": {"C": 1.0},
}


def _condition(condition_name: str) -> CoreCondition:
    try:
        return CORE_CONDITIONS[condition_name]
    except KeyError:
        raise ValueError(
            f"unknown Core condition {condition_name!r}; "
            f"expected one of {sorted(CORE_CONDITIONS)}"
        ) from None


def apply_condition_preprocessing(
    condition_name: str, raw_texts: list[str]
) -> list[str]:
    """Deterministically clean/normalize text for a condition (no fitting)."""
    condition = _condition(condition_name)
    preprocessor = EnglishPreprocessor(condition.preprocessing_config)
    return [preprocessor.transform(text).clean_text for text in raw_texts]


def build_condition_pipeline(condition_name: str, model_name: str):
    """Build the TF-IDF + classifier Pipeline for one (condition, model) cell."""
    condition = _condition(condition_name)
    return build_core_pipeline(
        model_name,
        tfidf_params=condition.tfidf_params,
        model_params=CORE_MODEL_PARAMS.get(model_name),
    )
