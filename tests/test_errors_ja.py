from datetime import datetime, timezone

from mail_classification.explain.ja_errors import (
    build_misclassification_rows_ja,
    summarize_error_categories,
    summarize_error_category_counts,
)
from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord


def _record(
    record_id,
    label,
    *,
    raw_text="本文",
    body_text="本文",
    difficulty=Difficulty.EASY,
    has_header=False,
    has_signature=False,
    has_quoted_reply=False,
    multi_intent=False,
    secondary_intent=None,
    contains_negation=False,
) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text=raw_text,
        body_text=body_text,
        label=label,
        template_group=f"{label.value}-g0",
        difficulty=difficulty,
        has_header=has_header,
        has_signature=has_signature,
        has_quoted_reply=has_quoted_reply,
        generation_seed=1,
        template_id=f"{label.value}-g0",
        variation_id=0,
        generated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        metadata={
            "multi_intent": multi_intent,
            "secondary_intent": secondary_intent,
            "contains_negation": contains_negation,
        },
    )


def _oof_row(sample_id, condition, model, fold_id, true_label, predicted_label):
    return {
        "sample_id": sample_id,
        "condition": condition,
        "model": model,
        "fold_id": fold_id,
        "true_label": true_label,
        "predicted_label": predicted_label,
    }


def test_build_misclassification_rows_skips_correct_predictions() -> None:
    record = _record("m1", MailLabel.BILLING)
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "billing")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows == []


def test_multi_intent_takes_priority_and_all_flags_are_boolean_columns() -> None:
    record = _record(
        "m1",
        MailLabel.BILLING,
        difficulty=Difficulty.HARD,
        multi_intent=True,
        secondary_intent="technical_issue",
        contains_negation=True,
    )
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "technical_issue")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert len(rows) == 1
    row = rows[0]
    assert row["primary_category"] == "multi_intent"
    # Categories overlap and are not collapsed to a single pick.
    assert row["cat_multi_intent"] is True
    assert row["cat_ambiguous_difficulty"] is True
    assert row["cat_negation_present"] is True
    assert row["cat_uncategorized"] is False


def test_ascii_email_in_header_does_not_falsely_trigger_mixed_ja_en() -> None:
    """Regression test for a heuristic bug caught by inspecting real output:
    an earlier version scanned raw_text (which always contains an ASCII
    sender email when has_header=True) instead of body_text, so ~62% of
    records were wrongly flagged mixed_ja_en from header noise alone even
    when the body was pure Japanese.
    """
    record = _record(
        "m1",
        MailLabel.BILLING,
        raw_text="差出人: taro@example.com\n件名: 請求\n\nログインできません。",
        body_text="ログインできません。",
        has_header=True,
    )
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_mixed_ja_en"] is False


def test_genuine_body_level_en_ja_mixing_is_detected() -> None:
    record = _record(
        "m1",
        MailLabel.PRODUCT_INQUIRY,
        body_text="iPhone 15で2FAが届きません",
    )
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "product_inquiry", "technical_issue")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_mixed_ja_en"] is True


def test_ordinary_japanese_text_does_not_falsely_trigger_orthographic_variation() -> None:
    """Regression test: an earlier version treated any East Asian Width "W"
    + isalnum() character as "fullwidth alnum", which matches ordinary
    hiragana/katakana/kanji, not just fullwidth ASCII forms (Ａ-Ｚ, １-９) --
    caught by inspecting the real category-count output (~64%) before
    trusting it.
    """
    record = _record("m1", MailLabel.BILLING, body_text="解約したいわけではないのですが、次回の請求だけ止められますか。")
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_orthographic_variation"] is False


def test_true_fullwidth_halfwidth_mix_triggers_orthographic_variation() -> None:
    record = _record("m1", MailLabel.PRODUCT_INQUIRY, body_text="ＡＢＣ１２３とABC123の表示が違います")
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "product_inquiry", "technical_issue")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_orthographic_variation"] is True


def test_dekiru_kanji_variant_triggers_orthographic_variation() -> None:
    record = _record("m1", MailLabel.ACCOUNT_SUPPORT, body_text="ログイン出来ない状態です")
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "account_support", "technical_issue")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_orthographic_variation"] is True


def test_glued_url_triggers_morphological_segmentation() -> None:
    record = _record(
        "m1", MailLabel.PRODUCT_INQUIRY, body_text="https://example.invalid/setupの手順が分かりません"
    )
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "product_inquiry", "technical_issue")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["cat_morphological_segmentation"] is True


def test_no_category_matches_falls_back_to_uncategorized() -> None:
    record = _record("m1", MailLabel.BILLING, body_text="請求内容を教えてください")
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    assert rows[0]["primary_category"] == "uncategorized"
    assert rows[0]["cat_uncategorized"] is True


def test_processed_text_is_looked_up_by_condition_and_sample_id() -> None:
    record = _record("m1", MailLabel.BILLING)
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows_ja(
        oof_rows, {"m1": record}, {("J0", "m1"): "請求 内容"}
    )

    assert rows[0]["processed_text"] == "請求 内容"
    assert rows[0]["raw_text"] == record.raw_text


def test_summarize_error_categories_counts_per_condition_model_category() -> None:
    rows = [
        {"condition": "J0", "model": "linear_svc", "primary_category": "multi_intent"},
        {"condition": "J0", "model": "linear_svc", "primary_category": "multi_intent"},
        {"condition": "J0", "model": "linear_svc", "primary_category": "uncategorized"},
        {"condition": "J1", "model": "linear_svc", "primary_category": "multi_intent"},
    ]

    summary = summarize_error_categories(rows)

    counts = {
        (row["condition"], row["model"], row["primary_category"]): row["count"]
        for row in summary
    }
    assert counts[("J0", "linear_svc", "multi_intent")] == 2
    assert counts[("J0", "linear_svc", "uncategorized")] == 1
    assert counts[("J1", "linear_svc", "multi_intent")] == 1


def test_summarize_error_category_counts_allows_overlap_beyond_100_percent() -> None:
    record = _record(
        "m1",
        MailLabel.BILLING,
        difficulty=Difficulty.HARD,
        multi_intent=True,
        secondary_intent="x",
        contains_negation=True,
    )
    oof_rows = [_oof_row("m1", "J0", "linear_svc", 0, "billing", "account_support")]
    rows = build_misclassification_rows_ja(oof_rows, {"m1": record}, {})

    counts = summarize_error_category_counts(rows)
    by_category = {row["category"]: row for row in counts}
    # A single misclassified row matching 3 categories (multi_intent,
    # ambiguous_difficulty, negation_present) must show up in all 3, each
    # at share_of_misclassified == 1.0 -- shares are not forced to sum to 1.
    assert by_category["multi_intent"]["count"] == 1
    assert by_category["ambiguous_difficulty"]["count"] == 1
    assert by_category["negation_present"]["count"] == 1
    assert by_category["multi_intent"]["share_of_misclassified"] == 1.0
