import pytest

from anchor.api import handle
from anchor.core import CoreError


def _chain(store):
    """A study, a data point, a hypothesis, and a promoted insight, each validated."""
    sid = store.start_study("Checkout friction", "Lee", objective="Why mobile users drop",
                            decision="Fund autofill or not")["study"]["id"]
    dp = store.propose("Drop off peaks on the address step", "data_point", "Priya", study_id=sid)["finding"]["id"]
    store.validate(dp, "Sam")
    hyp = store.propose("Long address forms drive abandonment", "hypothesis", "Jo", [dp])["finding"]["id"]
    store.validate(hyp, "Lee")
    ins = store.promote(hyp, "Kim", "Autofill is the top fix for mobile checkout")["finding"]["id"]
    store.validate(ins, "Sam", basis="evidence")
    return sid, dp, hyp, ins


def test_log_a_decision_in_one_step_with_chain_credit(make_store):
    store = make_store({"people": {"Morgan": "stakeholder", "Sam": "researcher", "Lee": "researcher"}})
    sid, dp, hyp, ins = _chain(store)
    r = store.log_decision("Fund address autofill in Q3", "Morgan", [ins], note="Biggest lever we have")
    assert r["warnings"] == []
    d = r["decision"]
    assert d["findings"][0]["id"] == ins and d["findings"][0]["status_at_use"] == "validated"
    assert d["findings"][0]["trust"].startswith("Validated by 1 researcher.")
    credits = {c["name"]: c["contributions"] for c in d["credits"]}
    assert list(credits) == ["Jo", "Kim", "Lee", "Priya", "Sam"]  # by name, not ranked
    assert {"did": "proposed", "finding_id": ins} in credits["Kim"]
    assert {"did": "proposed", "finding_id": dp} in credits["Priya"]
    assert {"did": "validated", "finding_id": hyp} in credits["Lee"]
    assert {"did": "ran study", "study_id": sid} in credits["Lee"]
    assert {"did": "validated", "finding_id": dp} in credits["Sam"]
    assert "Morgan" not in credits

    assert store.get(ins)["used_in"][0]["title"] == "Fund address autofill in Q3"
    priya = store.person("priya")
    assert priya["role"] == "contributor"
    assert priya["contributed_to"][0]["id"] == d["id"]
    assert store.person("Morgan")["decisions_made"][0]["id"] == d["id"]


def test_honest_warnings_and_outcomes(store):
    fid = store.propose("Users want dark mode", "hypothesis", "Jo")["finding"]["id"]
    r = store.log_decision("Ship dark mode", "Morgan", [fid])
    assert "not been validated" in r["warnings"][0]
    assert store.log_decision("Gut call", "Morgan")["warnings"][0].startswith("no findings linked")
    did = r["decision"]["id"]
    other = store.propose("Dark mode helps retention", "hypothesis", "Kim")["finding"]["id"]
    r = store.update_decision(did, "Morgan", outcome="Usage up 4 percent", add_finding_ids=[other])
    assert r["decision"]["outcome"] == "Usage up 4 percent"
    assert [f["id"] for f in r["decision"]["findings"]] == [fid, other]
    assert [d["id"] for d in store.list_decisions(made_by="morgan")][1] == did
    with pytest.raises(CoreError):
        store.log_decision("", "Morgan")
    with pytest.raises(CoreError):
        store.log_decision("x", "Morgan", [99])


def test_owner_sees_when_a_used_insight_is_contested(store):
    a = store.propose("Checkout form is too long for mobile users", "hypothesis", "Jo")["finding"]["id"]
    store.validate(a, "Sam")
    did = store.log_decision("Shorten the form", "Morgan", [a])["decision"]["id"]
    assert store.my_queue("Morgan")["decisions_at_risk"] == []
    b = store.propose("Checkout form is not too long for mobile users", "hypothesis", "Al")["finding"]["id"]
    store.confirm_conflict(b, a, "Lee")
    at_risk = store.my_queue("Morgan")["decisions_at_risk"]
    assert at_risk[0]["id"] == did and at_risk[0]["at_risk"] == [a]
    event = store.activity()[0]
    assert event["kind"] == "decision_at_risk" and event["decision_title"] == "Shorten the form"


def test_decisions_over_the_api(store):
    status, r = handle(store, "POST", "/api/log_decision", {"title": "Go", "made_by": "Morgan"})
    assert status == 200
    assert handle(store, "GET", f"/api/decisions/{r['decision']['id']}")[1]["title"] == "Go"
    assert handle(store, "GET", "/api/decisions")[1][0]["title"] == "Go"
    assert handle(store, "GET", "/api/people/Morgan")[1]["decisions_made"][0]["title"] == "Go"
    assert handle(store, "GET", "/api/people/Nobody")[0] == 400


def test_credit_follows_revisions_and_counts_feedback(store):
    fid = store.propose("Long forms drive abandonment", "hypothesis", "Jo")["finding"]["id"]
    store.validate(fid, "Dana", "Scope it to mobile web", outcome="changes_requested")
    new = store.revise(fid, "Jo", "Long forms drive abandonment on mobile web")["finding"]["id"]
    store.validate(new, "Dana")
    credits = {c["name"]: c["contributions"] for c in store.log_decision("Go", "Morgan", [new])["decision"]["credits"]}
    assert credits["Dana"] == [{"did": "suggested changes", "finding_id": fid},
                               {"did": "validated", "finding_id": new}]
    assert credits["Jo"] == [{"did": "proposed", "finding_id": fid}, {"did": "proposed", "finding_id": new}]
