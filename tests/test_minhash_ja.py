from datetime import datetime, timezone

import pytest

from mail_classification.extensions import (
    char_shingles,
    find_near_duplicates_ja,
    summarize_near_duplicates_ja,
)
from mail_classification.quality.ja_duplicates import find_duplicates
from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord


def _record(record_id: str, label: MailLabel, body_text: str, template_group: str = "g0") -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text=body_text,
        body_text=body_text,
        label=label,
        template_group=template_group,
        difficulty=Difficulty.EASY,
        has_header=False,
        has_signature=False,
        has_quoted_reply=False,
        generation_seed=1,
        template_id=template_group,
        variation_id=0,
        generated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )


def test_char_shingles_basic() -> None:
    shingles = char_shingles("ログインできません", k=5)

    assert "ログイン" not in shingles  # too short (4 chars) for k=5
    assert "ログインで" in shingles
    assert "グインでき" in shingles
    assert len(shingles) == len("ログインできません") - 5 + 1


def test_char_shingles_short_text_returns_single_shingle() -> None:
    assert char_shingles("こんにちは", k=10) == {"こんにちは"}


def test_char_shingles_empty_text_returns_empty_set() -> None:
    assert char_shingles("", k=5) == frozenset()


def test_find_near_duplicates_rejects_empty_records() -> None:
    with pytest.raises(ValueError, match="at least one record"):
        find_near_duplicates_ja([])


def test_find_near_duplicates_finds_shared_boilerplate_pair() -> None:
    shared = (
        "いつもお世話になっております。注文の状況について確認したいことがあります。"
        "今週中に発送されるかどうか教えてください。よろしくお願いいたします。"
    )
    records = [
        _record("m1", MailLabel.PRODUCT_INQUIRY, shared),
        _record("m2", MailLabel.PRODUCT_INQUIRY, shared + "もう一点質問があります。"),
        _record(
            "m3",
            MailLabel.TECHNICAL_ISSUE,
            "ノートパソコンでログイン直後にアプリが強制終了してしまいます。",
        ),
    ]

    rows = find_near_duplicates_ja(records, num_perm=32, bands=8, threshold=0.5)

    pairs = {(row["sample_id_a"], row["sample_id_b"]) for row in rows}
    assert ("m1", "m2") in pairs
    assert not any("m3" in pair for pair in pairs)


def test_find_near_duplicates_flags_exact_and_normalized_duplicates() -> None:
    text = "次回の請求だけ止めていただけますでしょうか。解約は希望しておりません。"
    records = [
        _record("m1", MailLabel.BILLING, text),
        _record("m2", MailLabel.BILLING, text),  # byte-identical
    ]

    rows = find_near_duplicates_ja(records, num_perm=32, bands=8, threshold=0.5)

    assert len(rows) == 1
    assert rows[0]["exact_raw_duplicate"] is True
    assert rows[0]["exact_body_duplicate"] is True
    assert rows[0]["normalized_duplicate"] is True
    assert rows[0]["jaccard_similarity"] == 1.0


def test_find_near_duplicates_flags_cross_label_pairs_distinctly() -> None:
    shared = "アカウントの状況について今すぐ確認していただきたいことがあります。"
    records = [
        _record("m1", MailLabel.BILLING, shared),
        _record("m2", MailLabel.ACCOUNT_SUPPORT, shared + "至急お願いします。"),
    ]

    rows = find_near_duplicates_ja(records, num_perm=32, bands=8, threshold=0.5)

    assert len(rows) == 1
    assert rows[0]["same_label"] is False


def test_summarize_near_duplicates_counts_categories() -> None:
    rows = [
        {
            "same_label": True,
            "same_template_group": True,
            "exact_raw_duplicate": True,
            "exact_body_duplicate": True,
            "normalized_duplicate": True,
        },
        {
            "same_label": False,
            "same_template_group": False,
            "exact_raw_duplicate": False,
            "exact_body_duplicate": False,
            "normalized_duplicate": False,
        },
    ]

    summary = summarize_near_duplicates_ja(rows)

    assert summary["total_candidate_pairs"] == 2
    assert summary["additional_beyond_core_exact_normalized"] == 1
    assert summary["cross_label_pairs"] == 1
    assert summary["same_template_group_pairs"] == 1
    assert summary["different_template_group_pairs"] == 1


def test_minhash_ja_runs_independently_alongside_core_ja_duplicate_check() -> None:
    records = [
        _record("m1", MailLabel.BILLING, "解約をお願いします。"),
        _record("m2", MailLabel.BILLING, "解約をお願いします。"),
    ]

    core_rows = find_duplicates(records)
    extension_rows = find_near_duplicates_ja(records, num_perm=16, bands=4, threshold=0.5)

    assert core_rows
    assert extension_rows
