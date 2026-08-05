"""Materialize the four (C0/C10/C20/C30) derived datasets from one assignment.

C0 is defined as *identical* to the approved Full dataset (same records, same
bytes) -- it is never regenerated or re-templated, only re-emitted, so a
byte-for-byte comparison against ``data/raw/full_emails.jsonl`` is a valid
regression check. C10/C20/C30 apply exactly the sentence text the assignment
already fixed for each selected sample; nothing here draws new randomness.

Contamination provenance (``subtopic_label``, ``contamination_level``,
``insertion_position``, ``sentence_variant_id``, ``style``) is recorded under
``metadata["subtopic_contamination"]`` for traceability, but every Core
Pipeline (``mail_classification.models.build_condition_pipeline`` via
``apply_condition_preprocessing``) only ever reads ``record.raw_text`` --
metadata is inert with respect to model input, verified by
``tests/test_subtopic_contamination_dataset.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mail_classification.generation.io import write_csv, write_json, write_jsonl
from mail_classification.schemas import RawMailRecord

from .assignment import ASSIGNMENT_FIELDS, CONTAMINATION_LEVELS, ContaminationAssignmentRow
from .insertion import apply_contamination

CONTAMINATION_METADATA_KEY = "subtopic_contamination"


def build_condition_records(
    full_records: list[RawMailRecord],
    assignment: list[ContaminationAssignmentRow],
    level: str,
) -> list[RawMailRecord]:
    """Return one record per input record: contaminated text for selected samples at `level`."""
    if level not in CONTAMINATION_LEVELS:
        raise ValueError(f"unknown contamination level {level!r}; expected one of {CONTAMINATION_LEVELS}")

    assignment_by_id = {row.sample_id: row for row in assignment}
    records: list[RawMailRecord] = []
    for record in full_records:
        row = assignment_by_id.get(record.id)
        if row is None or not row.applies_at(level):
            records.append(record)
            continue

        new_raw_text, new_body_text = apply_contamination(record, row.sentence_text, row.insertion_position)
        new_metadata = dict(record.metadata)
        new_metadata[CONTAMINATION_METADATA_KEY] = {
            "contamination_level": level,
            "subtopic_label": row.subtopic_label,
            "insertion_position": row.insertion_position,
            "sentence_variant_id": row.variant_id,
            "style": row.style,
        }
        records.append(
            record.model_copy(
                update={"raw_text": new_raw_text, "body_text": new_body_text, "metadata": new_metadata}
            )
        )
    return records


@dataclass(frozen=True)
class ConditionDatasetPaths:
    level: str
    data_path: Path
    data_hash: str
    contaminated_count: int


def write_condition_datasets(
    full_records: list[RawMailRecord],
    assignment: list[ContaminationAssignmentRow],
    project_root: str | Path,
    *,
    run_id: str,
    output_dir: str | Path,
    seed: int = 42,
) -> tuple[list[ConditionDatasetPaths], Path]:
    """Write full_emails_<level>.jsonl under data/derived/, assignment CSV + manifest under `output_dir`.

    The bulk regenerable JSONL datasets follow project_rules.md's
    ``data/derived/`` convention; ``contamination_assignment.csv`` and
    ``dataset_manifest.json`` are written into the Extension's own
    ``outputs/extensions/<run_id>/`` directory (the assignment brief's
    required-artifact list), not duplicated in both places.
    """
    project_root = Path(project_root).resolve()
    derived_dir = project_root / "data" / "derived" / "subtopic_contamination" / run_id
    output_dir = Path(output_dir)

    results: list[ConditionDatasetPaths] = []
    for level in CONTAMINATION_LEVELS:
        level_records = build_condition_records(full_records, assignment, level)
        data_path = derived_dir / f"full_emails_{level}.jsonl"
        data_hash = write_jsonl(data_path, level_records)
        contaminated_count = sum(
            1
            for row in assignment
            if row.applies_at(level)
        )
        results.append(
            ConditionDatasetPaths(
                level=level, data_path=data_path, data_hash=data_hash, contaminated_count=contaminated_count
            )
        )

    assignment_path = output_dir / "contamination_assignment.csv"
    write_csv(assignment_path, [row.as_dict() for row in assignment], ASSIGNMENT_FIELDS)

    manifest_path = output_dir / "dataset_manifest.json"
    write_json(
        manifest_path,
        {
            "run_id": run_id,
            "seed": seed,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "base_record_count": len(full_records),
            "assignment_row_count": len(assignment),
            "levels": {
                result.level: {
                    "data_path": str(result.data_path.relative_to(project_root)),
                    "data_hash": result.data_hash,
                    "contaminated_count": result.contaminated_count,
                    "contaminated_ratio": result.contaminated_count / len(full_records),
                }
                for result in results
            },
        },
    )
    return results, manifest_path
