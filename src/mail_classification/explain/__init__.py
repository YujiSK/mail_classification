"""Class coefficients and OOF misclassification/error-taxonomy analysis."""

from .errors import (
    ERROR_CATEGORY_SUMMARY_FIELDS,
    MISCLASSIFICATION_FIELDS,
    build_misclassification_rows,
    summarize_error_categories,
)
from .evidence import DECISION_SCORE_FIELDS, EVIDENCE_FIELDS, enrich_misclassifications_with_evidence
from .linear import (
    COEFFICIENT_FIELDS,
    DESCRIPTIVE_COEFFICIENT_FIELDS,
    STRUCTURAL_ARTIFACT_TOKENS,
    audit_top_features_for_structural_artifacts,
    extract_descriptive_full_fit_coefficients,
    extract_fold_coefficients,
)
from .runner import read_oof_predictions, run_and_write_explainability

__all__ = [
    "COEFFICIENT_FIELDS",
    "DECISION_SCORE_FIELDS",
    "DESCRIPTIVE_COEFFICIENT_FIELDS",
    "ERROR_CATEGORY_SUMMARY_FIELDS",
    "EVIDENCE_FIELDS",
    "MISCLASSIFICATION_FIELDS",
    "STRUCTURAL_ARTIFACT_TOKENS",
    "audit_top_features_for_structural_artifacts",
    "build_misclassification_rows",
    "enrich_misclassifications_with_evidence",
    "extract_descriptive_full_fit_coefficients",
    "extract_fold_coefficients",
    "read_oof_predictions",
    "run_and_write_explainability",
    "summarize_error_categories",
]
