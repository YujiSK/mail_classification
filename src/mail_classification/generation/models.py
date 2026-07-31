"""Validated configuration and reviewable template definitions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from mail_classification.schemas import Difficulty, MailLabel
from mail_classification.schemas.common import require_aware_datetime, require_nonblank


class StageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(gt=0)
    enabled: bool


class QualityThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_template_groups_per_label: int = Field(gt=0)
    max_class_ratio_deviation: float = Field(ge=0, le=1)
    max_length_mean_ratio: float = Field(ge=1)
    max_template_group_share: float = Field(gt=0, le=1)
    max_exact_duplicate_groups: int = Field(ge=0)
    max_normalized_duplicate_groups: int = Field(ge=0)
    exclusive_feature_min_count: int = Field(gt=1)
    full_exclusive_feature_min_count: int = Field(gt=1)
    max_shared_component_ratio_deviation: float = Field(ge=0, le=1)
    max_template_group_count_difference: int = Field(ge=0)
    max_difficulty_count_difference: int = Field(ge=0)
    review_samples_per_label: int = Field(gt=0)
    required_difficulties: list[Difficulty] = Field(min_length=1)


class OutputPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    templates: str
    smoke_data: str
    pilot_data: str
    full_data: str
    pilot_review_decision: str
    quality_dir: str
    manifest_dir: str

    _nonblank_templates = field_validator("templates")(require_nonblank)
    _nonblank_smoke = field_validator("smoke_data")(require_nonblank)
    _nonblank_pilot = field_validator("pilot_data")(require_nonblank)
    _nonblank_full = field_validator("full_data")(require_nonblank)
    _nonblank_decision = field_validator("pilot_review_decision")(require_nonblank)
    _nonblank_quality = field_validator("quality_dir")(require_nonblank)
    _nonblank_manifest = field_validator("manifest_dir")(require_nonblank)


class GeneratorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    full_version: str
    seed: int = Field(ge=0)
    deterministic_generated_at: datetime
    variations_per_template: int = Field(gt=0)

    _nonblank_version = field_validator("version")(require_nonblank)
    _nonblank_full_version = field_validator("full_version")(require_nonblank)
    _aware_timestamp = field_validator("deterministic_generated_at")(
        require_aware_datetime
    )


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    generator: GeneratorSettings
    stages: dict[str, StageConfig]
    quality: QualityThresholds
    paths: OutputPaths

    @model_validator(mode="after")
    def validate_stages(self) -> "GenerationConfig":
        if set(self.stages) != {"smoke", "pilot", "full"}:
            raise ValueError("stages must contain exactly smoke, pilot, and full")
        if not 4 <= self.stages["smoke"].count <= 8:
            raise ValueError("smoke count must be between 4 and 8")
        if not 80 <= self.stages["pilot"].count <= 120:
            raise ValueError("pilot count must be between 80 and 120")
        if self.stages["full"].count != 800:
            raise ValueError("full count must be exactly 800")
        return self


class SharedComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greetings: list[str] = Field(min_length=2)
    closings: list[str] = Field(min_length=2)
    signatures: list[list[str]] = Field(min_length=2)
    senders: list[str] = Field(min_length=2)
    subjects: list[str] = Field(min_length=2)
    quoted_replies: list[list[str]] = Field(min_length=2)
    urgency_lines: list[str] = Field(min_length=2)

    @field_validator("greetings", "closings", "senders", "subjects")
    @classmethod
    def validate_string_pool(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("component pools cannot contain blank strings")
        return values

    @field_validator("signatures", "quoted_replies")
    @classmethod
    def validate_line_pool(cls, values: list[list[str]]) -> list[list[str]]:
        if any(not lines or any(not line.strip() for line in lines) for lines in values):
            raise ValueError("multi-line components cannot be empty")
        return values

    @field_validator("urgency_lines")
    @classmethod
    def validate_urgency_pool(cls, values: list[str]) -> list[str]:
        if values.count("") != 1:
            raise ValueError("urgency_lines must contain exactly one empty option")
        if any(not value.strip() for value in values if value):
            raise ValueError("non-empty urgency lines cannot be blank")
        if len(values) != len(set(values)):
            raise ValueError("urgency lines must be unique")
        return values


class EmailTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    template_group: str
    label: MailLabel
    difficulty: Difficulty
    contexts: list[str] = Field(min_length=1)
    main_requests: list[str] = Field(min_length=1)
    secondary_details: list[str] = Field(min_length=1)
    multi_intent: bool = False
    secondary_intent: str | None = None

    _nonblank_id = field_validator("template_id")(require_nonblank)
    _nonblank_group = field_validator("template_group")(require_nonblank)

    @field_validator("contexts", "main_requests", "secondary_details")
    @classmethod
    def validate_variations(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("template variation text cannot be blank")
        return values

    @model_validator(mode="after")
    def validate_intent(self) -> "EmailTemplate":
        lengths = {len(self.contexts), len(self.main_requests), len(self.secondary_details)}
        if len(lengths) != 1:
            raise ValueError("context, request, and detail variation counts must match")
        if self.multi_intent != (self.secondary_intent is not None):
            raise ValueError("multi_intent and secondary_intent must be declared together")
        return self


class TemplateCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    shared: SharedComponents
    templates: list[EmailTemplate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "TemplateCatalog":
        ids = [template.template_id for template in self.templates]
        groups = [template.template_group for template in self.templates]
        if len(ids) != len(set(ids)):
            raise ValueError("template_id values must be unique")
        if len(groups) != len(set(groups)):
            raise ValueError("template_group values must be unique")
        return self


def load_generation_config(path: str | Path) -> GenerationConfig:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return GenerationConfig.model_validate(payload)
