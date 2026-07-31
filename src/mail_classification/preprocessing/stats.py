"""Typed output and observability for preprocessing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProcessingStats(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_char_count: int = Field(ge=0)
    output_char_count: int = Field(ge=0)
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    chars_removed: int = Field(ge=0)
    tokens_removed: int = Field(ge=0)
    urls_replaced: int = Field(ge=0)
    emails_replaced: int = Field(ge=0)


class PreprocessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_text: str
    clean_text: str
    tokens: tuple[str, ...]
    stats: ProcessingStats
    preprocessor_name: str
    preprocessor_version: str
