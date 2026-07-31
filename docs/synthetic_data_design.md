# Synthetic data design

## Purpose

The Phase 2 dataset supports controlled evaluation of English inquiry routing
without using real customer or Rabiloo mail. It is designed to expose
preprocessing, content-leakage, grouping, and ambiguity risks before any model
is implemented. Synthetic scores will not be presented as production
performance.

Implementation:

- `src/mail_classification/generation/`
- `configs/phase2.yml`
- `assets/templates/email_templates.yml`
- `scripts/generate_smoke_data.py`
- `scripts/generate_pilot_data.py`

## Labels

| Label | Primary intent |
|---|---|
| `product_inquiry` | capability, compatibility, installation, and usage information |
| `technical_issue` | errors, outages, crashes, connection failures, or degraded operation |
| `billing` | charges, invoices, refunds, contracts, renewals, and payment methods |
| `account_support` | login, password, authentication, lockout, email, and profile settings |

Formal label names are never inserted into message text or generation metadata.
The `label` field is assigned from the primary requested action. A secondary
purpose is recorded as plain-language `metadata.secondary_intent`, not as a
formal class name.

## Difficulty

- `easy`: one direct intent with sufficient information.
- `medium`: indirect wording, missing detail, or vocabulary shared with another
  intent.
- `hard`: negation, ambiguity, multiple requests, or primary/secondary intents
  that require context.

Difficulty is authored per template group and does not depend on message
length. Pilot has an equal 32/32/32 easy/medium/hard distribution.

## Template groups and variations

There are 24 reviewed template groups: six per label. Each group has four
paired context/request/detail variations, producing 96 unique Pilot records.
Surface changes from shared greetings, closings, headers, signatures, quoted
replies, and urgency lines do not create a new group. `template_id`,
`template_group`, `variation_id`, seed, label, and difficulty remain
traceable in every record.

Shared component pools are label-neutral. The seeded generator independently
chooses greetings, senders, signatures, subjects, and structural flags.
Urgency options are assigned in a deterministic cycle within each label so
that chance cannot turn urgency into a class shortcut. The selected urgency
index is stored in metadata and its cross-class distribution is audited.
Terms such as `charge`, `account`, and `access` deliberately occur in more than
one semantic setting.

Each class includes negation and at least one multi-intent hard group. Examples
include paid-but-unavailable service, login plus cancellation, feature inquiry
plus an observed error, clarification rather than refund, correct password
with failed verification, configuration guidance rather than an outage, and a
profile-setting request paired with a secondary billing, feature, or technical
question.

## Stages

- Smoke: 8 records, at least two per label. Validates schema, persistence,
  traceability, deterministic hash, and basic checks.
- Pilot: 96 records, 24 per label. Runs the complete duplicate, leakage,
  statistics, and review-sample workflow.
- Full: configured as 800 and explicitly `enabled: false`. The generator
  refuses to run it. Human Pilot approval must be recorded before a later
  change enables it.

## Reproducibility

`random.Random(seed)` is initialized once per generation call. Candidate order,
IDs, component choices, text, labels, difficulty, metadata, and output JSONL
order are deterministic for the same configuration, seed, template bytes, and
generator version. `generated_at` is a configured timezone-aware constant.
Runtime time and Git state are stored only in the separate run manifest.

Hashes are lowercase SHA-256 of exact file bytes:

- Phase 2 YAML
- template YAML
- emitted JSONL

## Storage and Git policy

Canonical records are UTF-8 JSONL in `data/raw/`. Quality results are JSON/CSV
under `outputs/data_quality/`, and run manifests are under
`outputs/manifests/`. These reproducible generated artifacts are ignored by
Git. The generator, configuration, templates, tests, and contracts are tracked.

## Limitations

Authored templates cannot reproduce all vocabulary, thread history, noise,
social context, malicious content, or distribution shifts of real mail.
Balanced classes and difficulties are experimental controls, not a prediction
of production prevalence. Frequency checks cannot prove semantic independence.
The generated dataset requires human Pilot review and, eventually, evaluation
against appropriately governed real-world evidence outside this assignment.

No external service receives the data, and no real personal, customer, or
internal company information is used.
