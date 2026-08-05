"""Fit/predict every (contamination level x Core condition x model) cell.

Reuses ``mail_classification.evaluation.cv.run_core_cell`` unchanged for each
cell -- the Fold artifact, the Pipeline factory, and the fold-level fit/
predict/timing logic are all Core's, never re-implemented here. The only new
axis this module adds is looping over the four contamination-level datasets,
which is why the Extension can share the exact same common Fold artifact as
Core: contamination never changes ``sample_id``, ``label``, or
``template_group``, only ``raw_text``/``body_text`` for a subset of samples.
"""

from __future__ import annotations

from mail_classification.evaluation.cv import FoldFitResult, run_core_cell
from mail_classification.schemas import FoldArtifact, RawMailRecord

from .assignment import CONTAMINATION_LEVELS

# D1+LinearSVC is Core's best cell (primary comparison target per the brief);
# D1+LogisticRegression, D0+LinearSVC, D2+LinearSVC add exactly the
# comparisons requested, no more.
CELLS: tuple[tuple[str, str], ...] = (
    ("D1", "linear_svc"),
    ("D1", "logistic_regression"),
    ("D0", "linear_svc"),
    ("D2", "linear_svc"),
)


def run_all_cells(
    records_by_level: dict[str, list[RawMailRecord]],
    fold_artifact: FoldArtifact,
    *,
    cells: tuple[tuple[str, str], ...] = CELLS,
    levels: tuple[str, ...] = CONTAMINATION_LEVELS,
) -> dict[str, list[FoldFitResult]]:
    results: dict[str, list[FoldFitResult]] = {}
    for level in levels:
        records = records_by_level[level]
        level_results: list[FoldFitResult] = []
        for condition_name, model_name in cells:
            level_results.extend(run_core_cell(records, fold_artifact, condition_name, model_name))
        results[level] = level_results
    return results
