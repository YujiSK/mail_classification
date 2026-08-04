from pathlib import Path

import pytest
import yaml

from mail_classification.preprocessing import (
    JapaneseNormalizationConfig,
    JapanesePreprocessingConfig,
    JapanesePreprocessor,
    JapaneseSegmentationConfig,
    UnsupportedPreprocessorVersion,
)

CASES = yaml.safe_load(
    (Path(__file__).parent / "fixtures" / "preprocessing_cases_ja.yml").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_preprocessing_cases(case: dict[str, object]) -> None:
    config = JapanesePreprocessingConfig(
        segmentation=JapaneseSegmentationConfig(
            remove_pos=tuple(case.get("remove_pos", [])),
            protect_negation=bool(case.get("protect_negation", True)),
            token_form=str(case.get("token_form", "normalized_form")),
        )
    )
    result = JapanesePreprocessor(config).transform(str(case["input"]))
    assert result.raw_text == case["input"]
    if "expected_text" in case:
        assert result.clean_text == case["expected_text"]
    for expected in case.get("expected_contains", []):
        assert expected in result.clean_text
    if "expected_tokens" in case:
        assert list(result.tokens) == case["expected_tokens"]
    for expected in case.get("expected_tokens_contain", []):
        assert expected in result.tokens


def test_fixture_has_at_least_30_concrete_cases() -> None:
    assert len(CASES) >= 30
    assert len({case["id"] for case in CASES}) == len(CASES)


def test_transform_is_deterministic_and_raw_text_is_unchanged() -> None:
    raw = "件名: ログインについて\nＡ URL: https://example.com"
    preprocessor = JapanesePreprocessor()
    first = preprocessor.transform(raw)
    second = preprocessor.transform(raw)
    assert first == second
    assert first.raw_text == raw


def test_each_layer_can_be_disabled() -> None:
    config = JapanesePreprocessingConfig(
        cleaning={"enabled": False},
        normalization=JapaneseNormalizationConfig(enabled=False),
        segmentation=JapaneseSegmentationConfig(enabled=False),
    )
    result = JapanesePreprocessor(config).transform("<b>ログイン</b>")
    assert result.clean_text == "<b>ログイン</b>"
    assert result.tokens == ()


def test_stats_are_nonnegative_and_count_replacements() -> None:
    result = JapanesePreprocessor().transform(
        "メールuser@example.co.jpまたはhttps://example.comをご確認ください"
    )
    assert result.stats.emails_replaced == 1
    assert result.stats.urls_replaced == 1
    assert result.stats.input_char_count > 0
    assert result.stats.output_token_count == len(result.tokens)


def test_unsupported_version_fails_explicitly() -> None:
    with pytest.raises(UnsupportedPreprocessorVersion):
        JapanesePreprocessor(JapanesePreprocessingConfig(version="2.0.0"))


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        JapanesePreprocessor().transform(None)  # type: ignore[arg-type]


def test_unknown_config_fields_are_rejected() -> None:
    with pytest.raises(Exception):
        JapanesePreprocessingConfig(unknown_field=True)  # type: ignore[call-arg]


def test_unknown_dictionary_is_rejected() -> None:
    with pytest.raises(Exception):
        JapanesePreprocessingConfig(dictionary="full-plus")


def test_sudachi_tokenizer_is_cached_across_instances() -> None:
    """Guards the project rule against re-initializing analyzer resources
    per document/instance (project_rules.md §5): constructing many
    preprocessors must not repeatedly reload the Sudachi dictionary.
    """
    from mail_classification.preprocessing.japanese import _load_sudachi_tokenizer

    first = JapanesePreprocessor().segmenter._tokenizer
    second = JapanesePreprocessor().segmenter._tokenizer
    assert first is second
    assert first is _load_sudachi_tokenizer("core")
