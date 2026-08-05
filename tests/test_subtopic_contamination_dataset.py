from collections import Counter
from pathlib import Path

import pytest

from mail_classification.extensions.subtopic_contamination import (
    CONTAMINATION_FRACTIONS,
    CONTAMINATION_LEVELS,
    SUBTOPIC_SENTENCES,
    apply_contamination,
    build_condition_records,
    build_contamination_assignment,
)
from mail_classification.extensions.subtopic_contamination.sentences import STYLES
from mail_classification.generation.io import read_jsonl, records_to_jsonl_bytes
from mail_classification.schemas import sha256_bytes
from test_cv import synthetic_records

ROOT = Path(__file__).parents[1]
FULL_DATA_PATH = ROOT / "data" / "raw" / "full_emails.jsonl"


def _skip_unless_full_data() -> list:
    if not FULL_DATA_PATH.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")
    return read_jsonl(FULL_DATA_PATH)


# --- Sentence bank -----------------------------------------------------


def test_sentence_bank_covers_all_styles_with_no_literal_label_names() -> None:
    label_words = {"billing", "technical_issue", "product_inquiry", "account_support"}
    for subtopic, sentences in SUBTOPIC_SENTENCES.items():
        assert len(sentences) == 12
        assert {s.style for s in sentences} == set(STYLES)
        for sentence in sentences:
            lowered = sentence.text.lower()
            for label_word in label_words:
                assert label_word not in lowered.replace("_", "")


# --- Insertion never touches header/signature/quoted-reply -------------


def test_insertion_only_modifies_body_text_substring() -> None:
    from datetime import datetime, timezone

    from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord

    record = RawMailRecord(
        id="m1",
        raw_text="From: a@b.com\nSubject: Hi\n\nHello,\n\nMy main point.\n\n--\nAlex",
        body_text="Hello,\n\nMy main point.",
        label=MailLabel.BILLING,
        template_group="g0",
        difficulty=Difficulty.EASY,
        has_header=True,
        has_signature=True,
        has_quoted_reply=False,
        generation_seed=1,
        template_id="g0",
        variation_id=0,
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )

    for position in ("early", "mid", "end"):
        new_raw, new_body = apply_contamination(record, "A subtopic sentence.", position)
        assert "From: a@b.com" in new_raw
        assert "--\nAlex" in new_raw
        assert "A subtopic sentence." in new_body
        assert "A subtopic sentence." in new_raw
        assert new_raw.count("A subtopic sentence.") == 1


# --- Assignment: nesting, rate, balance ---------------------------------


def test_assignment_is_nested_c10_subset_c20_subset_c30() -> None:
    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)

    c10 = {row.sample_id for row in assignment if row.applies_at("C10")}
    c20 = {row.sample_id for row in assignment if row.applies_at("C20")}
    c30 = {row.sample_id for row in assignment if row.applies_at("C30")}

    assert c10 <= c20 <= c30
    assert c10 and c20 and c30


def test_assignment_never_pairs_a_sample_with_its_own_label() -> None:
    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)
    for row in assignment:
        assert row.subtopic_label != row.main_label


def test_assignment_is_deterministic_for_same_seed() -> None:
    records = synthetic_records()
    first = build_contamination_assignment(records, seed=42)
    second = build_contamination_assignment(records, seed=42)
    assert [row.as_dict() for row in first] == [row.as_dict() for row in second]


def test_assignment_differs_for_different_seed() -> None:
    records = synthetic_records()
    a = build_contamination_assignment(records, seed=42)
    b = build_contamination_assignment(records, seed=7)
    assert [row.sentence_text for row in a] != [row.sentence_text for row in b]


def test_contamination_rate_matches_target_on_real_full_data() -> None:
    records = _skip_unless_full_data()
    assignment = build_contamination_assignment(records, seed=42)
    for level, fraction in CONTAMINATION_FRACTIONS.items():
        n = sum(1 for row in assignment if row.applies_at(level))
        assert n == round(len(records) * fraction), level


def test_subtopic_combinations_are_not_overly_skewed_on_real_full_data() -> None:
    records = _skip_unless_full_data()
    assignment = build_contamination_assignment(records, seed=42)
    pair_counts = Counter(
        (row.main_label, row.subtopic_label) for row in assignment if row.applies_at("C30")
    )
    # 4 main labels x 3 possible subtopics each = 12 pairs; the design targets
    # an exact 20/20/20 split per main label (60 contaminated / 3 subtopics).
    assert len(pair_counts) == 12
    counts = list(pair_counts.values())
    assert max(counts) - min(counts) <= 2


def test_sentence_variant_usage_is_not_overly_skewed_on_real_full_data() -> None:
    records = _skip_unless_full_data()
    assignment = build_contamination_assignment(records, seed=42)
    c30_rows = [row for row in assignment if row.applies_at("C30")]
    usage = Counter((row.subtopic_label, row.variant_id) for row in c30_rows)
    subtopic_totals = Counter(row.subtopic_label for row in c30_rows)
    for (subtopic, _variant_id), count in usage.items():
        expected = subtopic_totals[subtopic] / 12
        assert count <= expected * 2.5


# --- Dataset materialization: C0 identity, label/class invariance -------


def test_c0_dataset_is_byte_identical_to_approved_full_data() -> None:
    records = _skip_unless_full_data()
    assignment = build_contamination_assignment(records, seed=42)
    c0_records = build_condition_records(records, assignment, "C0")

    assert sha256_bytes(records_to_jsonl_bytes(c0_records)) == sha256_bytes(
        records_to_jsonl_bytes(records)
    )


def test_class_distribution_is_unchanged_across_all_levels() -> None:
    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)
    baseline = Counter(r.label for r in records)
    for level in CONTAMINATION_LEVELS:
        level_records = build_condition_records(records, assignment, level)
        assert Counter(r.label for r in level_records) == baseline


def test_same_sample_ids_present_across_all_four_conditions() -> None:
    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)
    id_sets = [
        {r.id for r in build_condition_records(records, assignment, level)}
        for level in CONTAMINATION_LEVELS
    ]
    assert all(ids == id_sets[0] for ids in id_sets)
    assert id_sets[0] == {r.id for r in records}


def test_contamination_metadata_never_appears_in_raw_or_body_text() -> None:
    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)
    c30_records = build_condition_records(records, assignment, "C30")
    for record in c30_records:
        assert "subtopic_contamination" not in record.raw_text
        assert "subtopic_contamination" not in record.body_text
        assert "contamination_level" not in record.raw_text
        assert "C30" not in record.raw_text


def test_model_input_pipeline_only_ever_reads_raw_text_not_metadata() -> None:
    """Metadata carries contamination provenance but must be inert to the Core Pipeline."""
    from mail_classification.models import apply_condition_preprocessing

    records = synthetic_records()
    assignment = build_contamination_assignment(records, seed=42)
    c30_records = build_condition_records(records, assignment, "C30")

    contaminated = [r for r in c30_records if "subtopic_contamination" in r.metadata]
    assert contaminated  # sanity: contamination actually happened

    stripped = [r.model_copy(update={"metadata": {}}) for r in c30_records]
    preprocessed_with_metadata = apply_condition_preprocessing(
        "D0", [r.raw_text for r in c30_records]
    )
    preprocessed_without_metadata = apply_condition_preprocessing(
        "D0", [r.raw_text for r in stripped]
    )
    assert preprocessed_with_metadata == preprocessed_without_metadata
