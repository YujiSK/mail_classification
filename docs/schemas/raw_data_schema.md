# Raw data schema

## Purpose and storage

`RawMailRecord` is the canonical, immutable input contract for one future
synthetic inquiry email. The preferred storage is UTF-8 JSON Lines: one
`model_dump_json()` object per line. CSV is permitted only after `metadata` is
serialized as a JSON string and restored before validation.
No Phase 1 code generates records.

Implementation: `src/mail_classification/schemas/dataset.py`.

## Fields

| Field | JSON type | Required | Validation |
|---|---|---:|---|
| `id` | string | yes | nonblank |
| `raw_text` | string | yes | nonblank; preserved verbatim |
| `body_text` | string | yes | nonblank; separate from raw source |
| `label` | string enum | yes | `product_inquiry`, `technical_issue`, `billing`, `account_support` |
| `template_group` | string | yes | nonblank |
| `difficulty` | string enum | yes | `easy`, `medium`, `hard`, `ambiguous` |
| `has_header` | boolean | yes | header-presence provenance |
| `has_signature` | boolean | yes | signature-presence provenance |
| `has_quoted_reply` | boolean | yes | quoted-reply provenance |
| `generation_seed` | integer | yes | zero or greater |
| `template_id` | string | yes | nonblank |
| `variation_id` | integer | yes | zero or greater |
| `generated_at` | RFC 3339 string | yes | timezone-aware |
| `metadata` | object | no | strict JSON-compatible values; default `{}` |

Dataset records reject empty or whitespace-only `raw_text` and `body_text`.
The preprocessing API separately accepts them for robust inference and unit
testing. Extra fields, invalid enums, naive datetimes, sets, NaN, and other
non-JSON metadata are rejected.

## Examples

Valid:

```json
{"id":"m1","raw_text":"Subject: Help\nI cannot log in.","body_text":"I cannot log in.","label":"account_support","template_group":"login-1","difficulty":"medium","has_header":true,"has_signature":false,"has_quoted_reply":false,"generation_seed":42,"template_id":"account-01","variation_id":0,"generated_at":"2026-07-31T04:00:00Z","metadata":{"source":"synthetic"}}
```

Invalid: `{"id":"m1","raw_text":" ","label":"unknown"}` is incomplete, has a
blank source, and uses an unsupported label.

## Future extension

Additive fields require a schema-version decision and migration test. Do not
reuse `metadata` to bypass a stable field that evaluation needs. `raw_text`
must never be overwritten; new representations belong in separate derived
artifacts.

Pydantic v2 is used because one typed model provides nested validation, enum
enforcement, timezone checks, forbidden-extra-field handling, and JSON
round-trips without separate handwritten serializers and validators.
