"""Seeded composition of reviewed templates and label-neutral components."""

from __future__ import annotations

from collections import defaultdict
import random

from mail_classification.schemas import MailLabel, RawMailRecord

from .models import EmailTemplate, GenerationConfig, TemplateCatalog

NEGATIONS = ("not", "no", "never", "without", "cannot", "can't", "don't")


class SyntheticMailGenerator:
    def __init__(self, config: GenerationConfig, catalog: TemplateCatalog) -> None:
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
        candidates = [
            (template, variation_id)
            for template in self.catalog.templates
            for variation_id in range(self.config.generator.variations_per_template)
        ]
        if stage == "smoke":
            by_label: dict[MailLabel, list[tuple[EmailTemplate, int]]] = defaultdict(
                list
            )
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
        else:
            if stage_config.count > len(candidates):
                raise ValueError(
                    "requested count exceeds unique template variations; "
                    "do not create duplicate records"
                )
            rng.shuffle(candidates)
            candidates = candidates[: stage_config.count]

        label_positions: dict[MailLabel, int] = defaultdict(int)
        records = []
        for position, (template, variation_id) in enumerate(candidates, start=1):
            label_position = label_positions[template.label]
            records.append(
                self._compose(
                    stage,
                    position,
                    template,
                    variation_id,
                    label_position,
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
        template: EmailTemplate,
        variation_id: int,
        label_position: int,
        rng: random.Random,
    ) -> RawMailRecord:
        shared = self.catalog.shared
        greeting_index = rng.randrange(len(shared.greetings))
        closing_index = rng.randrange(len(shared.closings))
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
                        f"From: {shared.senders[sender_index]}",
                        "To: help@example.invalid",
                        f"Subject: {shared.subjects[subject_index]}",
                    ]
                )
            )
        raw_sections.append(body_text)
        if has_signature:
            raw_sections.append("\n".join(shared.signatures[signature_index]))
        if has_quoted_reply:
            raw_sections.append(
                "On Tuesday, Support wrote:\n"
                + "\n".join(shared.quoted_replies[quote_index])
            )
        raw_text = "\n\n".join(raw_sections)
        folded = raw_text.casefold()

        return RawMailRecord(
            id=f"syn-{stage}-{position:04d}",
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
            metadata={
                "generator_version": self.config.generator.version,
                "multi_intent": template.multi_intent,
                "secondary_intent": template.secondary_intent,
                "contains_negation": any(
                    negation in folded for negation in NEGATIONS
                ),
                "component_indices": {
                    "greeting": greeting_index,
                    "closing": closing_index,
                    "sender": sender_index,
                    "subject": subject_index,
                    "signature": signature_index if has_signature else None,
                    "quoted_reply": quote_index if has_quoted_reply else None,
                    "urgency": urgency_index,
                },
            },
        )
