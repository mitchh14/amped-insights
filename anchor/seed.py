"""Sample data that walks the full research loop once, with a small team.

A study into mobile checkout produces data points and a hypothesis. A
reviewer asks for changes, the hypothesis is revised, validated, and
promoted to an insight. A stakeholder uses the insight in a decision, and
the decision raises a new question for research. Along the way an AI
agent's claim contradicts a validated finding and is flagged.

Used by scripts/seed.py and by the browser demo.
"""

from __future__ import annotations

from .core import Store

# The cast, and the role each holds on the team.
TEAM = {
    "Lee": "researcher",       # research lead
    "Sam": "researcher",
    "Dana": "trusted_reviewer",  # data science lead, outside the research team
    "Priya": "contributor",    # analytics
    "Jordan": "contributor",   # product manager
    "Morgan": "stakeholder",   # VP of product
}


def seed(s: Store) -> None:
    for name, role in TEAM.items():
        if s.whoami(name)["role"] != role:
            s.set_role(name, role, by="Lee")

    # Mode 1: plan a study tied to a decision.
    study = s.start_study(
        "Mobile checkout drop off", "Sam",
        objective="Find out why mobile shoppers leave checkout before paying",
        decision="Whether to fund address autofill in Q3",
        method="Funnel analysis and remote interviews",
        sample="30 days of mobile web sessions; 8 recent mobile shoppers",
        status="running",
    )["study"]["id"]

    # Mode 2: capture data points and a hypothesis.
    conv = s.propose("Mobile checkout conversion is 42 percent", "data_point", "Priya", study_id=study)["finding"]["id"]
    s.validate(conv, "Sam", "Matches the Q3 dashboard", basis="source_data")
    s.validate(conv, "Dana", "Rebuilt it from raw events", basis="reproduced")

    drop = s.propose("Most mobile checkout drop off happens on the address form step", "data_point",
                     "Priya", study_id=study)["finding"]["id"]
    s.validate(drop, "Sam", basis="source_data")

    quotes = s.propose("6 of 8 interviewed shoppers said typing an address on a phone is tedious",
                       "data_point", "Sam", study_id=study)["finding"]["id"]
    s.validate(quotes, "Lee", "Listened to the recordings", basis="evidence")

    hyp = s.propose("Shoppers abandon mobile checkout because the address form is too long",
                    "hypothesis", "Jordan", [conv, drop, quotes], study_id=study)["finding"]["id"]
    s.validate(hyp, "Sam", "Evidence lines up", basis="evidence")

    # Mode 5: a reviewer asks for changes, and the owner revises.
    s.validate(hyp, "Dana", "The app already has autofill. Scope this to mobile web.",
               outcome="changes_requested")
    hyp2 = s.revise(hyp, "Jordan",
                    "Shoppers abandon mobile web checkout because the address form is too long",
                    note="Scoped to mobile web, per Dana")["finding"]["id"]
    s.validate(hyp2, "Dana", "Scope is right now", basis="evidence")
    s.validate(hyp2, "Sam", basis="evidence")

    # Mode 3: promote the hypothesis to an insight.
    insight = s.promote(hyp2, "Lee", "Address autofill is the highest leverage fix for mobile web checkout",
                        note="Data, interviews, and a trusted review all point the same way")["finding"]["id"]
    s.validate(insight, "Dana", basis="evidence")
    s.request_validation(insight, "Lee", roles=["researcher"], note="One more research review before we lean on it")

    # Mode 4: an AI agent's claim contradicts a validated finding.
    contra = s.propose("Address form length does not affect mobile checkout abandonment",
                       "hypothesis", "Research agent (for Priya)", [conv])
    if contra["possible_conflicts"]:
        other = contra["possible_conflicts"][0]["finding"]["id"]
        s.confirm_conflict(contra["finding"]["id"], other, "Lee",
                           "An A/B test from last spring points the other way")

    # Mode 6: a stakeholder uses the insight in a decision.
    decision = s.log_decision(
        "Fund address autofill for mobile web in Q3", "Morgan", [insight],
        note="Biggest lever on mobile conversion we have evidence for",
    )["decision"]["id"]

    # Loop back: the decision raises a new question.
    s.request_research(
        "Would autofill also help returning shoppers who have a saved address?",
        "Morgan", from_decision_id=decision,
    )

    # Work still in progress elsewhere.
    guest = s.propose("Desktop shoppers prefer guest checkout over creating an account",
                      "hypothesis", "Jordan")["finding"]["id"]
    s.request_validation(guest, "Jordan", people=["Dana"])
    s.checkout(guest, "Sam")
