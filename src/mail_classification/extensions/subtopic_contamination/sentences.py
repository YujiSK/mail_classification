"""Hand-authored subtopic sentence bank for the contamination Extension.

Each of the four Task 10 classes gets 12 candidate sentences that could be
inserted, as a secondary mention, into an email whose *main* label is one of
the other three classes. No single sentence is a give-away for the label or
for any contamination condition: styles are deliberately mixed (polite,
concise, negation, priority-explicit, defer-for-later, fact-only) so that
primary-intent clarity comes from the mix of rhetorical strategies, not from
one repeated phrase. Sentences avoid the literal class-name strings
(``billing``, ``technical_issue``, ``product_inquiry``, ``account_support``)
so the existing label-literal leakage check
(``mail_classification.quality.leakage.audit_leakage``) is not tripped by
intentional subtopic vocabulary.

Insertion position (early/mid/end within the body) is an independent axis
handled by ``insertion.py`` -- sentences here are written to read naturally
at any of the three positions.
"""

from __future__ import annotations

from dataclasses import dataclass

STYLES = ("polite", "concise", "negation", "priority", "defer", "fact")


@dataclass(frozen=True)
class SubtopicSentence:
    subtopic: str
    variant_id: int
    style: str
    text: str


_RAW_SENTENCES: dict[str, list[tuple[str, str]]] = {
    "billing": [
        ("polite", "I would also appreciate a quick update on a recent invoice, though that is not why I'm writing today."),
        ("polite", "If it's not too much trouble, could someone also take a look at a charge on my last statement?"),
        ("concise", "Also, quick note: my last invoice looked a bit higher than usual."),
        ("concise", "Small side note -- a charge on my account seems off."),
        ("negation", "This message isn't about my payment method, but I did notice an unfamiliar charge worth mentioning."),
        ("negation", "I'm not writing about payments specifically, though I did want to flag a recent charge for the record."),
        ("priority", "My main concern is the request above; I also have a smaller question about a recent charge, but that can wait."),
        ("priority", "The request above is what matters most to me right now -- the invoice question below is secondary."),
        ("defer", "Whenever it's convenient, I'd also like someone to glance at a charge on my account, but there's no rush."),
        ("defer", "No urgency at all, but at some point I'd like clarification on a line item from my last invoice."),
        ("fact", "For reference, my most recent invoice amount was slightly different from previous months."),
        ("fact", "For your records, my subscription is currently on the annual payment plan."),
    ],
    "account_support": [
        ("polite", "I would also be grateful for a quick check on my account access, though it isn't the main reason for this email."),
        ("polite", "If possible, could someone also confirm my login details are still active? Not urgent."),
        ("concise", "Also, small note -- I had trouble logging in once last week."),
        ("concise", "Side note: my account profile settings look slightly different than before."),
        ("negation", "This isn't about my login credentials, but I did want to mention I was briefly locked out recently."),
        ("negation", "I'm not reporting an account access problem here, just noting that verification asked twice in a row."),
        ("priority", "My main request is above; a minor account access question is secondary and can be addressed later."),
        ("priority", "What I really need help with is above -- the account settings question below is a lower priority."),
        ("defer", "There's no rush, but whenever convenient I'd like someone to check my account access history."),
        ("defer", "Feel free to leave this for later: I'd like eventual confirmation that my profile details are correct."),
        ("fact", "For reference, my account has been active under the same login for a couple of years."),
        ("fact", "For context, I recently updated my account recovery email."),
    ],
    "technical_issue": [
        ("polite", "I would also appreciate a look at a small error message I saw, though it isn't the main point of this email."),
        ("polite", "If someone has time, could they also check why a page loaded slowly for me once? Not urgent."),
        ("concise", "Also, quick note -- the app crashed once on my end."),
        ("concise", "Side note: I noticed a sync issue at one point."),
        ("negation", "This isn't a bug report, but I did notice a feature acted oddly on one occasion."),
        ("negation", "I'm not filing a technical complaint here, though a page did fail to load once during my last visit."),
        ("priority", "The request above is my priority; a minor glitch I noticed is secondary and not urgent."),
        ("priority", "Above is what matters most right now -- the small error message below can wait."),
        ("defer", "No rush at all, but at some point I'd like someone to look into a brief app slowdown I noticed."),
        ("defer", "Whenever convenient, feel free to check a minor sync delay I noticed; it's not blocking anything."),
        ("fact", "For reference, the issue I noticed happened on the latest version of the app."),
        ("fact", "For your information, I was using the mobile app when I noticed this."),
    ],
    "product_inquiry": [
        ("polite", "I would also appreciate some information on your other plans, though that isn't my main reason for writing."),
        ("polite", "If convenient, could someone also share details on upgrade options? No rush at all."),
        ("concise", "Also, quick question -- do you offer a higher-tier plan?"),
        ("concise", "Side note: I'm curious about feature availability on other plans."),
        ("negation", "This isn't a request to switch plans, but I was curious about pricing for a higher tier."),
        ("negation", "I'm not asking to upgrade right now, though I did want to ask whether a certain feature is included."),
        ("priority", "My main concern is above; a general question about plan options below is secondary."),
        ("priority", "What matters most is the request above -- the product question below can be answered whenever."),
        ("defer", "No urgency, but whenever convenient I'd like to hear more about your other plan options."),
        ("defer", "Feel free to reply about this later: I'm curious about compatibility with other tools."),
        ("fact", "For reference, I'm currently on the standard plan."),
        ("fact", "For context, I've been a subscriber for about a year."),
    ],
}

SUBTOPIC_SENTENCES: dict[str, tuple[SubtopicSentence, ...]] = {
    subtopic: tuple(
        SubtopicSentence(subtopic=subtopic, variant_id=index, style=style, text=text)
        for index, (style, text) in enumerate(variants)
    )
    for subtopic, variants in _RAW_SENTENCES.items()
}

SENTENCES_PER_SUBTOPIC = 12

for _subtopic, _variants in SUBTOPIC_SENTENCES.items():
    if len(_variants) != SENTENCES_PER_SUBTOPIC:
        raise ValueError(
            f"subtopic {_subtopic!r} has {len(_variants)} sentences, "
            f"expected {SENTENCES_PER_SUBTOPIC}"
        )
    if len({variant.style for variant in _variants}) != len(STYLES):
        raise ValueError(f"subtopic {_subtopic!r} does not cover all styles {STYLES}")
