"""Independently recompute Japanese BERT metrics from tracked artifacts.

Reads ``fold_metrics.csv`` and ``predictions_oof.csv`` directly (never the
report generation code path) and recomputes every reported number from
scratch, so a bug in ``reporting/ja_generation.py``/``ja_tables.py`` cannot
silently reproduce itself here. Two aggregation methods are computed and
named distinctly, and must never be confused with each other:

- ``fold_mean_*`` / ``fold_std_*``: mean/population-stddev of the 5 per-fold
  metric values already stored in fold_metrics.csv (each fold's own
  accuracy/precision/recall/F1, computed once per fold at training time).
- ``oof_*``: recomputed directly from the 800 pooled out-of-fold predictions
  in predictions_oof.csv, independent of whatever fold_metrics.csv says.

These are expected to be close but are not identical in general (fold sizes
here are not perfectly equal: 167/167/134/166/166), so this script computes
both and never silently substitutes one for the other.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

LABELS = ["account_support", "billing", "product_inquiry", "technical_issue"]
ROOT = Path(__file__).resolve().parents[1]
BERT_RUN_DIR = ROOT / "outputs" / "runs" / "phaseJA7-bert-seed42"
CORE_RUN_DIR = ROOT / "outputs" / "runs" / "phaseJA4-core-seed42"
FOLD_ARTIFACT_PATH = ROOT / "outputs" / "folds" / "common_folds_ja.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _pstdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


def audit_fold_metrics(fold_metrics_path: Path) -> dict[str, object]:
    rows = _read_csv(fold_metrics_path)
    if len(rows) != 5:
        raise ValueError(f"expected 5 fold rows, found {len(rows)} in {fold_metrics_path}")

    accuracy = [float(r["accuracy"]) for r in rows]
    macro_precision = [float(r["macro_precision"]) for r in rows]
    macro_recall = [float(r["macro_recall"]) for r in rows]
    macro_f1 = [float(r["macro_f1"]) for r in rows]
    n_val = [int(r["n_val"]) for r in rows]

    if sum(n_val) != 800:
        raise ValueError(f"fold n_val values sum to {sum(n_val)}, expected 800")

    return {
        "fold_mean_accuracy": _mean(accuracy),
        "fold_std_accuracy": _pstdev(accuracy),
        "fold_mean_macro_precision": _mean(macro_precision),
        "fold_std_macro_precision": _pstdev(macro_precision),
        "fold_mean_macro_recall": _mean(macro_recall),
        "fold_std_macro_recall": _pstdev(macro_recall),
        "fold_mean_macro_f1": _mean(macro_f1),
        "fold_std_macro_f1": _pstdev(macro_f1),
        "per_fold_accuracy": accuracy,
        "per_fold_n_val": n_val,
        "n_val_sum": sum(n_val),
    }


def audit_oof_predictions(oof_path: Path) -> dict[str, object]:
    rows = _read_csv(oof_path)
    sample_ids = [r["sample_id"] for r in rows]
    unique_ids = set(sample_ids)
    duplicate_count = len(sample_ids) - len(unique_ids)

    y_true = [r["true_label"] for r in rows]
    y_pred = [r["predicted_label"] for r in rows]
    true_counts = {label: y_true.count(label) for label in LABELS}
    pred_counts = {label: y_pred.count(label) for label in LABELS}

    oof_accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", labels=LABELS, zero_division=0
    )
    cw_precision, cw_recall, cw_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=LABELS)
    matrix_rows = {
        true_label: {
            pred_label: int(matrix[i][j]) for j, pred_label in enumerate(LABELS)
        }
        for i, true_label in enumerate(LABELS)
    }
    matrix_sum = int(matrix.sum())

    return {
        "oof_row_count": len(rows),
        "sample_id_duplicate_count": duplicate_count,
        "sample_id_missing_count": max(0, 800 - len(unique_ids)),
        "true_label_counts": true_counts,
        "predicted_label_counts": pred_counts,
        "oof_accuracy": float(oof_accuracy),
        "oof_macro_precision": float(precision),
        "oof_macro_recall": float(recall),
        "oof_macro_f1": float(f1),
        "oof_classwise_precision": dict(zip(LABELS, (float(v) for v in cw_precision))),
        "oof_classwise_recall": dict(zip(LABELS, (float(v) for v in cw_recall))),
        "oof_classwise_f1": dict(zip(LABELS, (float(v) for v in cw_f1))),
        "confusion_matrix": matrix_rows,
        "confusion_matrix_sum": matrix_sum,
    }


def run_audit(bert_run_dir: Path = BERT_RUN_DIR) -> dict[str, object]:
    manifest = json.loads((bert_run_dir / "manifest.json").read_text(encoding="utf-8"))
    fold_summary = audit_fold_metrics(bert_run_dir / "fold_metrics.csv")
    oof_summary = audit_oof_predictions(bert_run_dir / "predictions_oof.csv")

    fold_artifact = json.loads(FOLD_ARTIFACT_PATH.read_text(encoding="utf-8"))
    fold_hash_matches = manifest["fold_artifact_hash"] == _sha256_file(FOLD_ARTIFACT_PATH)
    validation_ids = {
        row["sample_id"]
        for row in fold_artifact["records"]
        if row["split_role"] == "validation"
    }

    checks = {
        "oof_row_count_is_800": oof_summary["oof_row_count"] == 800,
        "no_duplicate_sample_ids": oof_summary["sample_id_duplicate_count"] == 0,
        "no_missing_sample_ids": oof_summary["sample_id_missing_count"] == 0,
        "each_class_has_200_true": all(
            count == 200 for count in oof_summary["true_label_counts"].values()
        ),
        "confusion_matrix_sums_to_800": oof_summary["confusion_matrix_sum"] == 800,
        "fold_n_val_sums_to_800": fold_summary["n_val_sum"] == 800,
        "fold_artifact_hash_matches_manifest": fold_hash_matches,
        "oof_sample_ids_match_fold_validation_ids": (
            set(_read_sample_ids(bert_run_dir / "predictions_oof.csv")) == validation_ids
        ),
        "all_metrics_finite_and_in_unit_interval": all(
            0.0 <= value <= 1.0
            for key in (
                "fold_mean_accuracy",
                "fold_mean_macro_precision",
                "fold_mean_macro_recall",
                "fold_mean_macro_f1",
            )
            for value in [fold_summary[key]]
        )
        and all(
            0.0 <= value <= 1.0
            for key in (
                "oof_accuracy",
                "oof_macro_precision",
                "oof_macro_recall",
                "oof_macro_f1",
            )
            for value in [oof_summary[key]]
        ),
    }

    return {
        "manifest": manifest,
        "fold_summary": fold_summary,
        "oof_summary": oof_summary,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def _read_sample_ids(oof_path: Path) -> list[str]:
    return [r["sample_id"] for r in _read_csv(oof_path)]


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    result = run_audit()
    fold_summary = result["fold_summary"]
    oof_summary = result["oof_summary"]

    print("=== Fold-mean (5 per-fold values) ===")
    print(f"fold_mean_accuracy       = {fold_summary['fold_mean_accuracy']:.6f}")
    print(f"fold_std_accuracy        = {fold_summary['fold_std_accuracy']:.6f}")
    print(f"fold_mean_macro_precision= {fold_summary['fold_mean_macro_precision']:.6f}")
    print(f"fold_std_macro_precision = {fold_summary['fold_std_macro_precision']:.6f}")
    print(f"fold_mean_macro_recall   = {fold_summary['fold_mean_macro_recall']:.6f}")
    print(f"fold_std_macro_recall    = {fold_summary['fold_std_macro_recall']:.6f}")
    print(f"fold_mean_macro_f1       = {fold_summary['fold_mean_macro_f1']:.6f}")
    print(f"fold_std_macro_f1        = {fold_summary['fold_std_macro_f1']:.6f}")
    print(f"per_fold_accuracy        = {fold_summary['per_fold_accuracy']}")

    print()
    print("=== OOF-direct (800 pooled predictions) ===")
    print(f"oof_row_count            = {oof_summary['oof_row_count']}")
    print(f"sample_id_duplicate_count= {oof_summary['sample_id_duplicate_count']}")
    print(f"sample_id_missing_count  = {oof_summary['sample_id_missing_count']}")
    print(f"true_label_counts        = {oof_summary['true_label_counts']}")
    print(f"predicted_label_counts   = {oof_summary['predicted_label_counts']}")
    print(f"oof_accuracy             = {oof_summary['oof_accuracy']:.6f}")
    print(f"oof_macro_precision      = {oof_summary['oof_macro_precision']:.6f}")
    print(f"oof_macro_recall         = {oof_summary['oof_macro_recall']:.6f}")
    print(f"oof_macro_f1             = {oof_summary['oof_macro_f1']:.6f}")
    print(f"oof_classwise_precision  = {oof_summary['oof_classwise_precision']}")
    print(f"oof_classwise_recall     = {oof_summary['oof_classwise_recall']}")
    print(f"oof_classwise_f1         = {oof_summary['oof_classwise_f1']}")
    print(f"confusion_matrix         = {oof_summary['confusion_matrix']}")
    print(f"confusion_matrix_sum     = {oof_summary['confusion_matrix_sum']}")

    print()
    print("=== Checks ===")
    for name, passed in result["checks"].items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    print()
    print("ALL CHECKS PASSED" if result["all_checks_passed"] else "SOME CHECKS FAILED")
