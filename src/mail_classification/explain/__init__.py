"""Class coefficients and OOF misclassification/error-taxonomy analysis."""

from .errors import (
    ERROR_CATEGORY_SUMMARY_FIELDS,
    MISCLASSIFICATION_FIELDS,
    build_misclassification_rows,
    summarize_error_categories,
)
from .evidence import DECISION_SCORE_FIELDS, EVIDENCE_FIELDS, enrich_misclassifications_with_evidence
from .ja_errors import (
    ERROR_CATEGORY_COUNTS_FIELDS,
    MISCLASSIFICATION_FIELDS as MISCLASSIFICATION_FIELDS_JA,
    build_misclassification_rows_ja,
    summarize_error_categories as summarize_error_categories_ja,
    summarize_error_category_counts,
)
from .ja_evidence import (
    DECISION_SCORE_FIELDS as DECISION_SCORE_FIELDS_JA,
    EVIDENCE_FIELDS as EVIDENCE_FIELDS_JA,
    enrich_misclassifications_with_evidence as enrich_misclassifications_with_evidence_ja,
)
from .ja_linear import (
    COEFFICIENT_FIELDS as COEFFICIENT_FIELDS_JA,
    DESCRIPTIVE_COEFFICIENT_FIELDS as DESCRIPTIVE_COEFFICIENT_FIELDS_JA,
    STRUCTURAL_ARTIFACT_TOKENS as STRUCTURAL_ARTIFACT_TOKENS_JA,
    audit_top_features_for_structural_artifacts as audit_top_features_for_structural_artifacts_ja,
    extract_descriptive_full_fit_coefficients as extract_descriptive_full_fit_coefficients_ja,
    extract_fold_coefficients as extract_fold_coefficients_ja,
)
from .ja_runner import (
    read_oof_predictions as read_oof_predictions_ja,
    run_and_write_explainability as run_and_write_explainability_ja,
)
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
    "COEFFICIENT_FIELDS_JA",
    "DECISION_SCORE_FIELDS",
    "DECISION_SCORE_FIELDS_JA",
    "DESCRIPTIVE_COEFFICIENT_FIELDS",
    "DESCRIPTIVE_COEFFICIENT_FIELDS_JA",
    "ERROR_CATEGORY_COUNTS_FIELDS",
    "ERROR_CATEGORY_SUMMARY_FIELDS",
    "EVIDENCE_FIELDS",
    "EVIDENCE_FIELDS_JA",
    "MISCLASSIFICATION_FIELDS",
    "MISCLASSIFICATION_FIELDS_JA",
    "STRUCTURAL_ARTIFACT_TOKENS",
    "STRUCTURAL_ARTIFACT_TOKENS_JA",
    "audit_top_features_for_structural_artifacts",
    "audit_top_features_for_structural_artifacts_ja",
    "build_misclassification_rows",
    "build_misclassification_rows_ja",
    "enrich_misclassifications_with_evidence",
    "enrich_misclassifications_with_evidence_ja",
    "extract_descriptive_full_fit_coefficients",
    "extract_descriptive_full_fit_coefficients_ja",
    "extract_fold_coefficients",
    "extract_fold_coefficients_ja",
    "read_oof_predictions",
    "read_oof_predictions_ja",
    "run_and_write_explainability",
    "run_and_write_explainability_ja",
    "summarize_error_categories",
    "summarize_error_categories_ja",
    "summarize_error_category_counts",
]
