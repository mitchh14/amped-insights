"""Sample data: one workspace mid-way through, so every state in the workbench shows.

A small team asks why mobile shoppers leave checkout. They collect context
(a funnel query, interview notes, a data export), and AI drafts blocks from it,
each saying how confident it is, why, and what it assumes. People check the
blocks. Some are checked by owners, peers, or an SME; two AI drafts still wait
for their owners; one observation needs changes; and one finding built on a
single quote draws a disagreement. A checked insight sits in the package.

Used by scripts/seed.py and by the browser demo.
"""

from __future__ import annotations

from .core import Store

# The cast, and the role each holds on the team.
TEAM = {
    "Lee": "researcher",    # research lead
    "Sam": "researcher",
    "Dana": "pwdr",         # data science lead
    "Priya": "pwdr",        # analytics
    "Jordan": "pwdr",       # product manager
}
# SMEs the team trusts most in this area: one researcher, one data science lead.
SMES = ("Sam", "Dana")

SOURCES = {
    "funnel": ("query", "Checkout funnel, last 30 days", "Priya",
               "Mobile web, Aug 29 to Sep 27.\nCart 12,000\nStarted address form 10,900\n"
               "Finished address form 6,650\nReached payment 5,600\nPaid 5,040 (42%)"),
    "int1": ("note", "Interviews, shoppers 1 to 4", "Sam",
             "S1: \"Typing my whole address with my thumbs, no thanks.\"\n"
             "S2: \"The keyboard kept covering the zip field.\"\n"
             "S3: \"I gave up and finished on my laptop.\"\n"
             "S4: \"It is tedious. I only do it if I really want the thing.\""),
    "int2": ("note", "Interviews, shoppers 5 to 8", "Sam",
             "S5: \"Address was fine, I have it saved.\"\n"
             "S6: \"The form is long on a phone.\"\n"
             "S7: \"I would have used Apple Pay if it was there.\"\n"
             "S8: \"Typing it out is a pain. Keyboard jumped around.\""),
    "split": ("data", "Returning vs new shoppers", "Priya",
              "Returning shoppers: 31% of mobile checkouts, 61% pay.\n"
              "New shoppers: 69% of mobile checkouts, 34% pay.\n"
              "Returning shoppers with a saved address skip the address step."),
}


def seed(s: Store) -> None:
    for name, role in TEAM.items():
        s.set_person(name, "Lee", role=role, sme=name in SMES)

    ws = s.start_study("Why do mobile shoppers leave checkout before paying?", "Sam",
                       decision="Whether to fund address autofill in Q3")["study"]["id"]
    s.update_study(ws, "Sam", status="running",
                   method="Funnel analysis of 30 days of mobile web sessions, plus 8 remote interviews "
                          "with recent mobile shoppers.")
    src = {key: s.add_source(ws, by, title, body, kind)["source"]["id"]
           for key, (kind, title, by, body) in SOURCES.items()}

    def block(statement, level, owner, *, sources=(), on=(), ai=False, confidence=None, why=None, assumes=()):
        return s.add(statement, level, owner, list(on), ws, "ai_agent" if ai else "person",
                     [src[k] for k in sources], confidence, why, list(assumes))["learning"]["id"]

    # Observations: what we saw, each taken from a source.
    o1 = block("Mobile checkout conversion is 42 percent", "observation", "Priya", sources=["funnel"])
    s.check(o1, "Sam", how="source_data", note="Matches the dashboard")

    o2 = block("39 percent of shoppers who start the address form leave before finishing it", "observation",
               "Jordan", sources=["funnel"], ai=True, confidence="high",
               why="Worked out from the funnel: 10,900 started the form, 6,650 finished it")
    s.check(o2, "Jordan", note="Did the math again from the funnel")

    o3 = block("6 of 8 shoppers said typing an address on a phone is tedious", "observation", "Sam",
               sources=["int1", "int2"])
    s.check(o3, "Lee", how="evidence", note="Listened to the recordings")

    o4 = block("2 shoppers said the keyboard covered or moved the form fields", "observation", "Jordan",
               sources=["int1", "int2"], ai=True, confidence="medium", why="S2 and S8 describe it",
               assumes=["The keyboard problem happens on most phones, not just theirs"])

    o7 = block("2 shoppers said they would pay with Apple Pay if offered", "observation", "Jordan",
               sources=["int2"], ai=True, confidence="low", why="Read from the interview notes",
               assumes=["Other shoppers feel the same as the one who said it"])
    s.check(o7, "Jordan")
    s.check(o7, "Lee", "needs_changes", note="Only S7 said this. It is 1 shopper, not 2.")

    o5 = block("Returning shoppers pay 61 percent of the time, new shoppers 34 percent", "observation", "Priya",
               sources=["split"], ai=True, confidence="high", why="Straight from the export")
    s.check(o5, "Priya", note="Checked against the export")
    s.check(o5, "Dana", how="reran", note="Rebuilt it from raw events")

    o6 = block("Returning shoppers with a saved address skip the address step", "observation", "Priya",
               sources=["split"], ai=True, confidence="medium", why="Stated in the export notes",
               assumes=["A saved address always skips the step, on every device"])

    # Findings: what the observations mean, built on them.
    f1 = block("Shoppers abandon checkout because forms are long", "finding", "Jordan", on=[o2, o3, o4], ai=True,
               confidence="medium", why="The funnel and the interviews point the same way",
               assumes=["The 8 people we interviewed are like most mobile shoppers"])
    s.check(f1, "Jordan", statement="Shoppers leave mobile checkout mainly because the address form is hard "
                                    "to fill in on a phone",
            note="Narrowed it to the address form, which is what the evidence shows")
    s.check(f1, "Sam", how="evidence", note="Funnel and interviews agree")

    f3 = block("Adding Apple Pay would fix most mobile checkout drop-off", "finding", "Jordan", on=[o7], ai=True,
               confidence="low", why="One shopper asked for it",
               assumes=["What one shopper wants, most shoppers want"])
    s.check(f3, "Jordan")
    s.check(f3, "Dana", "disagree", note="One quote cannot carry this. The funnel says the loss is at the address step.")

    f2 = block("Not having to type an address roughly doubles the chance a shopper pays", "finding", "Priya",
               on=[o5, o6])
    s.check(f2, "Lee", how="evidence")

    # Insights: what it means for us and what to do.
    i1 = block("Address autofill is likely our biggest mobile checkout win", "insight", "Jordan", on=[f1, f2])
    s.check(i1, "Sam", how="judgment", note="Strong. Check the two open observations before the pitch.")

    block("Test autofill with returning shoppers first, where the gain is easiest to measure", "insight", "Priya",
          on=[f2], ai=True, confidence="medium", why="Returning shoppers are the group we can measure fastest",
          assumes=["Returning shoppers react to autofill the same way new ones would"])

    s.set_package(ws, "Jordan", [i1])
