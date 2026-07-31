"""Deterministic synthetic-mail generation."""

from .generator import SyntheticMailGenerator
from .models import GenerationConfig, TemplateCatalog, load_generation_config
from .pipeline import StageResult, run_generation_stage
from .templates import load_template_catalog

__all__ = [
    "GenerationConfig",
    "StageResult",
    "SyntheticMailGenerator",
    "TemplateCatalog",
    "load_generation_config",
    "load_template_catalog",
    "run_generation_stage",
]
