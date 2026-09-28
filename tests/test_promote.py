import pytest

from anchor.core import CoreError


def _finding(store):
    obs = store.add("6 of 8 users said typing an address is tedious", "observation", "Lee")["learning"]["id"]
    return store.add("Long address forms drive mobile abandonment", "finding", "Jo", [obs])["learning"]["id"]


def test_promote_adds_a_new_linked_insight(store):
    f = _finding(store)
    store.review(f, "Sam")
    r = store.promote(f, "Kim", statement="Address autofill is the top fix for mobile checkout", note="Two studies agree")
    new = r["learning"]
    assert (new["level"], new["chip"]["label"], new["owner"]) == ("insight", "Not reviewed", "Kim")
    assert new["promoted_from"]["id"] == f and new["evidence_ids"] == [f]
    assert new["promotion"] is None  # insights are the top level
    # The finding stays as it was, and shows where it went.
    old = store.get(f)
    assert old["level"] == "finding" and old["stage"] == "shared" and old["chip"]["label"] == "Checked by peers"
    assert [x["id"] for x in old["promoted_to"]] == [new["id"]]
    step = [e for e in store.history(f) if e["kind"] == "promoted"][0]
    assert step["detail"] == {"to": new["id"], "to_level": "insight", "note": "Two studies agree"}
    assert step["text"] == f"Kim promoted #{f} to insight #{new['id']}"


def test_open_by_default_with_honest_warnings(store):
    lonely = store.add("Users want dark mode", "finding", "Jo")["learning"]["id"]
    r = store.promote(lonely, "Jo")
    assert r["learning"]["level"] == "insight" and r["learning"]["statement"] == "Users want dark mode"
    text = " ".join(r["warnings"])
    assert "not been reviewed" in text and "no evidence" in text
    assert store.get(lonely)["promotion"] == {"ready": True, "rule": False, "summary": "", "enforced": False}


def test_observation_to_finding_and_insight_stops(store):
    obs = store.add("Conversion is 42 percent", "observation", "Ana")["learning"]["id"]
    f = store.promote(obs, "Jo", "Conversion is low because of the form")["learning"]
    assert f["level"] == "finding" and f["promoted_from"]["id"] == obs
    ins = store.promote(f["id"], "Jo")["learning"]
    with pytest.raises(CoreError):
        store.promote(ins["id"], "Jo")


def test_team_rule_is_a_signal(make_store):
    store = make_store({"smes": ["Sam"], "promote": {"min_approvals": 2, "min_sme_approvals": 1}})
    f = _finding(store)
    store.review(f, "Kim")
    readiness = store.get(f)["promotion"]
    assert readiness["ready"] is False and readiness["rule"] is True
    assert readiness["summary"] == "1 of 2 approvals, or 0 of 1 SME approvals"
    assert any("not ready" in w for w in store.promote(f, "Kim")["warnings"])
    store.review(f, "Sam")  # one SME approval is enough
    assert store.get(f)["promotion"]["ready"] is True


def test_team_rule_can_be_required(make_store):
    store = make_store({"smes": ["Sam"], "promote": {"min_sme_approvals": 1, "enforce": "required"}})
    f = _finding(store)
    with pytest.raises(CoreError, match="not ready to promote"):
        store.promote(f, "Kim")
    store.review(f, "Sam")
    assert store.promote(f, "Kim")["learning"]["level"] == "insight"
