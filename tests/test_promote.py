import pytest

from anchor.core import CoreError


def _hypothesis(store):
    dp = store.propose("6 of 8 users said typing an address is tedious", "data_point", "Lee")["finding"]["id"]
    return store.propose("Long address forms drive mobile abandonment", "hypothesis", "Jo", [dp])["finding"]["id"]


def test_promote_creates_a_new_linked_insight(store):
    hyp = _hypothesis(store)
    store.validate(hyp, "Sam")
    r = store.promote(hyp, "Kim", statement="Address autofill is the top fix for mobile checkout",
                      note="Two studies agree")
    new = r["finding"]
    assert new["tier"] == "insight" and new["status"] == "proposed" and new["owner"] == "Kim"
    assert new["statement"] == "Address autofill is the top fix for mobile checkout"
    assert new["promoted_from"]["id"] == hyp
    assert new["evidence_links"] == [hyp]
    assert new["promotion"] is None  # insights are the top tier
    # The hypothesis stays as it was, and shows where it went.
    old = store.get(hyp)
    assert old["tier"] == "hypothesis" and old["status"] == "validated"
    assert old["validations"][0]["validated_by"] == "Sam"
    assert [f["id"] for f in old["promoted_to"]] == [new["id"]]
    step = [e for e in store.history(hyp) if e["kind"] == "promoted"][0]
    assert step["actor"] == "Kim"
    assert step["detail"] == {"to": new["id"], "from_tier": "hypothesis", "to_tier": "insight",
                              "note": "Two studies agree"}
    assert store.history(new["id"])[0]["detail"]["promoted_from"] == hyp


def test_open_by_default_with_honest_warnings(store):
    lonely = store.propose("Users want dark mode", "hypothesis", "Jo")["finding"]["id"]
    r = store.promote(lonely, "Jo")
    assert r["finding"]["tier"] == "insight"
    assert r["finding"]["statement"] == "Users want dark mode"
    text = " ".join(r["warnings"])
    assert "not been validated" in text and "no evidence" in text
    assert store.get(lonely)["promotion"] == {"ready": True, "summary": "no promotion rule set", "enforced": False}


def test_data_point_becomes_hypothesis_and_insight_stops(store):
    dp = store.propose("Conversion is 42 percent", "data_point", "Ana")["finding"]["id"]
    hyp = store.promote(dp, "Jo", "Conversion is low because of the form")["finding"]
    assert hyp["tier"] == "hypothesis" and hyp["promoted_from"]["id"] == dp
    ins = store.promote(hyp["id"], "Jo")["finding"]
    with pytest.raises(CoreError):
        store.promote(ins["id"], "Jo")


def test_team_rule_is_a_signal(make_store):
    store = make_store({"people": {"Sam": "researcher"},
                        "promote": {"min_validations": 2, "min_trusted_validations": 1}})
    hyp = _hypothesis(store)
    store.validate(hyp, "Kim")
    readiness = store.get(hyp)["promotion"]
    assert readiness["ready"] is False
    assert readiness["summary"] == "1 of 2 validations, or 0 of 1 trusted validations"
    r = store.promote(hyp, "Kim")
    assert any("not ready" in w for w in r["warnings"])
    store.validate(hyp, "Sam")  # one trusted validation is enough
    assert store.get(hyp)["promotion"]["ready"] is True


def test_team_rule_can_be_required(make_store):
    store = make_store({"people": {"Sam": "researcher"},
                        "promote": {"min_trusted_validations": 1, "trusted_roles_ready": True,
                                    "enforce": "required"}})
    hyp = _hypothesis(store)
    with pytest.raises(CoreError, match="not ready to promote"):
        store.promote(hyp, "Kim")
    # A trusted role can promote directly under this rule.
    assert store.promote(hyp, "Sam")["finding"]["tier"] == "insight"
