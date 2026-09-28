"""Sample data that walks the full research loop once, with a small team.

A study into mobile checkout produces observations and a finding drafted with
AI, which its owner confirms. A reviewer asks for changes, the finding is
revised, checked by an SME, and promoted to an insight. A stakeholder uses the
insight in a decision, and the decision raises a new question for research.
Along the way an AI agent's draft conflicts with a checked finding and is
flagged.

Used by scripts/seed.py and by the browser demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .core import Store

# The cast, and the role each holds on the team.
TEAM = {
    "Lee": "researcher",    # research lead
    "Sam": "researcher",
    "Dana": "pwdr",         # data science lead
    "Priya": "pwdr",        # analytics
    "Jordan": "pwdr",       # product manager
    "Morgan": "stakeholder",  # VP of product
}
# SMEs the team trusts most in this area: one researcher, one data science lead.
SMES = ("Sam", "Dana")


def seed(s: Store) -> None:
    for name, role in TEAM.items():
        s.set_person(name, "Lee", role=role, sme=name in SMES)

    # Plan a study tied to a decision, then run it.
    study = s.start_study("Why do mobile shoppers leave checkout before paying?", "Sam",
                          decision="Whether to fund address autofill in Q3")["study"]["id"]
    s.update_study(study, "Sam", status="running", method="Funnel analysis and remote interviews",
                   sample="30 days of mobile web sessions; 8 recent mobile shoppers")

    # Observations: what we saw.
    conv = s.add("Mobile checkout conversion is 42 percent", "observation", "Priya", study_id=study)["learning"]["id"]
    s.review(conv, "Sam", how="source_data", note="Matches the Q3 dashboard")
    s.review(conv, "Dana", how="reran", note="Rebuilt it from raw events")
    drop = s.add("Most mobile checkout drop off happens on the address form step", "observation", "Priya",
                 study_id=study)["learning"]["id"]
    s.review(drop, "Sam", how="source_data")
    quotes = s.add("6 of 8 interviewed shoppers said typing an address on a phone is tedious", "observation", "Sam",
                   study_id=study)["learning"]["id"]
    s.review(quotes, "Lee", how="evidence", note="Listened to the recordings")

    # A finding drafted with AI. Jordan checks it and fixes the wording before sharing.
    finding = s.add("Shoppers abandon checkout because forms are long", "finding", "Jordan",
                    [conv, drop, quotes], study, origin="person_with_ai")["learning"]["id"]
    s.confirm(finding, "Jordan", "Shoppers abandon mobile checkout because the address form is too long",
              note="Checked it against the quotes and narrowed it to the address form")
    s.review(finding, "Sam", how="evidence", note="Evidence lines up")

    # A reviewer asks for changes, and the owner revises.
    s.review(finding, "Dana", "changes", note="The app already has autofill. Scope this to mobile web.")
    finding2 = s.revise(finding, "Jordan", "Shoppers abandon mobile web checkout because the address form is too long",
                        note="Scoped to mobile web, per Dana")["learning"]["id"]
    s.review(finding2, "Dana", how="evidence", note="Scope is right now")
    s.review(finding2, "Sam", how="evidence")

    # Promote the finding to an insight.
    insight = s.promote(finding2, "Lee", "Address autofill is the highest leverage fix for mobile web checkout",
                        note="Data, interviews, and an SME review all point the same way")["learning"]["id"]
    s.review(insight, "Dana", how="evidence")
    s.ask_for_review(insight, "Lee", roles=["sme"], note="One more SME review before we lean on it")

    # An AI agent's draft, confirmed by Priya, conflicts with the checked finding.
    agent = s.add("Address form length does not affect mobile checkout abandonment", "finding", "Priya", [conv],
                  origin="ai_agent")["learning"]["id"]
    s.confirm(agent, "Priya", note="Matches an A/B test from last spring")
    s.link(agent, finding2, "conflicts_with", "Lee", note="The spring A/B test points the other way")

    # A stakeholder uses the insight in a decision, a while ago now.
    decision = s.log_decision("Fund address autofill for mobile web in Q3", "Morgan", [insight],
                              note="Biggest lever on mobile conversion we have evidence for")["decision"]["id"]
    with s._conn() as conn:  # sample data only: date the decision so its outcome is due
        then = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(timespec="seconds")
        conn.execute("UPDATE decisions SET at = ? WHERE id = ?", (then, decision))

    # Loop back: the decision raises a new question.
    s.ask_for_research("Would autofill also help returning shoppers who have a saved address?", "Morgan",
                       from_decision_id=decision)

    # Work still in progress elsewhere.
    guest = s.add("Desktop shoppers prefer guest checkout over creating an account", "finding", "Jordan")["learning"]["id"]
    s.ask_for_review(guest, "Jordan", people=["Dana"])
    s.working_on(guest, "Sam")
    s.add("Returning shoppers skip the address step when their address is saved", "finding", "Jordan",
          [drop], origin="person_with_ai")
