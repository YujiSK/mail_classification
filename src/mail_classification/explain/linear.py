"""Class coefficients from fitted Core Pipelines, and a structural-artifact re-audit.

Fold coefficients are extracted by refitting each fold's condition Pipeline
on that fold's exact train split (Phase 4's runner does not persist fitted
Pipeline objects, only OOF predictions and metrics). ``coefficient`` and
``feature`` in every row come from the same fitted Pipeline, satisfying the
Phase 5 validation requirement in docs/management/execution_plan.md.

``extract_descriptive_full_fit_coefficients`` fits on the entire dataset and
is a structurally separate function with its own output schema/file, so it
can never be mistaken for a Fold-evaluated result (project_rules.md: never
conflate a full-data fit with Fold-based performance).
"""

from __future__ import annotations

from mail_classification.models import apply_condition_preprocessing, build_condition_pipeline
from mail_classification.schemas import FoldArtifact, FoldRole, RawMailRecord

DEFAULT_TOP_N = 15

COEFFICIENT_FIELDS = [
    "condition",
    "model",
    "fold_id",
    "label",
    "rank_type",
    "rank",
    "feature",
    "coefficient",
]
DESCRIPTIVE_COEFFICIENT_FIELDS = [
    "condition",
    "model",
    "label",
    "rank_type",
    "rank",
    "feature",
    "coefficient",
]

# Header/signature/URL/email tokens a leakage-free intent classifier should
# not need. `<URL>`/`<EMAIL>` placeholders survive TF-IDF's default tokenizer
# as bare "url"/"email" (angle brackets are not word characters).
STRUCTURAL_ARTIFACT_TOKENS = frozenset(
    {"subject", "from", "sent", "cc", "bcc", "url", "email", "wrote"}
)


def _top_rows(
    base: dict[str, object],
    classes,
    coef,
    feature_names,
    top_n: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for class_index, label in enumerate(classes):
        class_coef = coef[class_index]
        order_desc = sorted(
            range(len(class_coef)), key=lambda i: class_coef[i], reverse=True
        )
        order_asc = sorted(range(len(class_coef)), key=lambda i: class_coef[i])
        order_abs = sorted(
            range(len(class_coef)), key=lambda i: abs(class_coef[i]), reverse=True
        )
        for rank_type, order in (
            ("top_positive", order_desc),
            ("top_negative", order_asc),
            ("top_absolute", order_abs),
        ):
            for rank, feature_index in enumerate(order[:top_n], start=1):
                rows.append(
                    {
                        **base,
                        "label": label,
                        "rank_type": rank_type,
                        "rank": rank,
                        "feature": feature_names[feature_index],
                        "coefficient": float(class_coef[feature_index]),
                    }
                )
    return rows


def extract_fold_coefficients(
    records: list[RawMailRecord],
    fold_artifact: FoldArtifact,
    condition_name: str,
    model_name: str,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[dict[str, object]]:
    """Per-fold, per-class top positive/negative/absolute coefficients."""
    records_by_id = {record.id: record for record in records}
    preprocessed_by_id = dict(
        zip(
            (record.id for record in records),
            apply_condition_preprocessing(
                condition_name, [record.raw_text for record in records]
            ),
        )
    )

    rows: list[dict[str, object]] = []
    for fold_id in range(fold_artifact.metadata.n_splits):
        fold_rows = [row for row in fold_artifact.records if row.fold_id == fold_id]
        train_ids = [
            row.sample_id for row in fold_rows if row.split_role is FoldRole.TRAIN
        ]

        pipeline = build_condition_pipeline(condition_name, model_name)
        x_train = [preprocessed_by_id[sample_id] for sample_id in train_ids]
        y_train = [records_by_id[sample_id].label.value for sample_id in train_ids]
        pipeline.fit(x_train, y_train)

        classifier = pipeline.named_steps["clf"]
        feature_names = pipeline.named_steps["tfidf"].get_feature_names_out()
        base = {"condition": condition_name, "model": model_name, "fold_id": fold_id}
        rows.extend(
            _top_rows(base, classifier.classes_, classifier.coef_, feature_names, top_n)
        )
    return rows


def extract_descriptive_full_fit_coefficients(
    records: list[RawMailRecord],
    condition_name: str,
    model_name: str,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> list[dict[str, object]]:
    """Fit on the ENTIRE dataset for description only; never a performance claim."""
    preprocessed = apply_condition_preprocessing(
        condition_name, [record.raw_text for record in records]
    )
    labels = [record.label.value for record in records]

    pipeline = build_condition_pipeline(condition_name, model_name)
    pipeline.fit(preprocessed, labels)

    classifier = pipeline.named_steps["clf"]
    feature_names = pipeline.named_steps["tfidf"].get_feature_names_out()
    base = {"condition": condition_name, "model": model_name}
    return _top_rows(base, classifier.classes_, classifier.coef_, feature_names, top_n)


def audit_top_features_for_structural_artifacts(
    coefficient_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Flag top coefficients whose feature is a known header/URL/email artifact token."""
    return [
        row
        for row in coefficient_rows
        if str(row["feature"]).casefold() in STRUCTURAL_ARTIFACT_TOKENS
    ]
