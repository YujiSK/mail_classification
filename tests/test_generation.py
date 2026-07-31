from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mail_classification.generation import (
    SyntheticMailGenerator,
    load_generation_config,
    load_template_catalog,
)
from mail_classification.generation.io import (
    read_jsonl,
    records_to_jsonl_bytes,
    write_jsonl,
)
from mail_classification.generation.pipeline import run_generation_stage
from mail_classification.generation import pipeline
from mail_classification.generation.models import EmailTemplate, GenerationConfig
from mail_classification.schemas import MailLabel, RawMailRecord

ROOT = Path(__file__).parents[1]
CONFIG = load_generation_config(ROOT / "configs" / "phase2.yml")
CATALOG = load_template_catalog(ROOT / CONFIG.paths.templates)


def generator(config=CONFIG, catalog=CATALOG) -> SyntheticMailGenerator:
    return SyntheticMailGenerator(config, catalog)


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


def test_ids_are_unique_and_template_groups_are_nonblank() -> None:
    records = generator().generate("pilot")
    assert len({record.id for record in records}) == len(records)
    assert all(record.template_group.strip() for record in records)


def test_generated_at_is_deterministic_and_timezone_aware() -> None:
    timestamps = {record.generated_at for record in generator().generate("pilot")}
    assert timestamps == {datetime(2026, 7, 31, tzinfo=timezone.utc)}


def test_unknown_stage_and_disabled_full_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown generation stage"):
        generator().generate("other")
    with pytest.raises(ValueError, match="disabled"):
        generator().generate("full")


def test_invalid_enabled_full_config_is_rejected() -> None:
    payload = CONFIG.model_dump(mode="json")
    payload["stages"]["full"]["enabled"] = True
    with pytest.raises(ValidationError, match="full stage"):
        GenerationConfig.model_validate(payload)


def test_invalid_smoke_count_is_rejected() -> None:
    payload = CONFIG.model_dump(mode="json")
    payload["stages"]["smoke"]["count"] = 9
    with pytest.raises(ValidationError, match="smoke count"):
        GenerationConfig.model_validate(payload)


def test_empty_template_text_is_rejected() -> None:
    payload = CATALOG.templates[0].model_dump()
    payload["contexts"][0] = " "
    with pytest.raises(ValidationError):
        EmailTemplate.model_validate(payload)


def test_unknown_template_label_is_rejected() -> None:
    payload = CATALOG.templates[0].model_dump()
    payload["label"] = "unknown"
    with pytest.raises(ValidationError):
        EmailTemplate.model_validate(payload)


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


def test_each_label_covers_all_required_negation_forms() -> None:
    records = generator().generate("pilot")
    required = ("not", "no", "never", "without", "cannot", "can't", "don't")
    for label in MailLabel:
        text = "\n".join(
            record.raw_text.casefold() for record in records if record.label == label
        )
        assert all(term in text for term in required)


def test_structural_components_are_spread_across_all_labels() -> None:
    records = generator().generate("pilot")
    for field in ("has_header", "has_signature", "has_quoted_reply"):
        assert {
            record.label for record in records if getattr(record, field)
        } == set(MailLabel)


def test_pipeline_writes_required_smoke_artifacts(tmp_path: Path) -> None:
    import shutil

    (tmp_path / "configs").mkdir()
    (tmp_path / "assets" / "templates").mkdir(parents=True)
    shutil.copy2(ROOT / "configs" / "phase2.yml", tmp_path / "configs" / "phase2.yml")
    shutil.copy2(
        ROOT / CONFIG.paths.templates,
        tmp_path / CONFIG.paths.templates,
    )
    first = run_generation_stage("smoke", tmp_path)
    second = run_generation_stage("smoke", tmp_path)
    assert first.count == 8
    assert first.data_hash == second.data_hash
    assert first.automatic_quality_pass
    assert first.data_path.exists()
    assert first.summary_path.exists()
    assert first.manifest_path.exists()


def test_clean_git_status_is_recorded_as_false(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    assert pipeline._git_dirty(ROOT) is False


def test_failed_git_status_is_recorded_as_null(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="bad"),
    )
    assert pipeline._git_dirty(ROOT) is None
