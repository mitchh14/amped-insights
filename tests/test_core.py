import sqlite3

import pytest

from anchor.core import CoreError, Store


def test_add_starts_shared_and_not_reviewed(store):
    f = store.add("Mobile checkout conversion is 42 percent", "observation", "ana")["learning"]
    assert (f["stage"], f["origin"], f["chip"]["label"]) == ("shared", "person", "Not reviewed")
    assert f["reviews"] == [] and f["evidence_ids"] == []


def test_add_rejects_bad_level_origin_and_unknown_evidence(store):
    with pytest.raises(CoreError):
        store.add("x", "opinion", "ana")
    with pytest.raises(CoreError):
        store.add("x", "finding", "ana", [99])
    with pytest.raises(CoreError):
        store.add("x", "finding", "ana", origin="robot")


def test_finding_without_evidence_warns(store):
    assert "no evidence" in store.add("Users like dark mode", "finding", "ana")["warnings"][0]


def test_reviews_stay_individual(store):
    lid = store.add("Conversion is 42 percent", "observation", "ana")["learning"]["id"]
    r1 = store.review(lid, "sam", note="checked dashboard")
    assert r1["learning"]["chip"]["label"] == "Checked by peers"
    r2 = store.review(lid, "lee")
    assert [v["by"] for v in r2["learning"]["reviews"]] == ["sam", "lee"]
    assert r2["learning"]["reviews"][0]["note"] == "checked dashboard"
    with pytest.raises(CoreError):
        store.review(lid, "sam")  # already approved


def test_owner_cannot_review_their_own(store):
    lid = store.add("Conversion is 42 percent", "observation", "ana")["learning"]["id"]
    with pytest.raises(CoreError):
        store.review(lid, "ana")


def test_evidence_and_supports(store):
    obs = store.add("Conversion is 42 percent", "observation", "ana")["learning"]["id"]
    finding = store.add("Checkout is too long", "finding", "jo", [obs])["learning"]
    assert finding["evidence"][0]["id"] == obs
    assert store.get(obs)["supports"][0]["id"] == finding["id"]


def test_query_matches_topic_and_filters(store):
    store.add("Mobile checkout conversion is 42 percent", "observation", "ana")
    store.add("Desktop users prefer guest checkout", "finding", "jo")
    store.add("Onboarding emails get opened", "observation", "jo")
    hits = store.query("what do we know about mobile checkout?")
    assert hits[0]["statement"].startswith("Mobile checkout")
    assert all("checkout" in h["statement"].lower() for h in hits)
    assert len(store.query("")) == 3
    assert len(store.query("", level="finding")) == 1
    assert len(store.query("", trust="not_reviewed")) == 3
    with pytest.raises(CoreError):
        store.query("", trust="validated")


def test_conflict_found_and_confirmed(store):
    old = store.add("Users abandon mobile checkout because the address form is too long", "finding", "jo")["learning"]["id"]
    store.review(old, "sam")
    r = store.add("Address form length does not affect mobile checkout abandonment", "finding", "bot")
    new = r["learning"]["id"]
    assert r["possible_conflicts"][0]["learning"]["id"] == old
    assert r["possible_conflicts"][0]["likely_conflict"]
    assert store.get(old)["chip"]["label"] == "Checked by peers"  # checking changes nothing

    a, b = store.link(new, old, "conflicts_with", "lee", "A/B test disagrees")["learnings"]
    assert a["chip"]["label"] == b["chip"]["label"] == "Contested"
    assert a["conflicts"][0]["with"]["id"] == old and b["conflicts"][0]["with"]["id"] == new
    assert b["reviews"][0]["by"] == "sam"  # prior reviews are kept
    changed = [e for e in store.history(old) if e["kind"] == "trust_changed"][-1]
    assert changed["detail"] == {"from": "checked_by_peers", "to": "contested", "cause": "conflict"}
    with pytest.raises(CoreError):
        store.link(old, new, "conflicts_with", "lee")


def test_numbers_signal_conflict(store):
    old = store.add("Mobile checkout conversion is 42 percent", "observation", "ana")["learning"]["id"]
    store.review(old, "sam")
    assert store.check_conflict("Mobile checkout conversion is 35 percent")["candidates"][0]["likely_conflict"]


def test_unrelated_and_unreviewed_are_not_candidates(store):
    old = store.add("Mobile checkout conversion is 42 percent", "observation", "ana")["learning"]["id"]
    assert store.check_conflict("Mobile checkout conversion is 35 percent")["candidates"] == []
    store.review(old, "sam")
    assert store.check_conflict("Onboarding emails are rarely opened")["candidates"] == []


def test_contested_learnings_still_surface(store):
    a = store.add("Mobile checkout conversion is 42 percent", "observation", "ana")["learning"]["id"]
    store.review(a, "sam")
    b = store.add("Mobile checkout conversion is 35 percent", "observation", "bo")["learning"]["id"]
    store.link(b, a, "conflicts_with", "lee")
    ids = [c["learning"]["id"] for c in store.check_conflict("Mobile checkout conversion is 50 percent")["candidates"]]
    assert set(ids) == {a, b}


def test_working_on_is_a_soft_hold(store):
    lid = store.add("x is 1", "observation", "ana")["learning"]["id"]
    assert store.working_on(lid, "sam")["warnings"] == []
    r = store.working_on(lid, "lee")
    assert r["warnings"] and r["learning"]["working_by"] == "lee"
    r = store.review(lid, "sam")
    assert r["warnings"] and r["learning"]["chip"]["label"] == "Checked by peers"
    assert store.working_on(lid, "lee", on=False)["learning"]["working_by"] is None


def test_activity_is_the_full_record_with_plain_text(store):
    lid = store.add("x is 1", "observation", "ana")["learning"]["id"]
    store.review(lid, "sam")
    store.working_on(lid, "sam")
    events = [e for e in store.activity() if e["learning_id"]]
    assert [e["kind"] for e in events] == ["working_on", "trust_changed", "reviewed", "added"]
    assert events[2]["text"] == "sam approved #1"
    assert events[1]["text"] == "#1 is now Checked by peers"


def test_an_older_database_is_explained(tmp_path):
    path = tmp_path / "old.db"
    sqlite3.connect(path).execute("CREATE TABLE findings (id INTEGER)")
    with pytest.raises(CoreError, match="older ANCHOR"):
        Store(str(path))
