# Run manifest schema

## Purpose and storage

`RunManifest` captures the provenance needed to reproduce a future run without
starting that run on import. Store one UTF-8 JSON file in that run's output
directory. Paths are provenance strings and are not required to exist when a
manifest is read on another machine.

Implementation: `src/mail_classification/schemas/run_manifest.py`.

## Fields

| Field group | JSON type | Presence | Validation |
|---|---|---:|---|
| `run_id`, `created_at`, `output_directory` | string | required | nonblank; timestamp has UTC offset |
| `git_commit`, `git_dirty` | string/null, boolean/null | required, nullable | acquisition failure is explicit `null`; commit is 7–40 lowercase hex |
| `command` | array[string]/null | required, nullable | argv form, nonempty when present |
| `python_version`, `platform` | string/null | required, nullable | `null` when unavailable |
| `dependency_versions` | object/null | required, nullable | nonblank package/version pairs |
| `config_path`, `data_path`, `fold_artifact_path` | string/null | required, nullable | existence is not validated |
| `config_hash`, `data_hash`, `fold_artifact_hash` | string/null | required, nullable | exactly 64 lowercase hex characters |
| `data_generation_seed`, `cv_seed` | integer/null | required, nullable | zero or greater |
| `template_path`, `template_hash`, `generator_version` | string/null | optional, nullable | Phase 2 generation provenance; hash uses exact bytes |
| `approval_decision_path`, `approval_decision_hash` | string/null | optional, nullable | tracked Phase Gate evidence used by Full generation |
| `preprocessor_name`, `preprocessor_version` | string/null | required, nullable | identity or unavailable state |
| `model_name`, `model_parameters` | string/object/null | required, nullable | Phase 1 allows `null`; params must be JSON-compatible |
| `primary_metric` | string | optional | default `macro_f1`, nonblank |

All declared keys must be present when constructing a full manifest, even when
their value is `null`; this distinguishes an acquisition failure or
not-applicable field from an accidentally omitted implementation step.
Unknown keys and non-JSON model parameters are rejected.

## Hash convention

Every manifest hash is lowercase SHA-256 of the exact file bytes. No newline,
encoding, JSON key ordering, or path normalization is performed before hashing.
Use `sha256_file(path)` for files and `sha256_bytes(content)` for bytes.

## Examples

Valid pre-run manifest:

```json
{"run_id":"r1","created_at":"2026-07-31T04:00:00Z","git_commit":null,"git_dirty":null,"command":null,"python_version":null,"platform":null,"dependency_versions":{"pydantic":"2.13.4"},"config_path":"configs/phase1.yml","config_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","data_path":null,"data_hash":null,"data_generation_seed":42,"cv_seed":42,"fold_artifact_path":null,"fold_artifact_hash":null,"preprocessor_name":"english_minimal","preprocessor_version":"1.0.0","model_name":null,"model_parameters":null,"primary_metric":"macro_f1","output_directory":"outputs/runs/r1"}
```

This includes every field; unavailable Git/model values are honest `null`.
An uppercase, short, or nonhex hash is invalid.

## Future extension

Model and evaluation fields may become non-null once those phases are approved.
Do not make Phase 1 import a Git client, inspect the environment, or create a
run directory; acquisition belongs in a future explicit command.
