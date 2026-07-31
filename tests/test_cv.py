from datetime import datetime, timezone

from mail_classification.evaluation import build_common_folds, run_core_cell, run_core_experiments
from mail_classification.schemas import Difficulty, FoldRole, MailLabel, RawMailRecord

LABELS = [
    MailLabel.PRODUCT_INQUIRY,
    MailLabel.TECHNICAL_ISSUE,
    MailLabel.BILLING,
    MailLabel.ACCOUNT_SUPPORT,
]
BODIES = {
    MailLabel.PRODUCT_INQUIRY: "please tell me the price of this product",
    MailLabel.TECHNICAL_ISSUE: "the app crashes every time I open it",
    MailLabel.BILLING: "why was I charged twice on my invoice",
    MailLabel.ACCOUNT_SUPPORT: "I cannot log in to my account",
}
GROUPS_PER_LABEL = 5
SAMPLES_PER_GROUP = 4


def _record(record_id: str, label: MailLabel, template_group: str) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text=f"{BODIES[label]} ({record_id})",
        body_text=BODIES[label],
        label=label,
        template_group=template_group,
        difficulty=Difficulty.EASY,
        has_header=False,
        has_signature=False,
        has_quoted_reply=False,
        generation_seed=1,
        template_id=template_group,
        variation_id=0,
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


def synthetic_records() -> list[RawMailRecord]:
    records = []
    for label in LABELS:
        for group_index in range(GROUPS_PER_LABEL):
            group = f"{label.value}-g{group_index}"
            for sample_index in range(SAMPLES_PER_GROUP):
                records.append(_record(f"{group}-s{sample_index}", label, group))
    return records


def synthetic_fold_artifact(records):
    return build_common_folds(records, data_hash="a" * 64, n_splits=5, random_seed=42)


def test_run_core_cell_covers_every_sample_exactly_once() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    results = run_core_cell(records, artifact, "D0", "linear_svc")

    assert len(results) == 5
    all_predicted_ids = [
        row["sample_id"] for result in results for row in result.oof_rows
    ]
    assert sorted(all_predicted_ids) == sorted(record.id for record in records)
    assert len(all_predicted_ids) == len(set(all_predicted_ids))


def test_run_core_cell_never_predicts_a_training_sample_in_the_same_fold() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    results = run_core_cell(records, artifact, "D0", "linear_svc")

    fold_rows_by_id = {
        (row.fold_id, row.sample_id): row.split_role for row in artifact.records
    }
    for result in results:
        for oof_row in result.oof_rows:
            assert (
                fold_rows_by_id[(result.fold_id, oof_row["sample_id"])]
                is FoldRole.VALIDATION
            )


def test_run_core_cell_reports_nonnegative_timing_and_positive_vocabulary() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    results = run_core_cell(records, artifact, "D0", "linear_svc")

    for result in results:
        assert result.fit_seconds >= 0
        assert result.predict_seconds >= 0
        assert result.vocabulary_size > 0
        assert result.n_train + result.n_test == len(records)


def test_run_core_experiments_covers_all_condition_model_cells() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    results = run_core_experiments(
        records,
        artifact,
        conditions=("D0", "D1"),
        models=("linear_svc", "logistic_regression"),
    )

    cells = {(result.condition, result.model) for result in results}
    assert cells == {
        ("D0", "linear_svc"),
        ("D0", "logistic_regression"),
        ("D1", "linear_svc"),
        ("D1", "logistic_regression"),
    }
    assert len(results) == 4 * 5  # 4 cells x 5 folds
