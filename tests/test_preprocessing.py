from pathlib import Path

import pytest
import yaml

from mail_classification.preprocessing import (
    EnglishPreprocessingConfig,
    EnglishPreprocessor,
    NormalizationConfig,
    SegmentationConfig,
    UnsupportedPreprocessorVersion,
)

CASES = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "preprocessing_cases.yml").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_preprocessing_cases(case: dict[str, object]) -> None:
    config = EnglishPreprocessingConfig(
        segmentation=SegmentationConfig(
            remove_stopwords=bool(case.get("remove_stopwords", False))
        )
    )
    result = EnglishPreprocessor(config).transform(str(case["input"]))
    assert result.raw_text == case["input"]
    if "expected_text" in case:
        assert result.clean_text == case["expected_text"]
    for expected in case.get("expected_contains", []):
        assert expected in result.clean_text
    if "expected_tokens" in case:
        assert list(result.tokens) == case["expected_tokens"]


def test_fixture_has_at_least_30_concrete_cases() -> None:
    assert len(CASES) >= 30
    assert len({case["id"] for case in CASES}) == len(CASES)


def test_transform_is_deterministic_and_raw_text_is_unchanged() -> None:
    raw = "From: X\nＡ URL: https://example.com"
    preprocessor = EnglishPreprocessor()
    first = preprocessor.transform(raw)
    second = preprocessor.transform(raw)
    assert first == second
    assert first.raw_text == raw


def test_each_layer_can_be_disabled() -> None:
    config = EnglishPreprocessingConfig(
        cleaning={"enabled": False},
        normalization=NormalizationConfig(enabled=False),
        segmentation=SegmentationConfig(enabled=False),
    )
    result = EnglishPreprocessor(config).transform("<b>RAW</b>")
    assert result.clean_text == "<b>RAW</b>"
    assert result.tokens == ()


def test_stats_are_nonnegative_and_count_replacements() -> None:
    result = EnglishPreprocessor().transform(
        "Email A@example.com or visit https://example.com"
    )
    assert result.stats.emails_replaced == 1
    assert result.stats.urls_replaced == 1
    assert result.stats.input_char_count > 0
    assert result.stats.output_token_count == len(result.tokens)


def test_lemmatization_request_fails_explicitly() -> None:
    with pytest.raises(NotImplementedError, match="no Phase 1 implementation"):
        EnglishPreprocessor(
            EnglishPreprocessingConfig(
                segmentation=SegmentationConfig(lemmatize=True)
            )
        )


def test_unsupported_version_fails_explicitly() -> None:
    with pytest.raises(UnsupportedPreprocessorVersion):
        EnglishPreprocessor(EnglishPreprocessingConfig(version="2.0.0"))


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        EnglishPreprocessor().transform(None)  # type: ignore[arg-type]
