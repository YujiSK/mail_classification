"""Template loading kept separate from generation orchestration."""

from pathlib import Path

import yaml

from .models import TemplateCatalog


def load_template_catalog(path: str | Path) -> TemplateCatalog:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return TemplateCatalog.model_validate(payload)
