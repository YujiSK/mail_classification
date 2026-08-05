"""LinearSVC feature-shift (C0 vs C30) and representative before/after transition examples.

``build_feature_shift`` reuses ``explain.linear.extract_fold_coefficients``
unchanged (a per-fold refit on that fold's own train split, exactly as Core
Phase 5 does) for the D1+LinearSVC cell at C0 and at C30, then compares the
per-label/per-feature fold-mean coefficients. ``subtopic_vocabulary_match``
flags whether a shifted feature is drawn from the contamination sentence
bank, directly answering "モデルが主トピックより副トピックの語彙へ引っ張ら
れる傾向" at the vocabulary level.

``build_representative_transition_examples`` answers the same question at
the single-sample level: for samples whose *own* text only differs between
C0 and C30 (contamination first applied at C30, i.e. ``min_level == "C30"``),
it refits that sample's validation fold under both datasets and reports the
decision-score/top-feature change -- the person-level evidence the aggregate
coefficient shift cannot show by itself.
"""

from __future__ import annotations

from collections import defaultdict
import re
from statistics import mean

from mail_classification.explain.linear import extract_fold_coefficients
from mail_classification.models import apply_condition_preprocessing, build_condition_pipeline
from mail_classification.schemas import FoldArtifact, FoldRole, MailLabel, RawMailRecord

from .sentences import SUBTOPIC_SENTENCES

FEATURE_SHIFT_FIELDS = [
    "label",
    "feature",
    "mean_coefficient_c0",
    "mean_coefficient_c30",
    "coefficient_shift",
    "rank_type",
    "subtopic_vocabulary_match",
]

_TOKEN_RE = re.compile(r"[a-zA-Z]+")
_TOP_FEATURE_N = 5

# Generic connector/function words used across every subtopic's sentences
# (e.g. "also", "the", "would"): excluded so vocabulary-match only flags
# genuinely subtopic-specific content words, not shared sentence scaffolding.
_CONNECTOR_STOPWORDS = frozenset(
    {
        "a", "about", "above", "also", "an", "and", "any", "are", "as", "at", "be",
        "below", "but", "can", "convenient", "could", "did", "do", "does", "down",
        "for", "free", "from", "had", "has", "have", "here", "i", "if", "in", "is",
        "isn", "it", "just", "later", "least", "main", "matters", "me", "most",
        "my", "no", "not", "note", "now", "of", "once", "one", "or", "quick",
        "reason", "reference", "right", "rush", "s", "secondary", "side", "small",
        "so", "some", "t", "that", "the", "this", "though", "time", "to", "too",
        "up", "urgency", "urgent", "was", "were", "what", "when", "whenever",
        "would", "writing", "you", "your",
    }
)


def _subtopic_vocabulary() -> dict[str, set[str]]:
    return {
        subtopic: {
            token.lower()
            for sentence in sentences
            for token in _TOKEN_RE.findall(sentence.text)
            if token.lower() not in _CONNECTOR_STOPWORDS
        }
        for subtopic, sentences in SUBTOPIC_SENTENCES.items()
    }


def _matching_subtopic(feature: str, vocabulary: dict[str, set[str]]) -> str:
    return "|".join(sorted(subtopic for subtopic, tokens in vocabulary.items() if feature in tokens))


def build_feature_shift(
    records_by_level: dict[str, list[RawMailRecord]],
    fold_artifact: FoldArtifact,
    *,
    condition_name: str = "D1",
    model_name: str = "linear_svc",
    baseline_level: str = "C0",
    compare_level: str = "C30",
    top_n: int = 25,
) -> list[dict[str, object]]:
    baseline_rows = extract_fold_coefficients(
        records_by_level[baseline_level], fold_artifact, condition_name, model_name, top_n=top_n
    )
    compare_rows = extract_fold_coefficients(
        records_by_level[compare_level], fold_artifact, condition_name, model_name, top_n=top_n
    )

    def _mean_by_label_feature(rows: list[dict[str, object]]) -> dict[tuple[str, str], float]:
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row in rows:
            if row["rank_type"] != "top_absolute":
                continue
            grouped[(row["label"], row["feature"])].append(row["coefficient"])
        return {key: mean(values) for key, values in grouped.items()}

    baseline_means = _mean_by_label_feature(baseline_rows)
    compare_means = _mean_by_label_feature(compare_rows)
    vocabulary = _subtopic_vocabulary()

    result: list[dict[str, object]] = []
    for label, feature in sorted(set(baseline_means) | set(compare_means)):
        c0 = baseline_means.get((label, feature))
        c30 = compare_means.get((label, feature))
        result.append(
            {
                "label": label,
                "feature": feature,
                "mean_coefficient_c0": c0 if c0 is not None else "",
                "mean_coefficient_c30": c30 if c30 is not None else "",
                "coefficient_shift": (c30 - c0) if (c0 is not None and c30 is not None) else "",
                "rank_type": "top_absolute",
                "subtopic_vocabulary_match": _matching_subtopic(feature, vocabulary),
            }
        )
    return result


def _top_contributions(row_vector, coef_row, feature_names, top_n: int) -> str:
    _, nonzero_indices = row_vector.nonzero()
    contributions = [
        (feature_names[index], float(row_vector[0, index] * coef_row[index]))
        for index in nonzero_indices
    ]
    contributions.sort(key=lambda item: item[1], reverse=True)
    return "; ".join(f"{name}:{value:.4f}" for name, value in contributions[:top_n])


def _fold_id_for_sample(fold_artifact: FoldArtifact, sample_id: str) -> int:
    for record in fold_artifact.records:
        if record.sample_id == sample_id and record.split_role is FoldRole.VALIDATION:
            return record.fold_id
    raise ValueError(f"sample_id {sample_id!r} has no validation fold in the Fold artifact")


def _fit_and_score_one_sample(
    records: list[RawMailRecord],
    fold_artifact: FoldArtifact,
    condition_name: str,
    model_name: str,
    fold_id: int,
    sample_id: str,
) -> dict[str, object]:
    records_by_id = {record.id: record for record in records}
    preprocessed_by_id = dict(
        zip(
            (record.id for record in records),
            apply_condition_preprocessing(condition_name, [record.raw_text for record in records]),
        )
    )
    fold_rows = [row for row in fold_artifact.records if row.fold_id == fold_id]
    train_ids = [row.sample_id for row in fold_rows if row.split_role is FoldRole.TRAIN]

    pipeline = build_condition_pipeline(condition_name, model_name)
    pipeline.fit(
        [preprocessed_by_id[sid] for sid in train_ids],
        [records_by_id[sid].label.value for sid in train_ids],
    )

    tfidf = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["clf"]
    feature_names = tfidf.get_feature_names_out()
    classes = list(classifier.classes_)

    matrix = tfidf.transform([preprocessed_by_id[sample_id]])
    decision_scores = classifier.decision_function(matrix)[0]
    predicted_label = pipeline.predict([preprocessed_by_id[sample_id]])[0]
    true_label = records_by_id[sample_id].label.value
    scores_by_label = dict(zip(classes, (float(v) for v in decision_scores)))

    return {
        "predicted_label": predicted_label,
        "true_label": true_label,
        "decision_scores": {label.value: scores_by_label.get(label.value, float("nan")) for label in MailLabel},
        "top_features_predicted": _top_contributions(
            matrix[0], classifier.coef_[classes.index(predicted_label)], feature_names, _TOP_FEATURE_N
        ),
        "top_features_true": _top_contributions(
            matrix[0], classifier.coef_[classes.index(true_label)], feature_names, _TOP_FEATURE_N
        ),
    }


REPRESENTATIVE_EXAMPLE_FIELDS = [
    "sample_id",
    "main_label",
    "subtopic_label",
    "style",
    "insertion_position",
    "fold_id",
    "true_label",
    "predicted_label_c0",
    "predicted_label_c30",
    "transition",
    "decision_score_true_label_c0",
    "decision_score_true_label_c30",
    "decision_score_subtopic_label_c0",
    "decision_score_subtopic_label_c30",
    "top_features_predicted_c0",
    "top_features_predicted_c30",
    "body_text_c0",
    "body_text_c30",
]


def build_representative_transition_examples(
    records_by_level: dict[str, list[RawMailRecord]],
    fold_artifact: FoldArtifact,
    assignment_rows: list[dict[str, object]],
    *,
    condition_name: str = "D1",
    model_name: str = "linear_svc",
    baseline_level: str = "C0",
    compare_level: str = "C30",
    max_examples: int = 6,
) -> list[dict[str, object]]:
    """Per-sample before/after decision-score comparison for isolated (C30-only) contamination."""
    c30_only_ids = sorted(
        row["sample_id"] for row in assignment_rows if row["min_level"] == "C30"
    )
    if len(c30_only_ids) > 200:
        # Deterministic subsample to keep refit cost bounded; every candidate is
        # equally isolated (contamination only present at C30), so an id-sorted
        # stride is a fine, reproducible way to pick a manageable pool.
        stride = len(c30_only_ids) // 200 + 1
        c30_only_ids = c30_only_ids[::stride]

    assignment_by_id = {row["sample_id"]: row for row in assignment_rows}
    c0_records = {record.id: record for record in records_by_level[baseline_level]}
    c30_records = {record.id: record for record in records_by_level[compare_level]}

    candidates: list[dict[str, object]] = []
    for sample_id in c30_only_ids:
        fold_id = _fold_id_for_sample(fold_artifact, sample_id)
        before = _fit_and_score_one_sample(
            records_by_level[baseline_level], fold_artifact, condition_name, model_name, fold_id, sample_id
        )
        after = _fit_and_score_one_sample(
            records_by_level[compare_level], fold_artifact, condition_name, model_name, fold_id, sample_id
        )
        before_correct = before["predicted_label"] == before["true_label"]
        after_correct = after["predicted_label"] == after["true_label"]
        if before_correct == after_correct:
            transition = "unchanged"
        elif before_correct and not after_correct:
            transition = "correct_to_incorrect"
        else:
            transition = "incorrect_to_correct"

        assignment_row = assignment_by_id[sample_id]
        candidates.append(
            {
                "sample_id": sample_id,
                "main_label": assignment_row["main_label"],
                "subtopic_label": assignment_row["subtopic_label"],
                "style": assignment_row["style"],
                "insertion_position": assignment_row["insertion_position"],
                "fold_id": fold_id,
                "true_label": before["true_label"],
                "predicted_label_c0": before["predicted_label"],
                "predicted_label_c30": after["predicted_label"],
                "transition": transition,
                "decision_score_true_label_c0": before["decision_scores"][before["true_label"]],
                "decision_score_true_label_c30": after["decision_scores"][after["true_label"]],
                "decision_score_subtopic_label_c0": before["decision_scores"][assignment_row["subtopic_label"]],
                "decision_score_subtopic_label_c30": after["decision_scores"][assignment_row["subtopic_label"]],
                "top_features_predicted_c0": before["top_features_predicted"],
                "top_features_predicted_c30": after["top_features_predicted"],
                "body_text_c0": c0_records[sample_id].body_text,
                "body_text_c30": c30_records[sample_id].body_text,
            }
        )
        if sum(1 for c in candidates if c["transition"] == "correct_to_incorrect") >= max_examples:
            break

    # Prioritize the illustrative "pulled toward the subtopic" flips, then fill
    # remaining slots with any other observed transition for contrast.
    flipped = [c for c in candidates if c["transition"] == "correct_to_incorrect"]
    other = [c for c in candidates if c["transition"] != "correct_to_incorrect"]
    return (flipped + other)[:max_examples]
