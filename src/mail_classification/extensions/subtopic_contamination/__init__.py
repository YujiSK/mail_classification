"""Subtopic-contamination Extension: independent of Core, never imported by it.

Answers a question Core's Full dataset design does not address: does mixing
a clearly-secondary subtopic (a different class's vocabulary) into an
email's body, at increasing contamination rates, degrade classification of
the *primary* (unchanged) label, and does the model's prediction get pulled
toward the subtopic's class? See docs/management/execution_plan.md and the
assignment brief for the full specification.

Deliberately separate from Core: its own package, its own output directory
(outputs/extensions/, never outputs/runs/ or outputs/data_quality/), and its
own derived dataset files under data/derived/ that never overwrite
data/raw/full_emails.jsonl.
"""

from .assignment import (
    CONTAMINATION_FRACTIONS,
    CONTAMINATION_LEVELS,
    ContaminationAssignmentRow,
    build_contamination_assignment,
)
from .dataset import build_condition_records, write_condition_datasets
from .insertion import apply_contamination
from .sentences import SUBTOPIC_SENTENCES

__all__ = [
    "CONTAMINATION_FRACTIONS",
    "CONTAMINATION_LEVELS",
    "ContaminationAssignmentRow",
    "SUBTOPIC_SENTENCES",
    "apply_contamination",
    "build_condition_records",
    "build_contamination_assignment",
    "write_condition_datasets",
]
