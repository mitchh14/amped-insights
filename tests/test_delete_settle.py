"""Deleting blocks, settling conflicts, and sources kept as links with a spot."""

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


# -- deleting ---------------------------------------------------------------

def test_delete_removes_a_block_and_what_rests_on_it_loses_it(ws):
    s, sid = ws
    o = block(s, sid, "Mobile conversion is 38 percent")
    keep = block(s, sid, "39 percent leave at the address form")
    f = block(s, sid, "Mobile shoppers drop off at the address form", "finding", evidence=[o, keep])
    s.check(o, "Sam", "needs_changes", note="Old number")
    new_o = s.revise(o, "Priya", "Mobile conversion is 42 percent")["learning"]["id"]
    s.set_package(sid, "Lee", [])
    out = s.delete(new_o, "Lee")
    assert out["deleted"] == new_o
    for gone in (o, new_o):  # the block and its earlier version
        with pytest.raises(CoreError, match="does not exist"):
            s.get(gone)
    assert s.get(f)["evidence_ids"] == [keep]
    assert all(b["id"] not in (o, new_o) for b in s.get_workspace(sid)["blocks"])
    assert "deleted" in [e["kind"] for e in s.activity()]
    assert any("deleted" in i["text"] for i in s.digest("Priya")["items"])  # its owner hears


def test_delete_can_move_what_rests_on_it(ws):
    s, sid = ws
    dup = block(s, sid, "39 percent leave at the address form", owner="Jordan")
    orig = block(s, sid, "39 percent of shoppers leave the address form")
    f = block(s, sid, "The address form loses the most shoppers", "finding", evidence=[dup])
    with pytest.raises(CoreError, match="cannot take its place"):
        s.delete(dup, "Lee", move_to=dup)
    assert s.delete(dup, "Lee", move_to=orig)["moved"] == [f]
    assert s.get(f)["evidence_ids"] == [orig]


def test_deleting_an_earlier_version_points_at_the_latest(ws):
    s, sid = ws
    o = block(s, sid, "Conversion is 38 percent")
    s.revise(o, "Priya", "Conversion is 42 percent")
    with pytest.raises(CoreError, match="earlier version"):
        s.delete(o, "Lee")


def test_deleting_a_block_used_in_a_decision_warns_the_decision(ws):
    s, sid = ws
    i = block(s, sid, "Address entry is our biggest fixable loss", "insight",
              evidence=[block(s, sid, "39 percent leave at the address form")])
    s.check(i, "Sam")
    s.set_package(sid, "Lee", [i])
    s.log_decision("Fund autofill", "Jordan", [i])
    s.delete(i, "Lee")
    assert s.get_workspace(sid)["package"] == []
    assert any(item["kind"] == "decision_at_risk" for item in s.digest("Jordan")["items"])


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


def test_settle_one_holds_deletes_the_other(clash):
    s, sid, a, b, up, cid = clash
    with pytest.raises(CoreError, match="note is required"):
        s.settle_conflict(cid, "Sam", "one_holds", "", keep=b)
    with pytest.raises(CoreError, match="keep must be"):
        s.settle_conflict(cid, "Sam", "one_holds", "Funnel wins", keep=up)
    out = s.settle_conflict(cid, "Sam", "one_holds", "The funnel is 30 days of data", keep=b, move=True)
    assert out["deleted"] == a and out["conflict"]["status"] == "settled"
    assert out["conflict"]["outcome_label"] == "One holds"
    assert state(s, b) == "checked_by_sme"
    assert s.get(up)["evidence_ids"] == [b]
    assert s.get_workspace(sid)["conflicts"] == []


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
    assert link["kind"] == "link" and link["body"] is None
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
    s.set_spot(lid, "Sam", src, "Tile Funnel, row 6")
    got = s.get(lid)
    assert got["no_spot"] == [] and got["sources"][0]["spot"] == "Tile Funnel, row 6"
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
    assert s.get(new)["sources"][0]["spot"] == "Playlist note 1"
    with pytest.raises(CoreError, match="say where"):
        s.add("x is 1 here", "observation", "Priya", study_id=sid, spots={src: ""})


def test_fix_a_link_or_delete_a_source(ws):
    s, sid = ws
    src = s.add_source(sid, "Priya", "Teardown", url="https://figma.example/f/teardown")["source"]["id"]
    o = s.add("3 of 5 competitors offer address lookup", "observation", "Priya", study_id=sid,
              spots={src: "Frame 2"})["learning"]["id"]
    fixed = s.update_source(src, "Priya", url="https://figma.example/f/teardown-v2")["source"]
    assert fixed["url"].endswith("v2") and s.get(o)["sources"][0]["spot"] == "Frame 2"
    with pytest.raises(CoreError, match="nothing to change"):
        s.update_source(src, "Priya")
    assert s.delete_source(src, "Lee")["cited_by"] == [o]
    got = s.get(o)
    assert got["source_ids"] == [] and got["rests_on_nothing"]
