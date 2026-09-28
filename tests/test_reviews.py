import pytest

from anchor.core import CoreError


def _learning(store, owner="Jo"):
    return store.add("Long address forms drive mobile abandonment", "finding", owner)["learning"]["id"]


def test_bad_input_is_explained(store):
    lid = _learning(store)
    assert store.review(lid, "Sam", "changes")["learning"]["reviews"][0]["note"] is None
    with pytest.raises(CoreError):
        store.review(lid, "Lee", "maybe")
    with pytest.raises(CoreError):
        store.review(lid, "Lee", how="vibes")


def test_request_reaches_the_right_queue_and_clears(make_store):
    store = make_store({"people": {"Sam": "researcher", "Lee": "researcher"}, "smes": ["Dana"]})
    lid = _learning(store)
    r = store.ask_for_review(lid, "Jo", people=["Kim"], roles=["researcher", "sme"], note="Before Friday")
    assert len(r["request_ids"]) == 3 and len(r["learning"]["open_requests"]) == 3
    for name in ("Kim", "Sam", "lee", "Dana"):
        assert [w["learning"]["id"] for w in store.my_queue(name)["waiting_on_me"]] == [lid]
    assert len(store.my_queue("Jo")["my_requests"]) == 3

    # Any researcher answering closes the role request for every researcher.
    store.review(lid, "Lee", "changes", note="Add the sample size")
    assert store.my_queue("Sam")["waiting_on_me"] == []
    assert store.my_queue("Jo")["feedback_on_mine"][0]["reviews"][0]["note"] == "Add the sample size"
    store.review(lid, "Dana")
    store.review(lid, "Kim")
    assert store.get(lid)["open_requests"] == [] and store.my_queue("Jo")["my_requests"] == []


def test_request_rules(store):
    lid = _learning(store)
    with pytest.raises(CoreError):
        store.ask_for_review(lid, "Jo")
    with pytest.raises(CoreError):
        store.ask_for_review(lid, "Jo", roles=["wizard"])
    r = store.ask_for_review(lid, "Jo", people=["Jo", "Sam"])
    assert len(r["request_ids"]) == 1 and "owns this learning" in r["warnings"][0]
    r = store.ask_for_review(lid, "Jo", people=["sam"])
    assert r["request_ids"] == [] and "already has an open request" in r["warnings"][0]
    req = store.my_queue("Sam")["waiting_on_me"][0]["request"]["id"]
    store.withdraw_request(req, "Jo")
    assert store.my_queue("Sam")["waiting_on_me"] == []
    with pytest.raises(CoreError):
        store.withdraw_request(req, "Jo")


def test_revise_replaces_and_asks_again(store):
    lid = _learning(store)
    store.review(lid, "Sam", "changes", note="Narrow it to mobile web")
    store.review(lid, "Lee", note="Fine as is")
    store.ask_for_review(lid, "Jo", people=["Kim"])
    assert store.my_queue("Jo")["feedback_on_mine"][0]["learning"]["id"] == lid

    r = store.revise(lid, "Jo", "Long address forms drive abandonment on mobile web", note="Scoped down")
    new = r["learning"]
    assert r["asked_again"] == ["Sam"]
    assert new["revises"]["id"] == lid and new["level"] == "finding" and new["chip"]["label"] == "Not reviewed"
    old = store.get(lid)
    assert old["stage"] == "replaced" and old["chip"]["label"] == "Replaced"
    assert old["replaced_by"][0]["id"] == new["id"] and len(old["reviews"]) == 2  # kept as it was
    assert old["open_requests"] == []
    assert store.my_queue("Jo")["feedback_on_mine"] == []
    assert [w["learning"]["id"] for w in store.my_queue("Sam")["waiting_on_me"]] == [new["id"]]
    revised = [e for e in store.history(lid) if e["kind"] == "revised"][0]
    assert revised["text"].startswith('Jo revised #1 as #2. Was: "Long address forms drive mobile abandonment"')
    with pytest.raises(CoreError):
        store.revise(new["id"], "Jo", new["statement"])
    with pytest.raises(CoreError, match="replaced by #2"):
        store.revise(lid, "Jo", "Something else")
    with pytest.raises(CoreError, match="review that one"):
        store.review(lid, "Kim")


def test_revising_a_contested_learning_warns(store):
    a = store.add("Checkout form is too long for mobile users", "finding", "Jo")["learning"]["id"]
    b = store.add("Checkout form is not too long for mobile users", "finding", "Al")["learning"]["id"]
    store.link(b, a, "conflicts_with", "Lee")
    assert "contested" in store.revise(a, "Jo", "Checkout form is too long for some mobile users")["warnings"][0]
