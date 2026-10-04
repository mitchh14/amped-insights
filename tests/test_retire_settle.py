"""Retiring blocks, settling conflicts, and sources kept as links with a spot."""

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


def block(s, sid, text, level="observation", owner="Priya", **kw):
    return s.add(text, level, owner, study_id=sid, **kw)["learning"]["id"]


# -- retiring ---------------------------------------------------------------

def test_retire_takes_a_block_out_of_use_without_erasing_it(ws):
    s, sid = ws
    o = block(s, sid, "Mobile conversion is 38 percent")
    f = block(s, sid, "Mobile shoppers convert less than desktop shoppers", "finding", evidence=[o])
    with pytest.raises(CoreError, match="say why"):
        s.retire(o, "Lee")
    out = s.retire(o, "Lee", "Out of date")
    assert out["learning"]["stage"] == "retired" and out["learning"]["check"]["state"] == "retired"
    assert out["learning"]["retired"]["reason"] == "Out of date"
    assert "rest on a retired block" in out["warnings"][0]
    # Still in the workspace, marked, so it can be shown and brought back.
    blocks = {b["id"]: b for b in s.get_workspace(sid)["blocks"]}
    assert blocks[o]["check"]["state"] == "retired"
    assert blocks[f]["rests_on_retired"] == [o]
    # Out of searches, and nothing new can rest on it or check it.
    assert all(x["id"] != o for x in s.query("conversion"))
    assert [x["id"] for x in s.query("conversion", trust="retired")] == [o]
    with pytest.raises(CoreError, match="retired"):
        s.add("Desktop converts better", "finding", "Priya", evidence=[o], study_id=sid)
    with pytest.raises(CoreError, match="retired"):
        s.check(o, "Sam")
    with pytest.raises(CoreError, match="retired"):
        s.revise(o, "Priya", "Mobile conversion is 39 percent")
    with pytest.raises(CoreError, match="already retired"):
        s.retire(o, "Lee", "Wrong")
    assert any(e["kind"] == "retired" for e in s.history(o))


def test_retire_with_a_replacement_can_move_what_rests_on_it(ws):
    s, sid = ws
    old = block(s, sid, "Mobile conversion is 38 percent")
    new = block(s, sid, "Mobile conversion is 42 percent")
    f = block(s, sid, "Mobile shoppers convert less than desktop shoppers", "finding", evidence=[old])
    with pytest.raises(CoreError, match="say which block replaces it"):
        s.retire(old, "Lee", "Out of date", move=True)
    out = s.retire(old, "Lee", replaced_by=new, move=True)
    assert out["learning"]["retired"]["reason"] == f"Replaced by #{new}"
    assert out["moved"] == [f] and out["warnings"] == []
    got = s.get(f)
    assert got["evidence_ids"] == [new] and got["rests_on_retired"] == []


def test_bring_back_restores_the_stage_it_had(ws):
    s, sid = ws
    draft = block(s, sid, "Shoppers hate the zip field", owner="Jordan", origin="ai_agent",
                  confidence="low", why="One quote")
    s.retire(draft, "Jordan", "A mistake")
    assert s.bring_back(draft, "Jordan")["learning"]["stage"] == "draft"
    with pytest.raises(CoreError, match="not retired"):
        s.bring_back(draft, "Jordan")


def test_retiring_a_block_used_in_a_decision_warns_the_decision(ws):
    s, sid = ws
    i = block(s, sid, "Address entry is our biggest fixable loss", "insight",
              evidence=[block(s, sid, "39 percent leave at the address form")])
    s.check(i, "Sam")
    s.log_decision("Fund autofill", "Jordan", [i])
    s.retire(i, "Lee", "Wrong")
    assert any(item["kind"] == "decision_at_risk" for item in s.digest("Jordan")["items"])


def test_a_retired_insight_leaves_the_package(ws):
    s, sid = ws
    i = block(s, sid, "Address entry is our biggest fixable loss", "insight",
              evidence=[block(s, sid, "39 percent leave at the address form")])
    s.set_package(sid, "Lee", [i])
    s.retire(i, "Lee", "Out of scope")
    assert s.get_workspace(sid)["package"] == []


# -- settling conflicts -----------------------------------------------------

@pytest.fixture
def clash(ws):
    s, sid = ws
    a = block(s, sid, "Adding Apple Pay would fix most mobile drop-off", "finding", owner="Jordan",
              evidence=[block(s, sid, "One shopper asked for Apple Pay")])
    b = block(s, sid, "The address step loses more shoppers than any other step", "finding",
              evidence=[block(s, sid, "39 percent leave at the address form")])
    up = block(s, sid, "A wallet is a smaller win than autofill", "insight", owner="Lee", evidence=[a])
    s.check(b, "Sam")
    s.link(a, b, "conflicts_with", "Dana", "The funnel says the loss is at the address step")
    cid = s.get_workspace(sid)["conflicts"][0]["id"]
    return s, sid, a, b, up, cid


def test_an_open_conflict_shows_in_the_workspace(clash):
    s, sid, a, b, _, cid = clash
    c = s.get_workspace(sid)["conflicts"][0]
    assert {c["a"]["id"], c["b"]["id"]} == {a, b} and c["status"] == "open"
    assert state(s, a) == state(s, b) == "disagreement"
    assert s.get(a)["conflicts"][0]["id"] == cid


def test_settle_one_holds_retires_the_other(clash):
    s, sid, a, b, up, cid = clash
    with pytest.raises(CoreError, match="note is required"):
        s.settle_conflict(cid, "Sam", "one_holds", "", keep=b)
    with pytest.raises(CoreError, match="keep must be"):
        s.settle_conflict(cid, "Sam", "one_holds", "Funnel wins", keep=up)
    out = s.settle_conflict(cid, "Sam", "one_holds", "The funnel is 30 days of data", keep=b)
    assert out["retired"] == a and out["conflict"]["status"] == "settled"
    assert out["conflict"]["outcome_label"] == "One holds"
    assert state(s, a) == "retired" and state(s, b) == "checked_by_sme"
    assert s.get(a)["retired"]["replaced_by"] == b
    assert s.get(up)["rests_on_retired"] == [a]
    assert s.get_workspace(sid)["conflicts"] == []
    with pytest.raises(CoreError, match="already settled"):
        s.settle_conflict(cid, "Sam", "not_a_conflict", "x")


def test_settle_both_hold_writes_scoped_versions(clash):
    s, sid, a, b, _, cid = clash
    with pytest.raises(CoreError, match="new wording"):
        s.settle_conflict(cid, "Sam", "both_hold", "Different groups", statements={"a": ""})
    out = s.settle_conflict(cid, "Sam", "both_hold", "Different groups",
                            statements={"a": "For shoppers who already use a wallet, Apple Pay would fix most drop-off"})
    new_a = out["revised"]["a"]
    assert s.get(a)["stage"] == "replaced" and s.get(new_a)["statement"].startswith("For shoppers")
    assert state(s, b) == "checked_by_sme"


def test_settle_not_a_conflict_clears_the_disagreement_and_can_be_flagged_again(clash):
    s, sid, a, b, _, cid = clash
    s.settle_conflict(cid, "Lee", "not_a_conflict", "One is about wallets, one about the address step")
    assert state(s, b) == "checked_by_sme"
    assert any(e["kind"] == "conflict_settled" for e in s.history(a))
    s.link(b, a, "conflicts_with", "Dana", "Looked again")
    assert state(s, b) == "disagreement"


def test_settle_cant_tell_yet_adds_a_question_and_stays_open(clash):
    s, sid, a, b, _, cid = clash
    out = s.settle_conflict(cid, "Sam", "cant_tell_yet", "We have no benchmark",
                            question="Does payment or the address form lose more shoppers?")
    assert out["conflict"]["status"] == "waiting"
    plan = s.get_workspace(sid)["plan"]
    assert plan[-1]["text"] == "Does payment or the address form lose more shoppers?"
    assert out["conflict"]["question_id"] == plan[-1]["id"]
    assert state(s, a) == state(s, b) == "disagreement"
    s.settle_conflict(cid, "Sam", "one_holds", "The new study answered it", keep=b)
    assert state(s, b) == "checked_by_sme"


# -- sources as links with a spot -------------------------------------------

def test_a_source_is_a_link_or_a_note(ws):
    s, sid = ws
    link = s.add_source(sid, "Priya", "Checkout funnel", url="https://looker.example/dash/funnel")["source"]
    assert link["kind"] == "link" and link["body"] is None and link["status"] == "ok"
    note = s.add_source(sid, "Sam", "Interview notes", "S1: Typing my address is a pain")["source"]
    assert note["kind"] == "note"
    with pytest.raises(CoreError, match="give a link"):
        s.add_source(sid, "Sam", "Empty")


def test_observations_say_the_spot_in_a_linked_source(ws):
    s, sid = ws
    src = s.add_source(sid, "Priya", "Checkout funnel", url="https://looker.example/dash/funnel")["source"]["id"]
    out = s.add("Mobile conversion is 42 percent", "observation", "Priya", study_id=sid, source_ids=[src])
    assert any("say where in the linked source" in w for w in out["warnings"])
    lid = out["learning"]["id"]
    assert s.get(lid)["no_spot"] == [src]
    s.set_spot(lid, "Sam", src, "Tile Funnel, row 6", receipt="Paid 5,040 (42%)")
    got = s.get(lid)
    assert got["no_spot"] == [] and got["sources"][0]["spot"]["spot"] == "Tile Funnel, row 6"
    assert got["sources"][0]["spot"]["receipt"] == "Paid 5,040 (42%)" and got["sources"][0]["spot"]["by"] == "Sam"
    assert any(e["kind"] == "spot_set" for e in s.history(lid))


def test_spots_can_be_given_when_adding_and_survive_a_new_version(ws):
    s, sid = ws
    src = s.add_source(sid, "Priya", "Replays", url="https://replays.example/p/40")["source"]["id"]
    ids = s.add_blocks(sid, "Jordan", [{"level": "observation", "statement": "12 of 40 replays show the keyboard covering a field",
                                        "spots": {str(src): "Playlist note 1"}, "confidence": "high", "why": "Counted"}])["ids"]
    got = s.get(ids[0])
    assert got["source_ids"] == [src] and got["no_spot"] == []
    s.check(ids[0], "Jordan")
    new = s.revise(ids[0], "Jordan", "12 of 40 replays show the keyboard covering the next field")["learning"]["id"]
    assert s.get(new)["sources"][0]["spot"]["spot"] == "Playlist note 1"
    with pytest.raises(CoreError, match="say where"):
        s.add("x is 1 here", "observation", "Priya", study_id=sid, spots={src: ""})


def test_people_report_what_they_found_at_a_link(ws):
    s, sid = ws
    src = s.add_source(sid, "Priya", "Teardown", url="https://figma.example/f/teardown")["source"]["id"]
    with pytest.raises(CoreError, match="status must be"):
        s.update_source(src, "Sam", status="gone")
    out = s.update_source(src, "Sam", status="broken", note="404")["source"]
    assert out["status"] == "broken" and out["status_by"] == "Sam"
    fixed = s.update_source(src, "Priya", url="https://figma.example/f/teardown-v2")["source"]
    assert fixed["status"] == "ok" and fixed["url"].endswith("v2")
    assert s.get_workspace(sid)["sources"][0]["url"].endswith("v2")
    with pytest.raises(CoreError, match="nothing to change"):
        s.update_source(src, "Priya")
