"""Paired-design statistical treatment: McNemar's test and sample-level paired bootstrap.

Every level (C10/C20/C30) is evaluated on the *same* 800 sample_ids as C0
(paired design, project_rules.md section 8: "CV Foldを独立標本とした安易な
有意差検定をしない"), so plain independent-sample tests would be invalid.
McNemar's test is the standard paired test for two classifiers' per-sample
correct/incorrect outcomes; the paired bootstrap resamples sample_ids (not
folds) with replacement to build a descriptive interval for the macro-F1
difference. Neither correction accounts for the fact that four (condition,
model) cells and three levels are compared here (a multiple-comparisons
problem) or for indirect effects (an uncontaminated validation sample's
prediction can still shift because *other* samples in its training fold were
contaminated) -- both caveats are surfaced in the returned dict rather than
suppressed, and the report states results as descriptive, not as a claimed
significant effect after correction.

No scipy dependency: for 1 degree of freedom, the chi-squared survival
function has the closed form ``erfc(sqrt(x / 2))`` (a chi-squared(1)
variable is the square of a standard normal), computed with stdlib ``math``.
"""

from __future__ import annotations

from math import erfc, sqrt
import random

from sklearn.metrics import f1_score

DEFAULT_N_BOOTSTRAP = 2000


def _paired_outcomes(
    oof_rows: list[dict[str, object]],
    condition: str,
    model: str,
    baseline_level: str,
    compare_level: str,
) -> dict[str, tuple[bool, bool, str, str, str, str]]:
    """sample_id -> (baseline_correct, compare_correct, baseline_true, baseline_pred, compare_true, compare_pred)."""
    by_level: dict[tuple[str, str], dict[str, dict[str, object]]] = {}
    for row in oof_rows:
        if row["condition"] != condition or row["model"] != model:
            continue
        if row["contamination_level"] not in (baseline_level, compare_level):
            continue
        by_level.setdefault(row["contamination_level"], {})[row["sample_id"]] = row

    baseline_rows = by_level.get(baseline_level, {})
    compare_rows = by_level.get(compare_level, {})
    shared_ids = sorted(set(baseline_rows) & set(compare_rows))
    if not shared_ids:
        raise ValueError(f"no shared sample_id between {baseline_level!r} and {compare_level!r}")

    return {
        sample_id: (
            baseline_rows[sample_id]["true_label"] == baseline_rows[sample_id]["predicted_label"],
            compare_rows[sample_id]["true_label"] == compare_rows[sample_id]["predicted_label"],
            baseline_rows[sample_id]["true_label"],
            baseline_rows[sample_id]["predicted_label"],
            compare_rows[sample_id]["true_label"],
            compare_rows[sample_id]["predicted_label"],
        )
        for sample_id in shared_ids
    }


def mcnemar_test(
    oof_rows: list[dict[str, object]],
    assignment_rows: list[dict[str, object]],
    *,
    condition: str,
    model: str,
    baseline_level: str = "C0",
    compare_level: str,
    contaminated_only: bool = False,
) -> dict[str, object]:
    """McNemar's test (continuity-corrected) on paired correct/incorrect outcomes."""
    from .analysis import applies_at  # local import: avoids a module-level cycle with analysis.py

    outcomes = _paired_outcomes(oof_rows, condition, model, baseline_level, compare_level)
    if contaminated_only:
        assignment_by_id = {row["sample_id"]: row for row in assignment_rows}
        outcomes = {
            sample_id: value
            for sample_id, value in outcomes.items()
            if sample_id in assignment_by_id and applies_at(assignment_by_id[sample_id], compare_level)
        }

    b = sum(1 for baseline_correct, compare_correct, *_ in outcomes.values() if baseline_correct and not compare_correct)
    c = sum(1 for baseline_correct, compare_correct, *_ in outcomes.values() if not baseline_correct and compare_correct)
    n = len(outcomes)

    if b + c == 0:
        statistic, p_value = 0.0, 1.0
    else:
        statistic = (abs(b - c) - 1) ** 2 / (b + c)
        p_value = erfc(sqrt(statistic / 2))

    return {
        "condition": condition,
        "model": model,
        "baseline_level": baseline_level,
        "compare_level": compare_level,
        "contaminated_only": contaminated_only,
        "n_pairs": n,
        "n_correct_to_incorrect": b,
        "n_incorrect_to_correct": c,
        "statistic": statistic,
        "p_value": p_value,
        "caveat": (
            "Paired design, single (condition,model,level) comparison shown without a "
            "multiple-comparisons correction across the 4x3 cells tested; an "
            "uncontaminated sample's prediction can still shift because other samples "
            "in its training fold were contaminated (indirect effect, not isolated by "
            "this test)."
        ),
    }


def paired_bootstrap_macro_f1_diff(
    oof_rows: list[dict[str, object]],
    *,
    condition: str,
    model: str,
    baseline_level: str = "C0",
    compare_level: str,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
    seed: int = 42,
) -> dict[str, object]:
    """Sample-level (not fold-level) paired bootstrap CI for the macro-F1 difference."""
    outcomes = _paired_outcomes(oof_rows, condition, model, baseline_level, compare_level)
    sample_ids = sorted(outcomes)
    baseline_true = [outcomes[sid][2] for sid in sample_ids]
    baseline_pred = [outcomes[sid][3] for sid in sample_ids]
    compare_true = [outcomes[sid][4] for sid in sample_ids]
    compare_pred = [outcomes[sid][5] for sid in sample_ids]
    labels = sorted(set(baseline_true) | set(compare_true))

    observed_diff = f1_score(
        compare_true, compare_pred, average="macro", labels=labels, zero_division=0
    ) - f1_score(baseline_true, baseline_pred, average="macro", labels=labels, zero_division=0)

    rng = random.Random(seed)
    n = len(sample_ids)
    diffs: list[float] = []
    for _ in range(n_bootstrap):
        indices = [rng.randrange(n) for _ in range(n)]
        b_true = [baseline_true[i] for i in indices]
        b_pred = [baseline_pred[i] for i in indices]
        c_true = [compare_true[i] for i in indices]
        c_pred = [compare_pred[i] for i in indices]
        diffs.append(
            f1_score(c_true, c_pred, average="macro", labels=labels, zero_division=0)
            - f1_score(b_true, b_pred, average="macro", labels=labels, zero_division=0)
        )
    diffs.sort()

    def _percentile(p: float) -> float:
        index = min(len(diffs) - 1, max(0, round(p * (len(diffs) - 1))))
        return diffs[index]

    return {
        "condition": condition,
        "model": model,
        "baseline_level": baseline_level,
        "compare_level": compare_level,
        "n_samples": n,
        "n_bootstrap": n_bootstrap,
        "observed_diff": observed_diff,
        "bootstrap_mean_diff": sum(diffs) / len(diffs),
        "ci95_low": _percentile(0.025),
        "ci95_high": _percentile(0.975),
        "fraction_bootstrap_le_zero": sum(1 for diff in diffs if diff <= 0) / len(diffs),
        "caveat": (
            "Sample-level paired bootstrap; not corrected for the 4x3 cells tested, "
            "and folds (not samples) were the CV unit, so this is a descriptive interval, "
            "not a formally powered hypothesis test."
        ),
    }
