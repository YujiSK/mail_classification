"""Deterministic, nested, balanced selection of samples to contaminate.

Design (seed=42, fixed):

1. Per main label (4 classes, 200 records each), records are grouped by
   ``template_group`` (6 groups/class, each group a single fixed
   ``difficulty`` in the Full dataset -- verified in ``dataset.py`` tests).
   Groups are ordered so consecutive groups alternate difficulty, then
   visited round-robin (one record per group per round, each group's
   internal order seeded-shuffled) to build a priority-ordered list whose
   every prefix is close to balanced across both ``template_group`` and
   ``difficulty`` -- not just the final 60-record prefix.
2. The first ``round(0.30 * 200) = 60`` records of that ordered list are the
   class's C30 contamination pool. The first 20 are the C10 pool, the first
   40 the C20 pool: C10 subset(C20) subset(C30), satisfying the nested
   ("paired") design the assignment requires.
3. Each selected record is paired with one of the other three labels as its
   subtopic, drawn from a round-robin-shuffled sequence (every full round of
   3 draws touches all three subtopics once) so subtopic pairs stay close to
   evenly split at every nesting level, not only at C30.
4. Each (record, subtopic) pair gets one of the subtopic's 12 sentence
   variants and one of the 3 insertion positions, both drawn from their own
   round-robin-shuffled sequences (seeded per class+subtopic) so variant and
   position usage stay close to even.

Every random draw uses ``random.Random`` seeded from a deterministic string
key built from ``seed`` plus the relevant class/group/subtopic identifiers,
so re-running with the same ``seed`` and the same input records reproduces
byte-identical assignments.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import random

from mail_classification.schemas import RawMailRecord

from .insertion import INSERTION_POSITIONS
from .sentences import SENTENCES_PER_SUBTOPIC, SUBTOPIC_SENTENCES

CONTAMINATION_LEVELS = ("C0", "C10", "C20", "C30")
CONTAMINATION_FRACTIONS: dict[str, float] = {"C0": 0.0, "C10": 0.10, "C20": 0.20, "C30": 0.30}

ASSIGNMENT_FIELDS = [
    "sample_id",
    "main_label",
    "subtopic_label",
    "template_group",
    "difficulty",
    "selection_rank",
    "min_level",
    "variant_id",
    "style",
    "sentence_text",
    "insertion_position",
]


@dataclass(frozen=True)
class ContaminationAssignmentRow:
    sample_id: str
    main_label: str
    subtopic_label: str
    template_group: str
    difficulty: str
    selection_rank: int
    min_level: str  # first CONTAMINATION_LEVELS entry at which this sample is contaminated
    variant_id: int
    style: str
    sentence_text: str
    insertion_position: str

    def applies_at(self, level: str) -> bool:
        if level == "C0":
            return False
        return CONTAMINATION_LEVELS.index(level) >= CONTAMINATION_LEVELS.index(self.min_level)

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "main_label": self.main_label,
            "subtopic_label": self.subtopic_label,
            "template_group": self.template_group,
            "difficulty": self.difficulty,
            "selection_rank": self.selection_rank,
            "min_level": self.min_level,
            "variant_id": self.variant_id,
            "style": self.style,
            "sentence_text": self.sentence_text,
            "insertion_position": self.insertion_position,
        }


def _template_group_interleaved_order(
    class_records: list[RawMailRecord], seed: int, main_label: str
) -> list[RawMailRecord]:
    groups: dict[str, list[RawMailRecord]] = defaultdict(list)
    for record in class_records:
        groups[record.template_group].append(record)

    by_difficulty: dict[str, list[str]] = defaultdict(list)
    for group_id in sorted(groups):
        difficulty = groups[group_id][0].difficulty.value
        by_difficulty[difficulty].append(group_id)

    max_occurrence = max(len(group_ids) for group_ids in by_difficulty.values())
    ordered_groups: list[str] = []
    for occurrence in range(max_occurrence):
        for difficulty in sorted(by_difficulty):
            if occurrence < len(by_difficulty[difficulty]):
                ordered_groups.append(by_difficulty[difficulty][occurrence])

    shuffled_by_group: dict[str, list[RawMailRecord]] = {}
    for group_id in ordered_groups:
        records = sorted(groups[group_id], key=lambda r: r.id)
        random.Random(f"{seed}|{main_label}|group|{group_id}").shuffle(records)
        shuffled_by_group[group_id] = records

    ordered: list[RawMailRecord] = []
    indices = {group_id: 0 for group_id in ordered_groups}
    progressed = True
    while progressed:
        progressed = False
        for group_id in ordered_groups:
            index = indices[group_id]
            if index < len(shuffled_by_group[group_id]):
                ordered.append(shuffled_by_group[group_id][index])
                indices[group_id] += 1
                progressed = True
    return ordered


def _round_robin_shuffled_sequence(items: list[str], n: int, seed: str) -> list[str]:
    rng = random.Random(seed)
    sequence: list[str] = []
    while len(sequence) < n:
        round_items = list(items)
        rng.shuffle(round_items)
        sequence.extend(round_items)
    return sequence[:n]


def build_contamination_assignment(
    records: list[RawMailRecord], *, seed: int = 42
) -> list[ContaminationAssignmentRow]:
    """Deterministically select and describe contamination for up to 30%/class.

    Every sample selected at C10 is also selected at C20 and C30 (nested).
    Never mutates ``records``; callers apply the sentence text separately
    (``dataset.py``) so this function stays a pure planning step that is
    itself trivial to audit (``contamination_assignment.csv``).
    """
    labels = sorted({record.label.value for record in records})
    if len(labels) < 2:
        raise ValueError("contamination assignment requires at least 2 distinct labels")

    rows: list[ContaminationAssignmentRow] = []
    for main_label in labels:
        class_records = [record for record in records if record.label.value == main_label]
        class_size = len(class_records)
        c10_count = round(class_size * CONTAMINATION_FRACTIONS["C10"])
        c20_count = round(class_size * CONTAMINATION_FRACTIONS["C20"])
        c30_count = round(class_size * CONTAMINATION_FRACTIONS["C30"])

        ordered = _template_group_interleaved_order(class_records, seed, main_label)
        selected = ordered[:c30_count]

        other_labels = [label for label in labels if label != main_label]
        subtopic_sequence = _round_robin_shuffled_sequence(
            other_labels, len(selected), f"{seed}|{main_label}|subtopic"
        )

        variant_sequences: dict[str, list[int]] = {
            subtopic: [
                int(value)
                for value in _round_robin_shuffled_sequence(
                    [str(i) for i in range(SENTENCES_PER_SUBTOPIC)],
                    c30_count,
                    f"{seed}|{main_label}|{subtopic}|variant",
                )
            ]
            for subtopic in other_labels
        }
        position_sequences: dict[str, list[str]] = {
            subtopic: _round_robin_shuffled_sequence(
                list(INSERTION_POSITIONS),
                c30_count,
                f"{seed}|{main_label}|{subtopic}|position",
            )
            for subtopic in other_labels
        }
        subtopic_draw_counts: dict[str, int] = {subtopic: 0 for subtopic in other_labels}

        for rank, record in enumerate(selected):
            subtopic = subtopic_sequence[rank]
            draw_index = subtopic_draw_counts[subtopic]
            subtopic_draw_counts[subtopic] += 1

            variant_id = variant_sequences[subtopic][draw_index]
            position = position_sequences[subtopic][draw_index]
            sentence = SUBTOPIC_SENTENCES[subtopic][variant_id]

            min_level = "C10" if rank < c10_count else "C20" if rank < c20_count else "C30"

            rows.append(
                ContaminationAssignmentRow(
                    sample_id=record.id,
                    main_label=main_label,
                    subtopic_label=subtopic,
                    template_group=record.template_group,
                    difficulty=record.difficulty.value,
                    selection_rank=rank,
                    min_level=min_level,
                    variant_id=variant_id,
                    style=sentence.style,
                    sentence_text=sentence.text,
                    insertion_position=position,
                )
            )
    rows.sort(key=lambda row: row.sample_id)
    return rows
