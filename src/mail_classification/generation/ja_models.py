"""Japanese template catalog: adds `semantic_template_id` without touching
`generation/models.py`, so the hash-fixed English Full dataset stays
byte-identical (`docs/audits/task10_ja_reuse_matrix.md`). `GenerationConfig`,
`SharedComponents`, `StageConfig`, and `QualityThresholds` are reused as-is
by import; only the template/catalog models are subclassed to add the
English<->Japanese comparison key.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
import yaml

from mail_classification.schemas.common import require_nonblank

from .models import EmailTemplate, TemplateCatalog


class JapaneseEmailTemplate(EmailTemplate):
    """`EmailTemplate` plus a link to the English semantic-equivalent group.

    `semantic_template_id` names the English `template_group` (e.g. "tg001")
    this Japanese group was authored as a natural (not literal) translation
    of, per the shared 4-label/24-group/4-variation design fixed in
    `docs/audits/task10_ja_reuse_matrix.md`. It enables joining English and
    Japanese results by intent for the cross-language comparison chapter.
    """

    semantic_template_id: str

    _nonblank_semantic_id = field_validator("semantic_template_id")(require_nonblank)


class JapaneseTemplateCatalog(TemplateCatalog):
    templates: list[JapaneseEmailTemplate] = Field(min_length=1)

    @field_validator("templates")
    @classmethod
    def validate_semantic_ids_are_english_groups(
        cls, templates: list[JapaneseEmailTemplate]
    ) -> list[JapaneseEmailTemplate]:
        expected = {f"tg{index:03d}" for index in range(1, 25)}
        found = {template.semantic_template_id for template in templates}
        missing = expected - found
        if missing:
            raise ValueError(
                "semantic_template_id values do not cover all 24 English "
                f"groups; missing: {sorted(missing)}"
            )
        return templates


def load_ja_template_catalog(path: str | Path) -> JapaneseTemplateCatalog:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return JapaneseTemplateCatalog.model_validate(payload)
