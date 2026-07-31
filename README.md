# Task 10: Synthetic inquiry-mail classification

This project evaluates preprocessing and leakage controls for English inquiry
mail classification. All mail records are synthetic; no Rabiloo internal mail,
customer data, or other confidential source is used.

Current status:

- Phase 1: schemas and preprocessing contracts complete.
- Phase 2: synthetic-data generation and automatic quality assurance complete;
  Pilot review approved after source correction and regeneration. The
  deterministic Full dataset contains 800 records, passed automatic QA, and
  passed the 24-record human spot review.
- Phase 3: ready but not started.
- Model training, cross-validation, and report writing have not started.

Project rules are defined in `docs/project_rules.md`. Generated raw data and
quality outputs are reproducible from tracked configuration and templates and
are intentionally excluded from Git.
