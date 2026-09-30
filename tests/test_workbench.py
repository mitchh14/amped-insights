"""The workbench: sources, blocks, one check verb, and taking AI text apart."""

import pytest

from anchor.core import CoreError

SMES = {"smes": ["Sam"]}


@pytest.fixture
def ws(make_store):
    s = make_store(SMES)
    sid = s.start_study("Why do shoppers leave checkout?", "Lee", decision="Fund autofill")["study"]["id"]
    return s, sid


def state(s, lid):
    return s.get(lid)["check"]["state"]


def test_blocks_cite_sources_in_their_workspace(ws, make_store):
    s, sid = ws
    src = s.add_source(sid, "Priya", "Funnel", "Cart 100, paid 42")["source"]
    lid = s.add("Conversion is 42 percent", "observation", "Priya", study_id=sid, source_ids=[src["id"]])["learning"]["id"]
    got = s.get(lid)
    assert got["source_ids"] == [src["id"]] and got["sources"][0]["title"] == "Funnel"
    assert not got["rests_on_nothing"]
    other = s.start_study("Another question", "Lee")["study"]["id"]
    with pytest.raises(CoreError, match="another workspace"):
        s.add("x is 1 here", "observation", "Priya", study_id=other, source_ids=[src["id"]])
    with pytest.raises(CoreError, match="kind"):
        s.add_source(sid, "Priya", "t", "b", kind="video")


def test_check_state_ladder(ws):
    s, sid = ws
    lid = s.add("Most drop off is on the address step", "observation", "Jordan", study_id=sid,
                origin="ai_agent", confidence="medium", why="From the funnel")["learning"]["id"]
    assert state(s, lid) == "needs_check"
    s.check(lid, "Jordan", statement="Most mobile drop off is on the address step")
    assert state(s, lid) == "checked_by_owner"
    assert s.get(lid)["statement"] == "Most mobile drop off is on the address step"
    s.check(lid, "Priya")
    assert state(s, lid) == "checked_by_peers"
    s.check(lid, "Sam", how="source_data")
    assert state(s, lid) == "checked_by_sme"
    s.check(lid, "Lee", "needs_changes", note="Say which step")
    assert state(s, lid) == "needs_changes"
    s.check(lid, "Dana", "disagree", note="Payment step is worse")
    assert state(s, lid) == "disagreement"


def test_check_routes_by_who_is_checking(ws):
    s, sid = ws
    lid = s.add("Shoppers find the form long", "finding", "Jordan", study_id=sid, origin="ai_agent")["learning"]["id"]
    with pytest.raises(CoreError, match="Jordan checks this AI draft first"):
        s.check(lid, "Sam")
    with pytest.raises(CoreError, match="change the wording"):
        s.check(lid, "Jordan", "disagree")
    s.check(lid, "Jordan")
    with pytest.raises(CoreError, match="already stand behind"):
        s.check(lid, "Jordan")
    s.check(lid, "Sam", "needs_changes", note="Which form?")
    with pytest.raises(CoreError, match="change the wording to answer"):
        s.check(lid, "Jordan")
    new = s.check(lid, "Jordan", statement="Shoppers find the address form long")["learning"]
    assert new["id"] != lid and new["revises"]["id"] == lid
    assert state(s, lid) == "replaced" and state(s, new["id"]) == "checked_by_owner"
    with pytest.raises(CoreError, match="verdict"):
        s.check(new["id"], "Sam", "maybe")


def test_unchecked_parts_flag_what_is_built_on_them(ws):
    s, sid = ws
    src = s.add_source(sid, "Sam", "Interviews", "6 of 8 said typing is tedious")["source"]["id"]
    ok = s.add("6 of 8 said typing is tedious", "observation", "Sam", study_id=sid, source_ids=[src])["learning"]["id"]
    draft = s.add("2 said the keyboard hid fields", "observation", "Jordan", study_id=sid, source_ids=[src],
                  origin="ai_agent")["learning"]["id"]
    finding = s.add("Typing an address on a phone is the problem", "finding", "Jordan", [ok, draft], sid)["learning"]["id"]
    insight = s.add("Autofill is our biggest win", "insight", "Jordan", [finding], sid)["learning"]["id"]
    assert s.get(finding)["unchecked_parts"] == 1 and s.get(finding)["unchecked_ids"] == [draft]
    assert s.get(insight)["unchecked_parts"] == 0 and s.get(insight)["deep_unchecked"] == 1
    s.check(draft, "Jordan")
    assert s.get(finding)["unchecked_parts"] == 0 and s.get(insight)["deep_unchecked"] == 0


def test_built_on_follows_the_newest_version(ws):
    s, sid = ws
    src = s.add_source(sid, "Sam", "Notes", "S7 wants Apple Pay")["source"]["id"]
    obs = s.add("2 shoppers want Apple Pay", "observation", "Jordan", study_id=sid, source_ids=[src])["learning"]["id"]
    finding = s.add("Payment options matter", "finding", "Jordan", [obs], sid)["learning"]["id"]
    s.check(obs, "Lee", "needs_changes", note="It was 1 shopper")
    assert s.get(finding)["unchecked_parts"] == 1
    new = s.check(obs, "Jordan", statement="1 shopper wants Apple Pay")["learning"]["id"]
    block = next(b for b in s.get_workspace(sid)["blocks"] if b["id"] == finding)
    assert block["built_on"] == [new] and block["unchecked_parts"] == 0
    assert s.get(new)["source_ids"] == [src]


def test_rests_on_nothing(ws):
    s, sid = ws
    obs = s.add("Conversion is 42 percent", "observation", "Priya", study_id=sid)
    assert "rests on nothing" in obs["warnings"][0] and obs["learning"]["rests_on_nothing"]
    finding = s.add("People leave", "finding", "Priya", study_id=sid)["learning"]
    assert finding["rests_on_nothing"]
    assert not s.add("It is the form", "finding", "Priya", [obs["learning"]["id"]], sid)["learning"]["rests_on_nothing"]


def test_ai_confidence_is_kept_apart_from_checks(ws):
    s, sid = ws
    out = s.add("Autofill doubles conversion", "insight", "Jordan", study_id=sid, origin="ai_agent")
    assert any("how confident" in w for w in out["warnings"])
    lid = s.add("Autofill helps", "insight", "Jordan", study_id=sid, origin="ai_agent", confidence="Low",
                why="One data source", assumes="Returning shoppers are like new ones")["learning"]["id"]
    got = s.get(lid)
    assert (got["confidence"], got["why"], got["assumes"]) == ("low", "One data source",
                                                               ["Returning shoppers are like new ones"])
    assert got["check"]["state"] == "needs_check"
    with pytest.raises(CoreError, match="confidence"):
        s.add("x is 1 or so", "observation", "Jordan", study_id=sid, confidence="certain")


def test_add_blocks_builds_on_earlier_refs(ws):
    s, sid = ws
    src = s.add_source(sid, "Jordan", "Funnel", "Address form: 39 percent leave")["source"]["id"]
    out = s.add_blocks(sid, "Jordan", [
        {"ref": "a", "level": "observation", "statement": "39 percent leave on the address form",
         "sources": [src], "confidence": "high", "why": "Read off the funnel"},
        {"ref": "b", "level": "finding", "statement": "The address form is the main leak",
         "built_on": ["a"], "confidence": "medium", "why": "Largest single drop", "assumes": ["The funnel is complete"]},
    ], origin="person_with_ai")
    a, b = out["refs"]["a"], out["refs"]["b"]
    assert s.get(b)["evidence_ids"] == [a] and s.get(b)["assumes"] == ["The funnel is complete"]
    assert all(s.get(i)["stage"] == "draft" for i in out["ids"])
    with pytest.raises(CoreError, match="not an earlier ref"):
        s.add_blocks(sid, "Jordan", [{"level": "finding", "statement": "x is y", "built_on": ["zzz"]}])


def test_break_down_takes_ai_text_apart(ws):
    s, sid = ws
    text = """Checkout summary (drafted by an AI assistant)

    Summary:
    - Mobile checkout conversion is 42 percent.
    - Most shoppers leave because the address form is clearly too long.
    We should prioritize address autofill next quarter."""
    out = s.break_down(sid, "Jordan", text)
    blocks = out["blocks"]
    assert [b["level"] for b in blocks] == ["observation", "finding", "insight"]
    assert out["source"]["kind"] == "ai_text" and out["source"]["body"] == text
    assert all(b["check"]["state"] == "needs_check" and b["origin"] == "ai_agent" for b in blocks)
    assert blocks[0]["source_ids"] == [out["source"]["id"]] and not blocks[0]["rests_on_nothing"]
    assert blocks[1]["rests_on_nothing"] and blocks[2]["rests_on_nothing"]
    said = " ".join(blocks[1]["assumes"])
    assert '"most" without a number' in said and '"clearly"' in said and "cause" in said
    assert "2 of 3 claims rest on nothing" in out["warnings"][0]
    with pytest.raises(CoreError, match="no claims"):
        s.break_down(sid, "Jordan", "Summary:\n# Heading")


def test_workspace_base_and_package(ws):
    s, sid = ws
    w = s.get_workspace(sid)
    assert [p["ok"] for p in w["base"]] == [True, False, False, False]
    s.update_study(sid, "Lee", method="Funnel and interviews", notes="Excludes app traffic")
    for t in ("A", "B"):
        s.add_source(sid, "Lee", t, "text")
    assert all(p["ok"] for p in s.get_workspace(sid)["base"])
    obs = s.add("x is 1 in the data", "observation", "Lee", study_id=sid)["learning"]["id"]
    ins = s.add("Do the thing", "insight", "Lee", [obs], sid)["learning"]["id"]
    with pytest.raises(CoreError, match="not a current insight"):
        s.set_package(sid, "Lee", [obs])
    assert s.set_package(sid, "Lee", [ins, ins])["package"] == [ins]
    w = s.get_workspace(sid)
    assert w["package"] == [ins] and w["counts"]["checked_by_owner"] == 2
    assert s.list_studies()[0]["counts"]["checked_by_owner"] == 2


def test_needs_check_orders_what_is_waiting(ws):
    s, sid = ws
    mine = s.add("Draft by AI here", "observation", "Sam", study_id=sid, origin="ai_agent")["learning"]["id"]
    theirs = s.add("Jordan wrote this one", "observation", "Jordan", study_id=sid)["learning"]["id"]
    asked = s.add("Priya wants a look", "observation", "Priya", study_id=sid)["learning"]["id"]
    s.ask_for_review(asked, "Priya", people=["Sam"])
    items = s.needs_check("Sam", sid)["items"]
    assert [i["id"] for i in items] == [mine, asked, theirs]
    s.check(theirs, "Sam")
    assert theirs not in [i["id"] for i in s.needs_check("Sam")["items"]]
