"""Per-sample decision scores and contributing features for OOF misclassifications.

Refits each fold's condition Pipeline one more time (same train split Phase 4
evaluated on; Phase 4 did not persist decision scores), purely to explain,
for each already-known misclassification, its per-class decision scores and
which TF-IDF features drove the (wrong) predicted class vs the (correct)
true class. ``true_label``/``predicted_label`` are never recomputed here —
they come from the caller's authoritative OOF-derived misclassification rows;
this module only adds explanatory evidence alongside them.
"""

from __future__ import annotations

from collections import defaultdict

from mail_classification.models import apply_condition_preprocessing, build_condition_pipeline
from mail_classification.schemas import FoldArtifact, FoldRole, MailLabel, RawMailRecord

DECISION_SCORE_FIELDS = [f"decision_score_{label.value}" for label in MailLabel]
EVIDENCE_FIELDS = [*DECISION_SCORE_FIELDS, "predicted_top_features", "true_top_features"]


def _top_contributing_features(row_vector, coef_row, feature_names, top_n: int) -> str:
    """Linear contribution of each nonzero feature toward one class's score."""
    _, nonzero_indices = row_vector.nonzero()
    contributions = [
        (feature_names[index], float(row_vector[0, index] * coef_row[index]))
        for index in nonzero_indices
    ]
    contributions.sort(key=lambda item: item[1], reverse=True)
    return "; ".join(f"{name}:{value:.4f}" for name, value in contributions[:top_n])


def enrich_misclassifications_with_evidence(
    misclassification_rows: list[dict[str, object]],
    records: list[RawMailRecord],
    fold_artifact: FoldArtifact,
    *,
    top_n: int = 5,
) -> list[dict[str, object]]:
    """Return new row dicts: each input row plus decision scores and top features."""
    if not misclassification_rows:
        return []

    records_by_id = {record.id: record for record in records}
    rows_by_cell_and_sample: dict[tuple[str, str], dict[str, dict[str, object]]] = (
        defaultdict(dict)
    )
    for row in misclassification_rows:
        rows_by_cell_and_sample[(row["condition"], row["model"])][row["sample_id"]] = row

    enriched: list[dict[str, object]] = []
    for (condition_name, model_name), rows_by_sample in rows_by_cell_and_sample.items():
        preprocessed_by_id = dict(
            zip(
                (record.id for record in records),
                apply_condition_preprocessing(
                    condition_name, [record.raw_text for record in records]
                ),
            )
        )

        for fold_id in range(fold_artifact.metadata.n_splits):
            fold_rows = [row for row in fold_artifact.records if row.fold_id == fold_id]
            train_ids = [
                row.sample_id for row in fold_rows if row.split_role is FoldRole.TRAIN
            ]
            target_ids = [
                row.sample_id
                for row in fold_rows
                if row.split_role is FoldRole.VALIDATION and row.sample_id in rows_by_sample
            ]
            if not target_ids:
                continue

            pipeline = build_condition_pipeline(condition_name, model_name)
            x_train = [preprocessed_by_id[sample_id] for sample_id in train_ids]
            y_train = [records_by_id[sample_id].label.value for sample_id in train_ids]
            pipeline.fit(x_train, y_train)

            tfidf = pipeline.named_steps["tfidf"]
            classifier = pipeline.named_steps["clf"]
            feature_names = tfidf.get_feature_names_out()
            classes = list(classifier.classes_)

            matrix = tfidf.transform([preprocessed_by_id[sid] for sid in target_ids])
            decision_scores = classifier.decision_function(matrix)

            for row_index, sample_id in enumerate(target_ids):
                base_row = rows_by_sample[sample_id]
                scores_by_label = dict(zip(classes, decision_scores[row_index]))
                row_vector = matrix[row_index]
                predicted_index = classes.index(base_row["predicted_label"])
                true_index = classes.index(base_row["true_label"])
                enriched_row = {
                    **base_row,
                    "predicted_top_features": _top_contributing_features(
                        row_vector, classifier.coef_[predicted_index], feature_names, top_n
                    ),
                    "true_top_features": _top_contributing_features(
                        row_vector, classifier.coef_[true_index], feature_names, top_n
                    ),
                }
                for label in MailLabel:
                    enriched_row[f"decision_score_{label.value}"] = float(
                        scores_by_label.get(label.value, float("nan"))
                    )
                enriched.append(enriched_row)
    return enriched
