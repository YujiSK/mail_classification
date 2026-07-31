from datetime import datetime, timezone

import pytest

from mail_classification.extensions import (
    exact_jaccard,
    find_near_duplicates,
    lsh_candidate_pairs,
    minhash_signature,
    summarize_near_duplicates,
    word_shingles,
)
from mail_classification.quality import find_duplicates
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
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


def test_word_shingles_basic() -> None:
    shingles = word_shingles("the quick brown fox jumps", k=3)

    assert shingles == {
        "the quick brown",
        "quick brown fox",
        "brown fox jumps",
    }


def test_word_shingles_short_text_returns_single_shingle() -> None:
    assert word_shingles("hi there", k=3) == {"hi there"}


def test_word_shingles_empty_text_returns_empty_set() -> None:
    assert word_shingles("", k=3) == frozenset()


def test_exact_jaccard_identical_sets() -> None:
    a = frozenset({"a", "b", "c"})
    assert exact_jaccard(a, a) == 1.0


def test_exact_jaccard_disjoint_sets() -> None:
    assert exact_jaccard(frozenset({"a"}), frozenset({"b"})) == 0.0


def test_exact_jaccard_partial_overlap() -> None:
    a = frozenset({"a", "b", "c", "d"})
    b = frozenset({"c", "d", "e", "f"})
    assert exact_jaccard(a, b) == pytest.approx(2 / 6)


def test_exact_jaccard_both_empty_is_one() -> None:
    assert exact_jaccard(frozenset(), frozenset()) == 1.0


def test_minhash_signature_is_deterministic_for_same_seed() -> None:
    shingles = word_shingles("the quick brown fox jumps over the lazy dog")

    first = minhash_signature(shingles, num_perm=32, seed=42)
    second = minhash_signature(shingles, num_perm=32, seed=42)

    assert first == second
    assert len(first) == 32


def test_minhash_signature_differs_for_different_seed() -> None:
    shingles = word_shingles("the quick brown fox jumps over the lazy dog")

    a = minhash_signature(shingles, num_perm=32, seed=1)
    b = minhash_signature(shingles, num_perm=32, seed=2)

    assert a != b


def test_minhash_signature_empty_shingles_is_all_zero() -> None:
    assert minhash_signature(frozenset(), num_perm=8) == (0,) * 8


def test_lsh_candidate_pairs_groups_identical_signatures() -> None:
    signatures = {
        "a": (1, 2, 3, 4),
        "b": (1, 2, 3, 4),
        "c": (9, 9, 9, 9),
    }

    candidates = lsh_candidate_pairs(signatures, bands=2)

    assert ("a", "b") in candidates
    assert ("a", "c") not in candidates
    assert ("b", "c") not in candidates


def test_lsh_candidate_pairs_rejects_non_divisible_bands() -> None:
    signatures = {"a": (1, 2, 3), "b": (1, 2, 3)}

    with pytest.raises(ValueError, match="divisible"):
        lsh_candidate_pairs(signatures, bands=2)


def test_lsh_candidate_pairs_empty_input() -> None:
    assert lsh_candidate_pairs({}, bands=4) == set()


def test_find_near_duplicates_rejects_empty_records() -> None:
    with pytest.raises(ValueError, match="at least one record"):
        find_near_duplicates([])


def test_find_near_duplicates_finds_shared_boilerplate_pair() -> None:
    shared = (
        "Hello team, I would like to ask about my recent order status "
        "and whether it will ship this week. Thank you for your help."
    )
    records = [
        _record("m1", MailLabel.PRODUCT_INQUIRY, shared),
        _record("m2", MailLabel.PRODUCT_INQUIRY, shared + " Also, one more question."),
        _record(
            "m3",
            MailLabel.TECHNICAL_ISSUE,
            "The application crashes immediately after login on my laptop.",
        ),
    ]

    rows = find_near_duplicates(records, num_perm=32, bands=8, threshold=0.5)

    pairs = {(row["sample_id_a"], row["sample_id_b"]) for row in rows}
    assert ("m1", "m2") in pairs
    assert not any("m3" in pair for pair in pairs)


def test_find_near_duplicates_flags_exact_and_normalized_duplicates() -> None:
    text = "Please cancel my subscription before the next billing cycle starts."
    records = [
        _record("m1", MailLabel.BILLING, text),
        _record("m2", MailLabel.BILLING, text),  # byte-identical
    ]

    rows = find_near_duplicates(records, num_perm=32, bands=8, threshold=0.5)

    assert len(rows) == 1
    assert rows[0]["exact_raw_duplicate"] is True
    assert rows[0]["exact_body_duplicate"] is True
    assert rows[0]["normalized_duplicate"] is True
    assert rows[0]["jaccard_similarity"] == 1.0


def test_find_near_duplicates_flags_cross_label_pairs_distinctly() -> None:
    shared = "I need help understanding this issue with my account right now please."
    records = [
        _record("m1", MailLabel.BILLING, shared),
        _record("m2", MailLabel.ACCOUNT_SUPPORT, shared + " urgent"),
    ]

    rows = find_near_duplicates(records, num_perm=32, bands=8, threshold=0.5)

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

    summary = summarize_near_duplicates(rows)

    assert summary["total_candidate_pairs"] == 2
    assert summary["additional_beyond_core_exact_normalized"] == 1
    assert summary["cross_label_pairs"] == 1
    assert summary["same_template_group_pairs"] == 1
    assert summary["different_template_group_pairs"] == 1


def test_minhash_never_imports_or_calls_quality_module_state() -> None:
    # Sanity check that this Extension module and Core's duplicate checker
    # can both run independently over the same records without interfering.
    records = [
        _record("m1", MailLabel.BILLING, "Please cancel my subscription."),
        _record("m2", MailLabel.BILLING, "Please cancel my subscription."),
    ]

    core_rows = find_duplicates(records)
    extension_rows = find_near_duplicates(records, num_perm=16, bands=4, threshold=0.5)

    assert core_rows  # Core's exact-duplicate check also finds this pair
    assert extension_rows
