import pytest
from sklearn.pipeline import Pipeline

from mail_classification.models import (
    JA_CORE_CONDITIONS,
    apply_condition_preprocessing_ja,
    build_condition_pipeline_ja,
)

SAMPLE_TEXT = (
    "差出人: sender@example.com\n"
    "件名: 請求についての質問\n\n"
    "こんにちは、詳細はhttps://example.com/invoiceをご確認いただき、"
    "reply@example.comまでご連絡ください。\n"
    "ログインできません。\n"
    "--\n"
    "山田太郎\n"
    "\n"
    "> 以前のメッセージ\n"
    "サポートが次のように書きました:\n"
    "過去のやり取り\n"
)


def test_exactly_four_approved_conditions() -> None:
    assert set(JA_CORE_CONDITIONS) == {"J0", "J1", "J2", "JC"}


def test_j1_changes_only_tfidf_range_relative_to_j0() -> None:
    j0, j1 = JA_CORE_CONDITIONS["J0"], JA_CORE_CONDITIONS["J1"]

    assert j1.preprocessing_config == j0.preprocessing_config
    assert j1.segment_for_tfidf == j0.segment_for_tfidf
    assert j0.tfidf_params["ngram_range"] == (1, 1)
    assert j1.tfidf_params["ngram_range"] == (1, 2)


def test_j2_changes_only_cleaning_relative_to_j0() -> None:
    j0, j2 = JA_CORE_CONDITIONS["J0"], JA_CORE_CONDITIONS["J2"]

    assert j2.tfidf_params == j0.tfidf_params
    assert j2.preprocessing_config.normalization == j0.preprocessing_config.normalization
    assert j2.preprocessing_config.segmentation == j0.preprocessing_config.segmentation
    assert j2.preprocessing_config.cleaning != j0.preprocessing_config.cleaning

    j0_cleaning = j0.preprocessing_config.cleaning
    j2_cleaning = j2.preprocessing_config.cleaning
    for field in (
        "remove_headers",
        "remove_signatures",
        "remove_quoted_reply",
        "replace_urls",
        "replace_emails",
    ):
        assert getattr(j0_cleaning, field) is False
        assert getattr(j2_cleaning, field) is True


def test_jc_bypasses_segmentation_and_uses_character_ngrams() -> None:
    j0, jc = JA_CORE_CONDITIONS["J0"], JA_CORE_CONDITIONS["JC"]

    assert jc.segment_for_tfidf is False
    assert jc.preprocessing_config.segmentation.enabled is False
    assert jc.preprocessing_config.cleaning == j0.preprocessing_config.cleaning
    assert jc.tfidf_params["analyzer"] == "char_wb"
    assert jc.tfidf_params["ngram_range"] == (2, 3)


def test_no_condition_removes_particles_or_auxiliaries_or_disables_negation_protection() -> None:
    for condition in JA_CORE_CONDITIONS.values():
        assert condition.preprocessing_config.segmentation.remove_pos == ()
        assert condition.preprocessing_config.segmentation.protect_negation is True


def test_apply_condition_preprocessing_rejects_unknown_condition() -> None:
    with pytest.raises(ValueError, match="unknown Core condition"):
        apply_condition_preprocessing_ja("J9", ["text"])


def test_j0_preprocessing_leaves_header_signature_quote_url_email_intact() -> None:
    (cleaned,) = apply_condition_preprocessing_ja("J0", [SAMPLE_TEXT])

    # J0 does not remove header/signature/quote content, but its
    # normalized_form() tokenization can still transliterate ASCII loanwords
    # into katakana (Sudachi's dictionary maps "example" -> "エグザンプル",
    # matching the "email" -> "Eメール" behavior documented in
    # docs/contracts/preprocessing_contract_ja.md); that is a token-form
    # change, not content removal, so this checks presence, not the exact
    # literal domain string.
    assert "sender" in cleaned
    assert "エグザンプル" in cleaned
    assert "山田" in cleaned
    assert "以前" in cleaned


def test_j2_preprocessing_strips_header_signature_quote_and_masks_url_email() -> None:
    (cleaned,) = apply_condition_preprocessing_ja("J2", [SAMPLE_TEXT])

    assert "sender@example.com" not in cleaned
    assert "reply@example.com" not in cleaned
    assert "山田" not in cleaned
    assert "以前" not in cleaned
    assert "<" in cleaned and ">" in cleaned  # masked URL/email placeholder tokens


def test_j1_preprocessing_matches_j0_preprocessing() -> None:
    j0_cleaned = apply_condition_preprocessing_ja("J0", [SAMPLE_TEXT])
    j1_cleaned = apply_condition_preprocessing_ja("J1", [SAMPLE_TEXT])

    assert j0_cleaned == j1_cleaned


def test_j0_negation_is_preserved_as_a_token() -> None:
    (cleaned,) = apply_condition_preprocessing_ja("J0", ["ログインできません。"])
    tokens = cleaned.split()
    assert any(token in ("ない", "ず", "ぬ", "無い") for token in tokens)


def test_jc_output_is_unsegmented_text_not_space_joined_tokens() -> None:
    (cleaned,) = apply_condition_preprocessing_ja("JC", ["ログインできません。"])
    assert cleaned == "ログインできません。"


@pytest.mark.parametrize("condition_name", sorted(JA_CORE_CONDITIONS))
@pytest.mark.parametrize("model_name", ["linear_svc", "logistic_regression"])
def test_build_condition_pipeline_smoke_fits_for_every_cell(
    condition_name: str, model_name: str
) -> None:
    pipeline = build_condition_pipeline_ja(condition_name, model_name)
    texts = apply_condition_preprocessing_ja(
        condition_name,
        [
            "製品の対応OSについて教えてください",
            "アプリが開かなくなりました",
            "請求金額が間違っています",
            "アカウントにログインできません",
        ],
    )
    labels = ["product_inquiry", "technical_issue", "billing", "account_support"]

    assert isinstance(pipeline, Pipeline)
    pipeline.fit(texts, labels)
    predictions = pipeline.predict(texts)
    assert len(predictions) == len(texts)


def test_build_condition_pipeline_rejects_unknown_condition() -> None:
    with pytest.raises(ValueError, match="unknown Core condition"):
        build_condition_pipeline_ja("J9", "linear_svc")


def test_build_condition_pipeline_rejects_unknown_model() -> None:
    with pytest.raises(ValueError, match="unknown Core model_name"):
        build_condition_pipeline_ja("J0", "random_forest")
