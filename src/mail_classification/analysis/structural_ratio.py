"""Compare structural-element ratios between the Full population and Core's
OOF misclassifications, from already-written artifacts only.

Reads ``data/raw/full_emails.jsonl`` (population) and
``outputs/runs/<explain_run_id>/misclassifications.csv`` (one row per
(sample_id, condition, model) OOF misclassification instance -- a sample
misclassified in more than one Core cell contributes more than one row,
matching the same instance-level grain error_category_summary.csv already
uses). Never re-fits/re-derives predictions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

STRUCTURAL_FLAGS = ("has_header", "has_signature", "has_quoted_reply")


def _load_full_dataset(full_data_path: str | Path) -> pd.DataFrame:
    lines = Path(full_data_path).read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line]
    return pd.DataFrame(records)


def _two_proportion_z_p_value(count_a: int, n_a: int, count_b: int, n_b: int) -> float:
    """Two-sided p-value for a two-proportion z-test, using only stdlib math
    (math.erf for the normal CDF) to avoid adding scipy as a dependency."""
    p_a, p_b = count_a / n_a, count_b / n_b
    p_pool = (count_a + count_b) / (n_a + n_b)
    if p_pool in (0.0, 1.0):
        return 1.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return 1.0
    z = (p_a - p_b) / se
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def compute_structural_ratio_comparison(
    full_data_path: str | Path, misclassifications_path: str | Path
) -> dict:
    full_df = _load_full_dataset(full_data_path)
    misclass_df = pd.read_csv(misclassifications_path)
    for flag in STRUCTURAL_FLAGS:
        misclass_df[flag] = misclass_df[flag].astype(str).str.lower() == "true"

    n_population = len(full_df)
    n_misclassified = len(misclass_df)
    if n_population == 0 or n_misclassified == 0:
        raise ValueError("population and misclassifications must both be nonempty")

    flags: dict[str, dict[str, object]] = {}
    for flag in STRUCTURAL_FLAGS:
        pop_count = int(full_df[flag].sum())
        mis_count = int(misclass_df[flag].sum())
        pop_ratio = pop_count / n_population
        mis_ratio = mis_count / n_misclassified
        flags[flag] = {
            "population_count": pop_count,
            "population_total": n_population,
            "population_ratio": pop_ratio,
            "misclassified_count": mis_count,
            "misclassified_total": n_misclassified,
            "misclassified_ratio": mis_ratio,
            "ratio_difference": mis_ratio - pop_ratio,
            "exceeds_population_ratio": bool(mis_ratio > pop_ratio),
            "two_proportion_z_p_value": _two_proportion_z_p_value(
                mis_count, n_misclassified, pop_count, n_population
            ),
        }

    return {
        "population_total": n_population,
        "misclassified_total": n_misclassified,
        "misclassified_grain": "one row per (sample_id, condition, model) OOF instance",
        "flags": flags,
    }


def write_structural_ratio_comparison(
    full_data_path: str | Path, misclassifications_path: str | Path, output_path: str | Path
) -> Path:
    result = compute_structural_ratio_comparison(full_data_path, misclassifications_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output_path
