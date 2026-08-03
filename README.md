# Task 10: Synthetic inquiry-mail classification

This project evaluates preprocessing and leakage controls for English inquiry
mail classification using TF-IDF + linear classifiers. All mail records are
synthetic; no Rabiloo internal mail, customer data, or other confidential
source is used.

Current status: Phase 0 through Phase 7 are complete (see
`docs/management/execution_plan.md` for the authoritative per-phase status,
evidence, and commit hashes; `docs/management/daily_report_*.md` for the
session-by-session work log).

Project rules are defined in `docs/management/project_rules.md`. Everything
under `outputs/` and the generated files under `data/raw/` are reproducible
from tracked configuration, templates, and code, and are intentionally
excluded from Git.

## Reproducing the pipeline

```bash
# 1. Resolve dependencies (Core + dev + reporting groups)
uv sync --group dev --group reporting

# 2. Generate the approved Full dataset (verified against
#    docs/reviews/full_review_decision.json's tracked hash)
uv run python scripts/generate_full_data.py

# 3. Run the Core ablation (D0/D1/D2 x LinearSVC/LogisticRegression,
#    common 5-fold CV) -- writes outputs/folds/ and
#    outputs/runs/phase4-core-seed42/
uv run python - <<'PY'
from pathlib import Path
from mail_classification.evaluation import (
    build_common_folds, load_verified_full_dataset,
    run_and_write_core_experiments, verify_full_dataset_hash, write_fold_artifact,
)
root = Path.cwd()
data_path = root / "data" / "raw" / "full_emails.jsonl"
decision_path = root / "docs" / "reviews" / "full_review_decision.json"
data_hash = verify_full_dataset_hash(data_path, decision_path)
records = load_verified_full_dataset(data_path, decision_path)
artifact = build_common_folds(records, data_hash=data_hash)
fold_path = root / "outputs" / "folds" / "common_folds.json"
write_fold_artifact(fold_path, artifact)
run_and_write_core_experiments(records, fold_path, root, run_id="phase4-core-seed42")
PY

# 4. Explainability / misclassification analysis --
#    writes outputs/runs/phase5-explain-seed42/
uv run python - <<'PY'
from pathlib import Path
from mail_classification.evaluation import load_verified_full_dataset, verify_full_dataset_hash
from mail_classification.explain import run_and_write_explainability
root = Path.cwd()
data_path = root / "data" / "raw" / "full_emails.jsonl"
decision_path = root / "docs" / "reviews" / "full_review_decision.json"
records = load_verified_full_dataset(data_path, decision_path)
fold_path = root / "outputs" / "folds" / "common_folds.json"
core_dir = root / "outputs" / "runs" / "phase4-core-seed42"
run_and_write_explainability(
    records, fold_path, core_dir / "predictions_oof.csv", root, run_id="phase5-explain-seed42"
)
PY

# 5. Extension: MinHashLSH near-duplicate sensitivity (no new dependency) --
#    writes outputs/extensions/phase6-minhash-seed42/
uv run python - <<'PY'
from pathlib import Path
from mail_classification.evaluation import load_verified_full_dataset, verify_full_dataset_hash
from mail_classification.extensions import run_and_write_minhash_extension
root = Path.cwd()
data_path = root / "data" / "raw" / "full_emails.jsonl"
decision_path = root / "docs" / "reviews" / "full_review_decision.json"
data_hash = verify_full_dataset_hash(data_path, decision_path)
records = load_verified_full_dataset(data_path, decision_path)
run_and_write_minhash_extension(records, data_hash, root, run_id="phase6-minhash-seed42")
PY

# 6. Build the final report: Markdown -> HTML -> PDF -> layout check --
#    writes outputs/reports/phase7-report-phase4-core-seed42/
uv run python scripts/build_report.py

# 7. Verify everything
uv run pytest -q
uv lock --check
```

Every step above is seed-fixed (`random_seed=42`) and keyed by the tracked
Full-dataset hash and common Fold artifact hash, so re-running it reproduces
the same `outputs/runs/`, `outputs/extensions/`, and `outputs/reports/`
content. `scripts/generate_smoke_data.py` / `generate_pilot_data.py` cover the
smaller Smoke/Pilot stages that preceded Full generation, if needed.

## Layout

- `src/mail_classification/`: schemas, preprocessing, generation, quality,
  evaluation, models, explain, extensions, reporting.
- `tools/pdf_renderer/`: standalone Markdown -> HTML -> PDF tool (ported from
  Task 9), independent of the experiment code.
- `docs/management/`: execution plan, project rules, daily reports.
- `docs/architecture/`, `docs/contracts/`, `docs/schemas/`, `docs/audits/`,
  `docs/reviews/`: design docs, data/model contracts, schema specs, prior-task
  audits, and tracked human-review approval evidence.
- `outputs/`: generated artifacts (Fold assignments, Core/Explain/Extension
  runs, the final report). All gitignored and reproducible from the commands
  above.
