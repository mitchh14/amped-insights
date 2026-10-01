"""The plan: sub-questions a workspace needs answered, and what is already known."""

import pytest

from anchor.core import CoreError

SMES = {"smes": ["Sam"]}


@pytest.fixture
def ws(make_store):
    s = make_store(SMES)
    sid = s.start_study("Why do mobile shoppers leave checkout?", "Lee", decision="Fund autofill in Q3")["study"]["id"]
    return s, sid


def test_sub_questions_build_the_plan(ws):
    s, sid = ws
    out = s.add_question(sid, "Lee", "Where in checkout do mobile shoppers stop?", expect="The address step")
    q1 = out["question"]["id"]
    q2 = s.add_question(sid, "Priya", "Would autofill cut address typing?")["question"]["id"]
    plan = s.get_workspace(sid)["plan"]
    assert [q["id"] for q in plan] == [q1, q2]
    assert plan[0]["expect"] == "The address step" and plan[0]["state"] == "open"
    assert s.get_workspace(sid)["base"][0] == {"key": "plan", "label": "The plan", "count": 2, "ok": True}
    s.update_question(q2, "Lee", position=1, text="Would autofill cut address typing on mobile?")
    plan = s.get_workspace(sid)["plan"]
    assert [q["id"] for q in plan] == [q2, q1] and plan[0]["text"].endswith("on mobile?")
    with pytest.raises(CoreError, match="does not exist"):
        s.update_question(999, "Lee", text="x")
    for i in range(4):
        warnings = s.add_question(sid, "Lee", f"Extra question number {i}")["warnings"]
    assert warnings and "sub-questions" in warnings[0]


def test_state_follows_the_blocks_that_answer(ws):
    s, sid = ws
    q = s.add_question(sid, "Lee", "Where do shoppers stop?")["question"]["id"]
    obs = s.add("7 of 12 left at the address form", "observation", "Lee", study_id=sid)["learning"]["id"]
    with pytest.raises(CoreError, match="only a finding or an insight"):
        s.set_answers(obs, "Lee", q)
    f = s.add("Typing a full address drives drop off", "finding", "Lee", [obs], sid, question_id=q)["learning"]["id"]
    assert s.get_workspace(sid)["plan"][0]["state"] == "in_progress"
    ins = s.promote(f, "Lee", "Autofill is our biggest checkout win")["learning"]["id"]
    plan = s.get_workspace(sid)["plan"][0]
    assert plan["block_ids"] == [f, ins] and plan["state"] == "in_progress"  # only the owner stands behind it
    s.check(ins, "Sam")
    plan = s.get_workspace(sid)["plan"][0]
    assert plan["state"] == "answered" and plan["answered_by"] == [ins]
    assert s.list_studies()[0]["plan"] == {"total": 1, "answered": 1, "label": "1 of 1 answered"}
    assert s.get(ins)["answers"]["text"] == "Where do shoppers stop?"
    # A new version keeps answering the same sub-question.
    s.check(ins, "Dana", "needs_changes", note="Say mobile")
    new = s.check(ins, "Lee", statement="Autofill is our biggest mobile checkout win")["learning"]["id"]
    assert s.get(new)["answers"]["id"] == q
    assert s.get_workspace(sid)["plan"][0]["block_ids"] == [f, new]


def test_set_answers_and_remove(ws):
    s, sid = ws
    q = s.add_question(sid, "Lee", "Where do shoppers stop?")["question"]["id"]
    f = s.add("Shoppers stop at the address form", "finding", "Priya", study_id=sid)["learning"]["id"]
    out = s.set_answers(f, "Jordan", q)
    assert out["learning"]["question_id"] == q and out["plan"][0]["state"] == "in_progress"
    assert s.get(f)["check"]["state"] == "checked_by_owner"  # answering is not a check
    assert s.history(f)[-1]["kind"] == "answers_set"
    other = s.start_study("Another question here", "Lee")["study"]["id"]
    q_other = s.add_question(other, "Lee", "Something else entirely")["question"]["id"]
    with pytest.raises(CoreError, match="another workspace"):
        s.set_answers(f, "Lee", q_other)
    out = s.remove_question(q, "Lee")
    assert out["untagged"] == [f] and out["plan"] == []
    assert s.get(f)["answers"] is None
    assert any(e["kind"] == "question_removed" for e in s.get_study(sid)["history"])


def test_already_known_comes_from_other_workspaces(ws):
    s, sid = ws
    older = s.start_study("What slows down checkout?", "Priya")["study"]["id"]
    checked = s.add("Shoppers abandon the address form on mobile", "finding", "Priya", study_id=older)["learning"]["id"]
    s.check(checked, "Sam")
    draft = s.add("Mobile shoppers abandon the address form", "finding", "Priya", study_id=older,
                  origin="ai_agent")["learning"]["id"]
    here = s.add("Shoppers abandon the mobile address form", "finding", "Lee", study_id=sid)["learning"]["id"]
    q = s.add_question(sid, "Lee", "Do mobile shoppers abandon the address form?")["question"]["id"]
    known = s.get_workspace(sid)["plan"][0]["already_known"]
    ids = [b["id"] for b in known]
    assert ids == [checked]  # not the draft, not this workspace's own block
    assert known[0]["check"]["state"] == "checked_by_sme" and known[0]["workspace"]["id"] == older
    assert s.already_known(q)["blocks"][0]["id"] == checked
    assert draft not in ids and here not in ids


def test_add_blocks_can_answer(ws):
    s, sid = ws
    q = s.add_question(sid, "Lee", "Where do shoppers stop?")["question"]["id"]
    src = s.add_source(sid, "Lee", "Funnel", "Cart 100, address 60, paid 42")["source"]["id"]
    out = s.add_blocks(sid, "Lee", [
        {"ref": "o", "level": "observation", "statement": "40 of 100 left at address", "sources": [src]},
        {"level": "finding", "statement": "Address is the main stop", "built_on": ["o"], "answers": q}])
    assert s.get(out["ids"][1])["answers"]["id"] == q
    assert s.get_workspace(sid)["plan"][0]["block_ids"] == [out["ids"][1]]
