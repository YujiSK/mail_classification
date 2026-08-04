"""Phase JA-8: English<->Japanese comparison, computed once and cached as JSON.

Reads only already-written English (Core, hash-fixed, unmodified) and
Japanese artifacts; never re-runs training or evaluation. Group-level (not
sample-level) comparison, since English and Japanese template variations
are semantically paired via ``semantic_template_id`` but are not literal
1:1 translations, so no per-record correspondence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from mail_classification.generation.io import write_json
from mail_classification.reporting.tables import best_core_metric_cell, read_csv_rows

DEFAULT_THRESHOLD = 0.5


def _group_accuracy(
    oof_rows: list[dict[str, str]], records_by_id: dict[str, dict], group_key
) -> dict[str, float]:
    correct: dict[str, int] = {}
    total: dict[str, int] = {}
    for row in oof_rows:
        group = group_key(records_by_id[row["sample_id"]])
        total[group] = total.get(group, 0) + 1
        if row["true_label"] == row["predicted_label"]:
            correct[group] = correct.get(group, 0) + 1
    return {group: correct.get(group, 0) / count for group, count in total.items()}


def build_en_ja_comparison(
    project_root: str | Path,
    *,
    en_core_run_id: str = "phase4-core-seed42",
    ja_core_run_id: str = "phaseJA4-core-seed42",
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, object]:
    project_root = Path(project_root).resolve()

    en_metrics = read_csv_rows(
        project_root / "outputs" / "runs" / en_core_run_id / "metrics_summary.csv"
    )
    en_condition, en_model, en_macro_f1 = best_core_metric_cell(
        project_root / "outputs" / "runs" / en_core_run_id, "macro_f1"
    )
    ja_condition, ja_model, ja_macro_f1 = best_core_metric_cell(
        project_root / "outputs" / "runs" / ja_core_run_id, "macro_f1"
    )

    en_oof = read_csv_rows(project_root / "outputs" / "runs" / en_core_run_id / "predictions_oof.csv")
    ja_oof = read_csv_rows(project_root / "outputs" / "runs" / ja_core_run_id / "predictions_oof.csv")
    en_best_oof = [r for r in en_oof if r["condition"] == en_condition and r["model"] == en_model]
    ja_best_oof = [r for r in ja_oof if r["condition"] == ja_condition and r["model"] == ja_model]

    en_records = {
        rec["id"]: rec
        for rec in (
            json.loads(line)
            for line in (project_root / "data" / "raw" / "full_emails.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }
    ja_records = {
        rec["id"]: rec
        for rec in (
            json.loads(line)
            for line in (project_root / "data" / "raw" / "full_emails_ja.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }

    en_group_accuracy = _group_accuracy(en_best_oof, en_records, lambda rec: rec["template_group"])
    ja_group_accuracy = _group_accuracy(
        ja_best_oof, ja_records, lambda rec: rec["metadata"]["semantic_template_id"]
    )

    both_high = en_only = ja_only = both_low = 0
    for group in sorted(en_group_accuracy):
        en_high = en_group_accuracy[group] >= threshold
        ja_high = ja_group_accuracy.get(group, 0.0) >= threshold
        if en_high and ja_high:
            both_high += 1
        elif en_high:
            en_only += 1
        elif ja_high:
            ja_only += 1
        else:
            both_low += 1

    return {
        "en_condition": f"{en_condition}/{en_model}",
        "ja_condition": f"{ja_condition}/{ja_model}",
        "en_macro_f1": en_macro_f1,
        "ja_macro_f1": ja_macro_f1,
        "en_group_accuracy": en_group_accuracy,
        "ja_group_accuracy": ja_group_accuracy,
        "threshold": threshold,
        "both_high": both_high,
        "en_only_high": en_only,
        "ja_only_high": ja_only,
        "both_low": both_low,
    }


def write_en_ja_comparison(
    project_root: str | Path,
    output_path: str | Path,
    **kwargs,
) -> dict[str, object]:
    comparison = build_en_ja_comparison(project_root, **kwargs)
    write_json(output_path, comparison)
    return comparison
