# Fold artifact schema

## Purpose and storage

`FoldArtifact` is the reusable assignment contract that lets every future
condition and model consume the same outer folds. It validates assignments but
does not implement `StratifiedKFold` or `StratifiedGroupKFold`. Preferred
storage is one UTF-8 JSON object containing `metadata` and `records`.

Implementation: `src/mail_classification/schemas/folds.py`.

## Metadata

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `schema_version` | string | no | default `1.0` |
| `created_at` | RFC 3339 string | yes | timezone-aware |
| `splitter_name` | string | yes | nonblank; records the chosen strategy |
| `n_splits` | integer | yes | at least 2 |
| `random_seed` | integer | yes | zero or greater |
| `label_column` | string | no | nonblank, default `label` |
| `group_column` | string | no | nonblank, default `template_group` |
| `data_hash` | string | yes | exact-byte SHA-256 |

Each record requires `sample_id`, nonnegative `fold_id`, `split_role` (`train` or
`validation`), one of the four labels, and nonblank `template_group`.

## Cross-record validation

- `fold_id` is smaller than `n_splits`.
- A `(fold_id, sample_id)` occurs once only, so a sample cannot be both train
  and validation in the same fold.
- A `(fold_id, template_group)` has one role only, preventing template-family
  leakage within that fold.

The contract intentionally does not require a group structure to exist or
select a splitter. The future data audit decides that; ordinary stratification
is valid only when no real grouping exists.

## Examples

Valid record:

```json
{"sample_id":"m1","fold_id":0,"split_role":"validation","label":"billing","template_group":"billing-template-1"}
```

Invalid: two records in fold `0` with group `billing-template-1`, where one is
`train` and the other `validation`.

## Future extension

Generation code must verify coverage and class balance before persisting the
artifact. Any added repeated-CV or nested-CV identifiers require a versioned
migration rather than overloading `fold_id`.
