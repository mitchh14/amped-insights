import pytest

from anchor.core import CoreError


def _finding(store, owner="Jo"):
    return store.propose("Long address forms drive mobile abandonment", "hypothesis", owner)["finding"]["id"]


def test_outcomes_are_individual_and_latest_counts(store):
    fid = _finding(store)
    f = store.validate(fid, "Sam", "Narrow it to mobile web", outcome="changes_requested")["finding"]
    assert f["status"] == "proposed"
    f = store.validate(fid, "Lee", "Our A/B test says otherwise", outcome="disagree")["finding"]
    assert f["status"] == "proposed"  # disagreeing never contests on its own
    f = store.validate(fid, "Sam", "Scope is right now")["finding"]
    assert f["status"] == "validated"
    assert [(v["validated_by"], v["outcome"], v["current"]) for v in f["validations"]] == [
        ("Sam", "changes_requested", False), ("Lee", "disagree", True), ("Sam", "approve", True),
    ]
    with pytest.raises(CoreError):
        store.validate(fid, "Sam")  # already approved
    # If the only approver changes their mind, the finding goes back to proposed.
    f = store.validate(fid, "Sam", "New data changed my mind", outcome="disagree")["finding"]
    assert f["status"] == "proposed"
    kinds = [e["kind"] for e in store.history(fid)]
    assert kinds.count("status_changed") == 2 and "disagreed" in kinds and "changes_requested" in kinds


def test_blank_reasons_are_allowed_and_bad_input_is_not(store):
    fid = _finding(store)
    assert store.validate(fid, "Sam", outcome="changes_requested")["finding"]["validations"][0]["note"] is None
    with pytest.raises(CoreError):
        store.validate(fid, "Lee", outcome="maybe")
    with pytest.raises(CoreError):
        store.validate(fid, "Lee", basis="vibes")


def test_request_reaches_the_right_queue_and_clears(make_store):
    store = make_store({"people": {"Sam": "researcher", "Lee": "researcher", "Kim": "contributor"}})
    fid = _finding(store)
    r = store.request_validation(fid, "Jo", people=["Kim"], roles=["researcher"], note="Before Friday")
    assert len(r["request_ids"]) == 2
    assert len(r["finding"]["open_requests"]) == 2
    assert [w["finding"]["id"] for w in store.my_queue("Kim")["waiting_on_me"]] == [fid]
    assert [w["finding"]["id"] for w in store.my_queue("Sam")["waiting_on_me"]] == [fid]
    assert [w["finding"]["id"] for w in store.my_queue("lee")["waiting_on_me"]] == [fid]
    assert len(store.my_queue("Jo")["my_requests"]) == 2

    # Any researcher answering closes the role request, for every researcher.
    store.validate(fid, "Lee", outcome="changes_requested", note="Add the sample size")
    assert store.my_queue("Sam")["waiting_on_me"] == []
    assert len(store.my_queue("Kim")["waiting_on_me"]) == 1
    feedback = store.my_queue("Jo")["feedback_on_mine"]
    assert feedback[0]["reviews"][0]["note"] == "Add the sample size"

    store.validate(fid, "Kim")
    assert store.my_queue("Kim")["waiting_on_me"] == []
    assert store.get(fid)["open_requests"] == []
    assert store.my_queue("Jo")["my_requests"] == []


def test_request_rules(store):
    fid = _finding(store)
    with pytest.raises(CoreError):
        store.request_validation(fid, "Jo")
    with pytest.raises(CoreError):
        store.request_validation(fid, "Jo", roles=["wizard"])
    r = store.request_validation(fid, "Jo", people=["Jo", "Sam"])
    assert len(r["request_ids"]) == 1 and "owns this finding" in r["warnings"][0]
    r = store.request_validation(fid, "Jo", people=["sam"])
    assert r["request_ids"] == [] and "already has an open request" in r["warnings"][0]
    req = store.my_queue("Sam")["waiting_on_me"][0]["request"]["id"]
    store.withdraw_request(req, "Jo")
    assert store.my_queue("Sam")["waiting_on_me"] == []
    with pytest.raises(CoreError):
        store.withdraw_request(req, "Jo")
