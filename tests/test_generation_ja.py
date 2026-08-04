from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from mail_classification.generation import (
    JapaneseSyntheticMailGenerator,
    load_generation_config,
    load_ja_template_catalog,
    run_ja_generation_stage,
)
from mail_classification.generation.ja_generator import NEGATIONS
from mail_classification.generation.ja_models import JapaneseEmailTemplate
from mail_classification.generation.io import read_jsonl, records_to_jsonl_bytes, write_jsonl
from mail_classification.schemas import MailLabel, RawMailRecord

ROOT = Path(__file__).parents[1]
CONFIG = load_generation_config(ROOT / "configs" / "phase2_ja.yml")
CATALOG = load_ja_template_catalog(ROOT / CONFIG.paths.templates)


def generator(config=CONFIG, catalog=CATALOG) -> JapaneseSyntheticMailGenerator:
    return JapaneseSyntheticMailGenerator(config, catalog)


def test_same_seed_produces_identical_pilot_bytes() -> None:
    first = records_to_jsonl_bytes(generator().generate("pilot"))
    second = records_to_jsonl_bytes(generator().generate("pilot"))
    assert first == second


def test_different_seed_changes_pilot_output() -> None:
    changed = CONFIG.model_copy(
        update={
            "generator": CONFIG.generator.model_copy(
                update={"seed": CONFIG.generator.seed + 1}
            )
        }
    )
    assert records_to_jsonl_bytes(generator().generate("pilot")) != (
        records_to_jsonl_bytes(generator(changed).generate("pilot"))
    )


def test_smoke_has_eight_records_and_all_labels() -> None:
    records = generator().generate("smoke")
    assert len(records) == 8
    assert {record.label for record in records} == set(MailLabel)


def test_pilot_is_balanced_and_has_all_template_variations() -> None:
    records = generator().generate("pilot")
    assert len(records) == 96
    assert {
        label: sum(record.label == label for record in records)
        for label in MailLabel
    } == {label: 24 for label in MailLabel}
    assert len({record.template_group for record in records}) == 24
    assert len({(record.template_id, record.variation_id) for record in records}) == 96


def test_all_generated_records_pass_raw_schema() -> None:
    for record in generator().generate("pilot"):
        assert RawMailRecord.model_validate_json(record.model_dump_json()) == record


def test_raw_text_is_separate_and_contains_body_verbatim() -> None:
    for record in generator().generate("pilot"):
        assert record.body_text in record.raw_text
        original = record.raw_text
        RawMailRecord.model_validate(record.model_dump())
        assert record.raw_text == original


def test_ids_are_unique_and_use_ja_namespace() -> None:
    records = generator().generate("pilot")
    assert len({record.id for record in records}) == len(records)
    assert all(record.id.startswith("syn-ja-") for record in records)
    assert all(record.template_group.startswith("tg-ja-") for record in records)


def test_generated_at_is_deterministic_and_timezone_aware() -> None:
    timestamps = {record.generated_at for record in generator().generate("pilot")}
    assert timestamps == {datetime(2026, 8, 4, tzinfo=timezone.utc)}


def test_unknown_stage_is_rejected_and_full_is_enabled() -> None:
    with pytest.raises(ValueError, match="unknown generation stage"):
        generator().generate("other")
    assert len(generator().generate("full")) == 800


def test_empty_template_text_is_rejected() -> None:
    payload = CATALOG.templates[0].model_dump()
    payload["contexts"][0] = " "
    with pytest.raises(ValidationError):
        JapaneseEmailTemplate.model_validate(payload)


def test_semantic_template_id_is_required_and_covers_all_english_groups() -> None:
    ids = {template.semantic_template_id for template in CATALOG.templates}
    assert ids == {f"tg{index:03d}" for index in range(1, 25)}
    payload = CATALOG.templates[0].model_dump()
    del payload["semantic_template_id"]
    with pytest.raises(ValidationError):
        JapaneseEmailTemplate.model_validate(payload)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    records = generator().generate("smoke")
    output = tmp_path / "smoke.jsonl"
    digest = write_jsonl(output, records)
    assert read_jsonl(output) == records
    assert len(digest) == 64


def test_template_counts_are_equal_by_label() -> None:
    counts = {
        label: sum(template.label == label for template in CATALOG.templates)
        for label in MailLabel
    }
    assert counts == {label: 6 for label in MailLabel}


def test_formal_label_names_do_not_appear_in_generated_content_or_metadata() -> None:
    for record in generator().generate("pilot"):
        searchable = (
            record.raw_text + record.body_text + str(record.metadata)
        ).casefold()
        assert all(label.value not in searchable for label in MailLabel)


def test_each_label_contains_negation_and_multi_intent_examples() -> None:
    records = generator().generate("pilot")
    for label in MailLabel:
        label_records = [record for record in records if record.label == label]
        assert any(record.metadata["contains_negation"] for record in label_records)
        assert any(record.metadata["multi_intent"] for record in label_records)


def test_structural_components_are_spread_across_all_labels() -> None:
    records = generator().generate("pilot")
    for field in ("has_header", "has_signature", "has_quoted_reply"):
        assert {
            record.label for record in records if getattr(record, field)
        } == set(MailLabel)


def test_urgency_components_are_balanced_across_labels() -> None:
    records = generator().generate("pilot")
    counts = {
        label: Counter(
            record.metadata["component_indices"]["urgency"]
            for record in records
            if record.label == label
        )
        for label in MailLabel
    }
    assert len({tuple(sorted(count.items())) for count in counts.values()}) == 1
    assert all(count == 6 for count in counts[MailLabel.PRODUCT_INQUIRY].values())


def test_full_distribution_is_exact_and_deterministic() -> None:
    first = generator().generate("full")
    second = generator().generate("full")
    assert records_to_jsonl_bytes(first) == records_to_jsonl_bytes(second)
    assert len(first) == 800
    assert Counter(record.label for record in first) == {
        label: 200 for label in MailLabel
    }
    group_counts = Counter(record.template_group for record in first)
    assert set(group_counts.values()) == {33, 34}
    for label in MailLabel:
        difficulty_counts = Counter(
            record.difficulty.value for record in first if record.label == label
        )
        assert sorted(difficulty_counts.values()) == [66, 67, 67]
        urgency_counts = Counter(
            record.metadata["component_indices"]["urgency"]
            for record in first
            if record.label == label
        )
        assert urgency_counts == {index: 50 for index in range(4)}
    assert len({record.id for record in first}) == 800
    assert all("template_instance" in record.metadata for record in first)
    assert {
        record.metadata["generator_version"] for record in first
    } == {CONFIG.generator.full_version}


def test_contains_negation_uses_ja_negation_vocabulary() -> None:
    records = generator().generate("pilot")
    for label in MailLabel:
        negated = [
            record
            for record in records
            if record.label == label and record.metadata["contains_negation"]
        ]
        assert negated
        assert any(
            term in record.raw_text.casefold()
            for record in negated
            for term in NEGATIONS
        )


def test_semantic_template_id_is_recorded_in_metadata() -> None:
    for record in generator().generate("smoke"):
        assert record.metadata["semantic_template_id"].startswith("tg")


def test_reply_block_lead_in_matches_japanese_cleaner_pattern() -> None:
    from mail_classification.preprocessing.japanese import REPLY_BLOCK_PATTERN

    records = [r for r in generator().generate("pilot") if r.has_quoted_reply]
    assert records
    assert all(REPLY_BLOCK_PATTERN.search(record.raw_text) for record in records)


def test_header_lines_match_japanese_cleaner_pattern() -> None:
    from mail_classification.preprocessing.japanese import HEADER_PATTERN

    records = [r for r in generator().generate("pilot") if r.has_header]
    assert records
    assert all(HEADER_PATTERN.search(record.raw_text) for record in records)


def test_pipeline_writes_required_smoke_artifacts(tmp_path: Path) -> None:
    import shutil

    (tmp_path / "configs").mkdir()
    (tmp_path / "assets" / "templates").mkdir(parents=True)
    shutil.copy2(
        ROOT / "configs" / "phase2_ja.yml", tmp_path / "configs" / "phase2_ja.yml"
    )
    shutil.copy2(ROOT / CONFIG.paths.templates, tmp_path / CONFIG.paths.templates)
    first = run_ja_generation_stage("smoke", tmp_path)
    second = run_ja_generation_stage("smoke", tmp_path)
    assert first.count == 8
    assert first.data_hash == second.data_hash
    assert first.automatic_quality_pass
    assert first.data_path.exists()
    assert first.summary_path.exists()
    assert first.manifest_path.exists()


def test_pipeline_rejects_full_without_tracked_pilot_approval(tmp_path: Path) -> None:
    import shutil

    (tmp_path / "configs").mkdir()
    (tmp_path / "assets" / "templates").mkdir(parents=True)
    shutil.copy2(
        ROOT / "configs" / "phase2_ja.yml", tmp_path / "configs" / "phase2_ja.yml"
    )
    shutil.copy2(ROOT / CONFIG.paths.templates, tmp_path / CONFIG.paths.templates)
    with pytest.raises(ValueError, match="tracked Pilot approval is missing"):
        run_ja_generation_stage("full", tmp_path)
