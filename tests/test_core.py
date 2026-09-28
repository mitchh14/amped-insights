import pytest

from anchor.core import CoreError, Store


def test_propose_starts_as_proposed(store):
    f = store.propose("Mobile checkout conversion is 42 percent", "data_point", "ana")["finding"]
    assert f["status"] == "proposed"
    assert f["validations"] == []
    assert f["evidence_links"] == []


def test_propose_rejects_bad_tier_and_unknown_evidence(store):
    with pytest.raises(CoreError):
        store.propose("x", "opinion", "ana")
    with pytest.raises(CoreError):
        store.propose("x", "hypothesis", "ana", [99])


def test_hypothesis_without_evidence_warns(store):
    r = store.propose("Users like dark mode", "hypothesis", "ana")
    assert r["warnings"]


def test_validations_stay_individual(store):
    fid = store.propose("Conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    r1 = store.validate(fid, "sam", "checked dashboard")
    assert r1["finding"]["status"] == "validated"
    r2 = store.validate(fid, "lee")
    names = [v["validated_by"] for v in r2["finding"]["validations"]]
    assert names == ["sam", "lee"]
    assert r2["finding"]["validations"][0]["note"] == "checked dashboard"
    with pytest.raises(CoreError):
        store.validate(fid, "sam")


def test_owner_cannot_self_validate(store):
    fid = store.propose("Conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    with pytest.raises(CoreError):
        store.validate(fid, "ana")


def test_evidence_links_and_cited_by(store):
    dp = store.propose("Conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    hyp = store.propose("Checkout is too long", "hypothesis", "jo", [dp])["finding"]
    assert hyp["evidence"][0]["id"] == dp
    assert store.get(dp)["cited_by"][0]["id"] == hyp["id"]


def test_query_matches_topic(store):
    store.propose("Mobile checkout conversion is 42 percent", "data_point", "ana")
    store.propose("Desktop users prefer guest checkout", "hypothesis", "jo")
    store.propose("Onboarding emails get opened", "data_point", "jo")
    hits = store.query("what do we know about mobile checkout?")
    assert [h["statement"] for h in hits][0].startswith("Mobile checkout")
    assert all("checkout" in h["statement"].lower() for h in hits)
    assert len(store.query("")) == 3
    assert len(store.query("", tier="hypothesis")) == 1


def test_conflict_detected_and_confirmed(store):
    old = store.propose(
        "Users abandon mobile checkout because the address form is too long", "hypothesis", "jo"
    )["finding"]["id"]
    store.validate(old, "sam")
    r = store.propose("Address form length does not affect mobile checkout abandonment", "hypothesis", "bot")
    new = r["finding"]["id"]
    assert r["possible_conflicts"][0]["finding"]["id"] == old
    assert r["possible_conflicts"][0]["likely_conflict"]
    # Checking changes nothing.
    assert store.get(old)["status"] == "validated"

    res = store.confirm_conflict(new, old, "lee", "A/B test disagrees")
    a, b = res["findings"]
    assert a["status"] == b["status"] == "contested"
    assert a["conflicts"][0]["with"]["id"] == old
    assert b["conflicts"][0]["with"]["id"] == new
    # Prior state is kept, not erased.
    assert b["validations"][0]["validated_by"] == "sam"
    contested = [e for e in store.history(old) if e["kind"] == "contested"][0]
    assert contested["detail"]["previous_status"] == "validated"
    with pytest.raises(CoreError):
        store.confirm_conflict(old, new, "lee")


def test_numbers_signal_conflict(store):
    old = store.propose("Mobile checkout conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    store.validate(old, "sam")
    cands = store.check_conflict("Mobile checkout conversion is 35 percent")["candidates"]
    assert cands[0]["likely_conflict"]


def test_unrelated_is_not_a_candidate(store):
    old = store.propose("Mobile checkout conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    store.validate(old, "sam")
    assert store.check_conflict("Onboarding emails are rarely opened")["candidates"] == []


def test_validating_contested_keeps_status(store):
    a = store.propose("Checkout form is too long for mobile users", "hypothesis", "jo")["finding"]["id"]
    b = store.propose("Checkout form is not too long for mobile users", "hypothesis", "al")["finding"]["id"]
    store.validate(a, "sam")
    store.confirm_conflict(b, a, "lee")
    r = store.validate(a, "kim")
    assert r["finding"]["status"] == "contested"
    assert r["warnings"]


def test_checkout_is_advisory(store):
    fid = store.propose("x is 1", "data_point", "ana")["finding"]["id"]
    assert store.checkout(fid, "sam")["warnings"] == []
    r = store.checkout(fid, "lee")
    assert r["warnings"] and r["finding"]["checked_out_by"] == "lee"
    r = store.validate(fid, "sam")
    assert r["warnings"]  # someone else has it, but the validation still went through
    assert r["finding"]["status"] == "validated"
    r = store.release(fid, "lee")
    assert r["finding"]["checked_out_by"] is None


def test_activity_feed(store):
    fid = store.propose("x is 1", "data_point", "ana")["finding"]["id"]
    store.validate(fid, "sam")
    store.checkout(fid, "sam")
    kinds = [e["kind"] for e in store.activity() if e["finding_id"]]
    assert kinds == ["checked_out", "status_changed", "validated", "proposed"]


def test_contested_findings_still_surface_in_conflict_check(store):
    a = store.propose("Mobile checkout conversion is 42 percent", "data_point", "ana")["finding"]["id"]
    store.validate(a, "sam")
    b = store.propose("Mobile checkout conversion is 35 percent", "data_point", "bo")["finding"]["id"]
    store.confirm_conflict(b, a, "lee")
    ids = [c["finding"]["id"] for c in store.check_conflict("Mobile checkout conversion is 50 percent")["candidates"]]
    assert set(ids) == {a, b}
