# Human review guide

## Artifact

Review `outputs/data_quality/pilot_review_samples.csv`. It contains at least
ten records per class plus deterministic coverage for difficulties, shortest
and longest messages, negation, multi-intent text, headers, signatures, quoted
replies, and leakage candidates. Duplicate candidates are added when any
exist; a clean duplicate report means that selection reason is not applicable.

Fill only:

- `review_status`: suggested values `pass`, `revise`, or `reject`;
- `review_comment`: concise evidence and the rule/template that should change.

Do not edit `raw_text`, `body_text`, label, or generation metadata in the CSV.

## Review questions

For each record, check:

1. Is the assigned label the primary requested action?
2. Is the difficulty justified by intent structure rather than length alone?
3. Does the English read naturally enough for the intended experiment?
4. Is ambiguity purposeful, and is the primary intent still defensible?
5. Are negation and secondary intent interpreted correctly?
6. Does a formal label, template ID, artificial marker, sender, signature,
   subject, formatting habit, or metadata value disclose the label?
7. Does it look like a superficial copy of another group?
8. Could one token alone make the class trivial?
9. Are header, signature, and quoted reply plausible and independent of label?
10. Are the shortest and longest examples still credible?

Also review every informational row in
`pilot_leakage_findings.csv`. Decide whether a class-exclusive token/bigram is
legitimate intent vocabulary or an avoidable template artifact.

## Correcting problems

Never hand-edit generated records. Identify the responsible template,
component pool, threshold, or generation rule; update the tracked source; run
all tests; regenerate Smoke and Pilot; and repeat duplicate, leakage, hash, and
review extraction. Record both the reason and new hashes in the daily report.

If a label is disputable, revise the template's main request or primary label
at the source. If text is unnatural, revise the authored variation rather than
post-processing the output. If a structural leak is found, expand or rebalance
the shared pool across all classes.

## Approval

Full generation remains prohibited while any required row is unreviewed, any
row is marked `revise`/`reject`, any automatic error/warning remains, or
informational leakage candidates lack a documented decision. Human approval
must identify reviewer and time and be recorded outside the generated mail
body. Approval does not authorize model training; that belongs to Phase 3.

After review, preserve the completed CSV and write
`outputs/data_quality/pilot_review_decision.json` with the reviewer, review
time, decision, Pilot data hash, template-definition hash, review CSV hash,
row counts, and an explicit decision for every informational leakage
candidate. The automatically generated Pilot summary remains an immutable
pre-review artifact; the separate decision file records the later review
outcome.

Because `outputs/` is excluded from Git, copy the immutable approval evidence
to `docs/reviews/pilot_review_decision.json`. The tracked record is the Phase
Gate source of truth and must include the ignored decision JSON hash as well as
the Pilot data, template, review CSV, immutable review fields, and leakage
findings hashes.
