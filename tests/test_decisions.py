import pytest

from anchor.api import handle
from anchor.core import CoreError


def _chain(store):
    """A study, an observation, a finding, and a promoted insight, each checked."""
    sid = store.start_study("Why do mobile users drop?", "Lee", decision="Fund autofill or not")["study"]["id"]
    obs = store.add("Drop off peaks on the address step", "observation", "Priya", study_id=sid)["learning"]["id"]
    store.review(obs, "Sam")
    f = store.add("Long address forms drive abandonment", "finding", "Jo", [obs])["learning"]["id"]
    store.review(f, "Lee")
    ins = store.promote(f, "Kim", "Autofill is the top fix for mobile checkout")["learning"]["id"]
    store.review(ins, "Sam", how="evidence")
    return sid, obs, f, ins


def test_log_a_decision_in_one_step_with_chain_credit(make_store):
    store = make_store({"people": {"Morgan": "stakeholder"}, "smes": ["Sam"]})
    sid, obs, f, ins = _chain(store)
    r = store.log_decision("Fund address autofill in Q3", "Morgan", [ins], note="Biggest lever we have")
    assert r["warnings"] == []
    d = r["decision"]
    assert d["learnings"][0]["id"] == ins and d["learnings"][0]["trust_at_use"] == "checked_by_sme"
    assert d["learnings"][0]["trust"].startswith("Checked by 1 SME.")
    assert d["outcome"] is None and d["outcome_due"] is False
    credits = {c["name"]: c["contributions"] for c in d["credits"]}
    assert list(credits) == ["Jo", "Kim", "Lee", "Priya", "Sam"]  # by name, never ranked
    assert {"did": "added", "learning_id": ins} in credits["Kim"]
    assert {"did": "approved", "learning_id": f} in credits["Lee"]
    assert {"did": "ran the study", "study_id": sid} in credits["Lee"]
    assert "Morgan" not in credits

    assert store.get(ins)["used_in"][0]["title"] == "Fund address autofill in Q3"
    priya = store.person("priya")
    assert priya["contributed_to"][0]["id"] == d["id"]
    assert store.person("Morgan")["decisions_made"][0]["id"] == d["id"]


def test_honest_warnings_and_outcome_later(make_store):
    store = make_store({"outcome_after_days": 0})
    lid = store.add("Users want dark mode", "finding", "Jo")["learning"]["id"]
    r = store.log_decision("Ship dark mode", "Morgan", [lid])
    assert r["warnings"] == [f"#{lid} is Not reviewed"]
    assert store.log_decision("Gut call", "Morgan")["warnings"][0].startswith("no learnings linked")
    did = r["decision"]["id"]
    assert store.get_decision(did)["outcome_due"] is True
    assert [d["id"] for d in store.my_queue("Morgan")["outcomes_due"]] == [did + 1, did]
    other = store.add("Dark mode helps retention", "finding", "Kim")["learning"]["id"]
    r = store.update_decision(did, "Morgan", outcome="Usage up 4 percent", add_learning_ids=[other])
    assert r["decision"]["outcome"] == "Usage up 4 percent" and r["decision"]["outcome_due"] is False
    assert [x["id"] for x in r["decision"]["learnings"]] == [lid, other]
    with pytest.raises(CoreError):
        store.log_decision("", "Morgan")
    with pytest.raises(CoreError):
        store.log_decision("x", "Morgan", [99])


def test_owner_hears_when_a_used_learning_is_contested(store):
    a = store.add("Checkout form is too long for mobile users", "finding", "Jo")["learning"]["id"]
    store.review(a, "Sam")
    did = store.log_decision("Shorten the form", "Morgan", [a])["decision"]["id"]
    assert store.my_queue("Morgan")["decisions_at_risk"] == []
    b = store.add("Checkout form is not too long for mobile users", "finding", "Al")["learning"]["id"]
    store.link(b, a, "conflicts_with", "Lee")
    at_risk = store.my_queue("Morgan")["decisions_at_risk"]
    assert at_risk[0]["id"] == did and at_risk[0]["at_risk"] == [a]
    step = store.next_step("Morgan")["step"]
    assert step["kind"] == "at_risk" and step["learning_id"] == a
    assert store.digest("Morgan")["items"][0]["text"] == f'#{a}, used in "Shorten the form", is now Contested'


def test_decisions_over_the_api(store):
    status, r = handle(store, "POST", "/api/log_decision", {"title": "Go", "made_by": "Morgan"})
    assert status == 200
    assert handle(store, "GET", f"/api/decisions/{r['decision']['id']}")[1]["title"] == "Go"
    assert handle(store, "GET", "/api/decisions")[1][0]["title"] == "Go"
    assert handle(store, "GET", "/api/people/Morgan")[1]["decisions_made"][0]["title"] == "Go"
    assert handle(store, "GET", "/api/people/Nobody")[0] == 400


def test_credit_follows_revisions_and_counts_feedback(store):
    lid = store.add("Long forms drive abandonment", "finding", "Jo")["learning"]["id"]
    store.review(lid, "Dana", "changes", note="Scope it to mobile web")
    new = store.revise(lid, "Jo", "Long forms drive abandonment on mobile web")["learning"]["id"]
    store.review(new, "Dana")
    credits = {c["name"]: c["contributions"] for c in store.log_decision("Go", "Morgan", [new])["decision"]["credits"]}
    assert credits["Dana"] == [{"did": "asked for changes", "learning_id": lid}, {"did": "approved", "learning_id": new}]
    assert credits["Jo"] == [{"did": "added", "learning_id": lid}, {"did": "added", "learning_id": new}]
