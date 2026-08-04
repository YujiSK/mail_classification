"""Japanese Core ablation conditions J0-JC.

Independent module mirroring the English D0-D2 pattern (``conditions.py``):
does not import from or modify ``conditions.py``, so the English Phase 3-4
hash-fixed results are unaffected (``docs/audits/task10_ja_reuse_matrix.md``).

- J0 (baseline): light cleaning (headers/signature/quoted-reply/URL/email
  untouched), NFKC + neologdn + punctuation/whitespace + lowercase
  normalization, Sudachi Mode C segmentation with ``normalized_form()``
  tokens, negation-protected (no POS removal). TF-IDF word unigram.
- J1: J0 preprocessing; TF-IDF extended to word unigram+bigram.
- J2: J0's TF-IDF (word unigram); cleaning enhanced with header/signature/
  quoted-reply removal and URL/email masking.
- JC: J0-equivalent light cleaning/normalization; Sudachi segmentation is
  bypassed entirely (character n-grams do not need word tokens); TF-IDF
  character 2-3gram directly on normalized text.

Each condition changes exactly one factor relative to J0
(``project_rules.md`` §8), mirroring the English D0-D2 approval discipline.
No condition removes particles/auxiliary verbs (``remove_pos=()``) and all
protect negation (``protect_negation=True``): POS-removal ablation is left
to a future Extension, not folded into Core, per explicit instruction to
never blanket-remove 助詞/助動詞 in Core.
"""

from __future__ import annotations

from dataclasses import dataclass

from mail_classification.preprocessing import (
    JapaneseCleaningConfig,
    JapanesePreprocessingConfig,
    JapanesePreprocessor,
    JapaneseSegmentationConfig,
)

from .factory import build_core_pipeline

_LIGHT_CLEANING = JapaneseCleaningConfig(
    remove_headers=False,
    remove_signatures=False,
    remove_quoted_reply=False,
    replace_urls=False,
    replace_emails=False,
)
_ENHANCED_CLEANING = JapaneseCleaningConfig()  # defaults: all removal/masking on

_WORD_SEGMENTATION = JapaneseSegmentationConfig(
    enabled=True,
    split_mode="C",
    token_form="normalized_form",
    remove_pos=(),
    protect_negation=True,
)
_NO_SEGMENTATION = JapaneseSegmentationConfig(enabled=False)


@dataclass(frozen=True)
class JaCoreCondition:
    name: str
    description: str
    preprocessing_config: JapanesePreprocessingConfig
    tfidf_params: dict[str, object]
    # True: space-join Sudachi tokens for a whitespace-tokenizer TfidfVectorizer.
    # False: pass clean_text through untouched for a character-analyzer TfidfVectorizer.
    segment_for_tfidf: bool


JA_CORE_CONDITIONS: dict[str, JaCoreCondition] = {
    "J0": JaCoreCondition(
        name="J0",
        description=(
            "Baseline: NFKC/neologdn/punctuation/whitespace/lowercase "
            "normalization; header/signature/quoted-reply/URL/email "
            "untouched; Sudachi Mode C normalized_form tokens; word unigram."
        ),
        preprocessing_config=JapanesePreprocessingConfig(
            cleaning=_LIGHT_CLEANING, segmentation=_WORD_SEGMENTATION
        ),
        tfidf_params={
            "tokenizer": str.split,
            "token_pattern": None,
            "lowercase": False,
            "ngram_range": (1, 1),
        },
        segment_for_tfidf=True,
    ),
    "J1": JaCoreCondition(
        name="J1",
        description="J0 preprocessing; TF-IDF extended to word unigram+bigram.",
        preprocessing_config=JapanesePreprocessingConfig(
            cleaning=_LIGHT_CLEANING, segmentation=_WORD_SEGMENTATION
        ),
        tfidf_params={
            "tokenizer": str.split,
            "token_pattern": None,
            "lowercase": False,
            "ngram_range": (1, 2),
        },
        segment_for_tfidf=True,
    ),
    "J2": JaCoreCondition(
        name="J2",
        description=(
            "J0 TF-IDF (word unigram); cleaning enhanced with header/"
            "signature/quoted-reply removal and URL/email masking."
        ),
        preprocessing_config=JapanesePreprocessingConfig(
            cleaning=_ENHANCED_CLEANING, segmentation=_WORD_SEGMENTATION
        ),
        tfidf_params={
            "tokenizer": str.split,
            "token_pattern": None,
            "lowercase": False,
            "ngram_range": (1, 1),
        },
        segment_for_tfidf=True,
    ),
    "JC": JaCoreCondition(
        name="JC",
        description=(
            "J0-equivalent light cleaning/normalization; segmentation "
            "bypassed; TF-IDF character 2-3gram (char_wb) directly on "
            "normalized text."
        ),
        preprocessing_config=JapanesePreprocessingConfig(
            cleaning=_LIGHT_CLEANING, segmentation=_NO_SEGMENTATION
        ),
        tfidf_params={"analyzer": "char_wb", "ngram_range": (2, 3), "lowercase": False},
        segment_for_tfidf=False,
    ),
}

JA_CORE_MODEL_PARAMS: dict[str, dict[str, object]] = {
    "linear_svc": {"C": 1.0},
    "logistic_regression": {"C": 1.0},
}


def _condition(condition_name: str) -> JaCoreCondition:
    try:
        return JA_CORE_CONDITIONS[condition_name]
    except KeyError:
        raise ValueError(
            f"unknown Core condition {condition_name!r}; "
            f"expected one of {sorted(JA_CORE_CONDITIONS)}"
        ) from None


def apply_condition_preprocessing_ja(
    condition_name: str, raw_texts: list[str]
) -> list[str]:
    """Deterministically clean/normalize(/segment) text for a condition (no fitting)."""
    condition = _condition(condition_name)
    preprocessor = JapanesePreprocessor(condition.preprocessing_config)
    if condition.segment_for_tfidf:
        return [
            " ".join(preprocessor.transform(text).tokens) for text in raw_texts
        ]
    return [preprocessor.transform(text).clean_text for text in raw_texts]


def build_condition_pipeline_ja(condition_name: str, model_name: str):
    """Build the TF-IDF + classifier Pipeline for one (condition, model) cell."""
    condition = _condition(condition_name)
    return build_core_pipeline(
        model_name,
        tfidf_params=condition.tfidf_params,
        model_params=JA_CORE_MODEL_PARAMS.get(model_name),
    )
