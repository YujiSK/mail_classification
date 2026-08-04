"""Japanese counterpart of ``generator.py``.

Orchestration logic (candidate selection for smoke/pilot/full, component
seeding, deterministic ID assignment) is copied rather than imported from
``generator.py`` because the English module hardcodes three English-specific
literals inline in ``_compose`` (the ``From:``/``To:``/``Subject:`` header
block, the ``"On {day}, Support wrote:"`` reply lead-in, and the English
``NEGATIONS`` substring tuple used for the ``contains_negation`` metadata
flag). Forking avoids touching the hash-fixed English generation path
(``docs/audits/task10_ja_reuse_matrix.md``) while keeping every other part
of the algorithm identical, including the Full 200/50/33-34/67-67-66
allocation math in ``_full_candidates``.
"""

from __future__ import annotations

from collections import defaultdict
import random

from mail_classification.schemas import MailLabel, RawMailRecord

from .ja_models import JapaneseEmailTemplate, JapaneseTemplateCatalog
from .models import GenerationConfig

# Simple substring detection, matching the English generator's own
# simplicity (a folded-text membership check, not a morphological
# analysis). Documented as a first-cut limitation in
# docs/audits/task10_ja_reuse_matrix.md and
# docs/contracts/preprocessing_contract_ja.md; a Sudachi-POS-based detector
# is a Phase JA-5+ improvement candidate, not implemented here so that this
# metadata flag stays as cheap and dependency-light as its English sibling.
NEGATIONS = ("ない", "ません", "ず", "ぬ", "できない", "できません", "無い")


class JapaneseSyntheticMailGenerator:
    def __init__(
        self, config: GenerationConfig, catalog: JapaneseTemplateCatalog
    ) -> None:
        self.config = config
        self.catalog = catalog
        expected = config.generator.variations_per_template
        if any(len(template.contexts) != expected for template in catalog.templates):
            raise ValueError("every template must match variations_per_template")
        counts = defaultdict(int)
        for template in catalog.templates:
            counts[template.label] += 1
        missing = set(MailLabel) - set(counts)
        if missing:
            raise ValueError(f"templates missing labels: {sorted(item.value for item in missing)}")
        if any(
            count < config.quality.min_template_groups_per_label
            for count in counts.values()
        ):
            raise ValueError("each label needs the configured minimum template groups")

    def generate(self, stage: str) -> list[RawMailRecord]:
        if stage not in self.config.stages:
            raise ValueError(f"unknown generation stage: {stage}")
        stage_config = self.config.stages[stage]
        if not stage_config.enabled:
            raise ValueError(f"generation stage is disabled: {stage}")

        rng = random.Random(self.config.generator.seed)
        candidates: list[tuple[JapaneseEmailTemplate, int, int | None]] = [
            (template, variation_id, None)
            for template in self.catalog.templates
            for variation_id in range(self.config.generator.variations_per_template)
        ]
        if stage == "smoke":
            by_label: dict[
                MailLabel, list[tuple[JapaneseEmailTemplate, int, int | None]]
            ] = defaultdict(list)
            for candidate in candidates:
                by_label[candidate[0].label].append(candidate)
            selected = []
            per_label = stage_config.count // len(MailLabel)
            remainder = stage_config.count % len(MailLabel)
            for offset, label in enumerate(MailLabel):
                pool = by_label[label][:]
                rng.shuffle(pool)
                selected.extend(pool[: per_label + (offset < remainder)])
            candidates = selected
        elif stage == "pilot":
            if stage_config.count > len(candidates):
                raise ValueError(
                    "requested count exceeds unique template variations; "
                    "do not create duplicate records"
                )
            rng.shuffle(candidates)
            candidates = candidates[: stage_config.count]
        else:
            candidates = self._full_candidates(stage_config.count)
            rng.shuffle(candidates)

        label_positions: dict[MailLabel, int] = defaultdict(int)
        records = []
        for position, (template, variation_id, surface_serial) in enumerate(
            candidates, start=1
        ):
            label_position = label_positions[template.label]
            records.append(
                self._compose(
                    stage,
                    position,
                    template,
                    variation_id,
                    label_position,
                    surface_serial,
                    rng,
                )
            )
            label_positions[template.label] += 1
        if len({record.id for record in records}) != len(records):
            raise RuntimeError("generated IDs are not unique")
        return records

    def _compose(
        self,
        stage: str,
        position: int,
        template: JapaneseEmailTemplate,
        variation_id: int,
        label_position: int,
        surface_serial: int | None,
        rng: random.Random,
    ) -> RawMailRecord:
        shared = self.catalog.shared
        if surface_serial is None:
            greeting_index = rng.randrange(len(shared.greetings))
            closing_index = rng.randrange(len(shared.closings))
        else:
            surface_cycle = (
                surface_serial // self.config.generator.variations_per_template
            )
            greeting_index = surface_cycle % len(shared.greetings)
            closing_index = (
                surface_cycle // len(shared.greetings) + variation_id
            ) % len(shared.closings)
        sender_index = rng.randrange(len(shared.senders))
        subject_index = rng.randrange(len(shared.subjects))
        signature_index = rng.randrange(len(shared.signatures))
        quote_index = rng.randrange(len(shared.quoted_replies))

        has_header = rng.random() < 0.55
        has_signature = rng.random() < 0.55
        has_quoted_reply = rng.random() < 0.35
        urgency_index = label_position % len(shared.urgency_lines)
        urgency = shared.urgency_lines[urgency_index]
        body_lines = [
            shared.greetings[greeting_index],
            "",
            template.contexts[variation_id],
            template.main_requests[variation_id],
            template.secondary_details[variation_id],
        ]
        if urgency:
            body_lines.append(urgency)
        body_lines.extend(["", shared.closings[closing_index]])
        body_text = "\n".join(body_lines)

        raw_sections: list[str] = []
        if has_header:
            raw_sections.append(
                "\n".join(
                    [
                        f"差出人: {shared.senders[sender_index]}",
                        "宛先: help@example.invalid",
                        f"件名: {shared.subjects[subject_index]}",
                    ]
                )
            )
        raw_sections.append(body_text)
        if has_signature:
            raw_sections.append("\n".join(shared.signatures[signature_index]))
        if has_quoted_reply:
            raw_sections.append(
                "サポートが次のように書きました:\n"
                + "\n".join(shared.quoted_replies[quote_index])
            )
        raw_text = "\n\n".join(raw_sections)
        folded = raw_text.casefold()

        metadata = {
            "generator_version": (
                self.config.generator.full_version
                if surface_serial is not None
                else self.config.generator.version
            ),
            "multi_intent": template.multi_intent,
            "secondary_intent": template.secondary_intent,
            "contains_negation": any(negation in folded for negation in NEGATIONS),
            "semantic_template_id": template.semantic_template_id,
            "component_indices": {
                "greeting": greeting_index,
                "closing": closing_index,
                "sender": sender_index,
                "subject": subject_index,
                "signature": signature_index if has_signature else None,
                "quoted_reply": quote_index if has_quoted_reply else None,
                "urgency": urgency_index,
            },
        }
        if surface_serial is not None:
            metadata["template_instance"] = surface_serial

        return RawMailRecord(
            id=f"syn-ja-{stage}-{position:04d}",
            raw_text=raw_text,
            body_text=body_text,
            label=template.label,
            template_group=template.template_group,
            difficulty=template.difficulty,
            has_header=has_header,
            has_signature=has_signature,
            has_quoted_reply=has_quoted_reply,
            generation_seed=self.config.generator.seed,
            template_id=template.template_id,
            variation_id=variation_id,
            generated_at=self.config.generator.deterministic_generated_at,
            metadata=metadata,
        )

    def _full_candidates(
        self, count: int
    ) -> list[tuple[JapaneseEmailTemplate, int, int]]:
        labels = list(MailLabel)
        difficulties = list(self.config.quality.required_difficulties)
        if count % len(labels):
            raise ValueError("full count must divide evenly across labels")
        per_label = count // len(labels)
        if per_label != 200 or len(difficulties) != 3:
            raise ValueError("full allocation requires 200 records and 3 difficulties")

        candidates: list[tuple[JapaneseEmailTemplate, int, int]] = []
        for label_index, label in enumerate(labels):
            low_difficulty = difficulties[label_index % len(difficulties)]
            for difficulty_index, difficulty in enumerate(difficulties):
                templates = [
                    template
                    for template in self.catalog.templates
                    if template.label == label and template.difficulty == difficulty
                ]
                if len(templates) != 2:
                    raise ValueError(
                        "full allocation requires two template groups per "
                        f"label/difficulty: {label.value}/{difficulty.value}"
                    )
                difficulty_count = 66 if difficulty == low_difficulty else 67
                group_counts = [difficulty_count // 2] * 2
                if difficulty_count % 2:
                    group_counts[(label_index + difficulty_index) % 2] += 1
                for template, group_count in zip(
                    templates, group_counts, strict=True
                ):
                    candidates.extend(
                        (
                            template,
                            serial % self.config.generator.variations_per_template,
                            serial,
                        )
                        for serial in range(group_count)
                    )
        if len(candidates) != count:
            raise RuntimeError("full allocation did not produce the requested count")
        return candidates
