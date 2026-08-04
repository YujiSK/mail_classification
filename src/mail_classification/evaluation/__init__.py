"""Fold generation and Core experiment execution on the approved Full dataset."""

from .aggregate import METRICS_SUMMARY_FIELDS, build_metrics_summary
from .cv import FoldFitResult, run_core_cell, run_core_experiments
from .full_dataset import (
    approved_full_data_hash,
    load_verified_full_dataset,
    verify_full_dataset_hash,
)
from .ja_cv import FoldFitResult as JaFoldFitResult
from .ja_cv import run_core_cell as run_core_cell_ja
from .ja_cv import run_core_experiments as run_core_experiments_ja
from .ja_runner import run_and_write_core_experiments as run_and_write_core_experiments_ja
from .metrics import (
    CONFUSION_FIELDS,
    METRICS_LONG_FIELDS,
    build_confusion_matrix_rows,
    build_metrics_long,
)
from .paired import PAIRED_DIFFERENCE_FIELDS, build_paired_differences
from .runner import OOF_FIELDS, load_fold_artifact, run_and_write_core_experiments
from .splits import (
    audit_template_groups,
    build_common_folds,
    recommend_splitter_name,
    write_fold_artifact,
)

__all__ = [
    "CONFUSION_FIELDS",
    "METRICS_LONG_FIELDS",
    "METRICS_SUMMARY_FIELDS",
    "OOF_FIELDS",
    "PAIRED_DIFFERENCE_FIELDS",
    "FoldFitResult",
    "JaFoldFitResult",
    "approved_full_data_hash",
    "audit_template_groups",
    "build_common_folds",
    "build_confusion_matrix_rows",
    "build_metrics_long",
    "build_metrics_summary",
    "build_paired_differences",
    "load_fold_artifact",
    "load_verified_full_dataset",
    "recommend_splitter_name",
    "run_and_write_core_experiments",
    "run_and_write_core_experiments_ja",
    "run_core_cell",
    "run_core_cell_ja",
    "run_core_experiments",
    "run_core_experiments_ja",
    "verify_full_dataset_hash",
    "write_fold_artifact",
]
