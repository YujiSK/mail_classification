"""Deterministic synthetic-mail generation."""

from .generator import SyntheticMailGenerator
from .ja_generator import JapaneseSyntheticMailGenerator
from .ja_models import JapaneseEmailTemplate, JapaneseTemplateCatalog, load_ja_template_catalog
from .ja_pipeline import JaStageResult, run_ja_generation_stage
from .models import GenerationConfig, TemplateCatalog, load_generation_config
from .pipeline import StageResult, run_generation_stage
from .templates import load_template_catalog

__all__ = [
    "GenerationConfig",
    "JaStageResult",
    "JapaneseEmailTemplate",
    "JapaneseSyntheticMailGenerator",
    "JapaneseTemplateCatalog",
    "StageResult",
    "SyntheticMailGenerator",
    "TemplateCatalog",
    "load_generation_config",
    "load_ja_template_catalog",
    "load_template_catalog",
    "run_generation_stage",
    "run_ja_generation_stage",
]
