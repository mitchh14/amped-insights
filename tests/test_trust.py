from anchor.api import handle


def test_one_trust_state_and_a_plain_summary(make_store):
    store = make_store({"smes": ["Sam", "Dana"]})
    lid = store.add("Long address forms drive mobile abandonment", "finding", "Jo")["learning"]["id"]
    assert store.get(lid)["trust"]["summary"] == "Not reviewed yet."

    store.review(lid, "Kim", note="Looks right to me")
    assert store.get(lid)["trust"]["state"] == "checked_by_peers"
    store.review(lid, "Sam", how="source_data")
    store.review(lid, "Lee", how="reran")
    assert store.get(lid)["trust"]["state"] == "checked_by_sme"
    store.review(lid, "Dana", "changes", note="Scope it to mobile web")
    f = store.get(lid)
    assert (f["trust"]["state"], f["chip"]["label"]) == ("needs_changes", "Needs changes")
    assert (f["trust"]["sme"], f["trust"]["peer"], f["trust"]["changes"]) == (1, 2, 1)
    assert f["trust"]["summary"] == (
        "Checked by 1 SME and 2 peers. "
        "How they checked: checked the source data (1), reran it (1). "
        "1 asks for changes."
    )
    # SME reviews are listed first, each with its role.
    assert [(v["by"], v["sme"]) for v in f["reviews"]] == [
        ("Sam", True), ("Dana", True), ("Kim", False), ("Lee", False)]
    store.review(lid, "Lee", "disagree", note="Our A/B test says otherwise")
    assert store.get(lid)["chip"]["label"] == "Contested"


def test_sme_standing_is_kept_as_it_was_at_review_time(store):
    lid = store.add("x is 1", "observation", "Jo")["learning"]["id"]
    store.review(lid, "Sam")
    store.set_person("Sam", "Lee", sme=True)
    assert store.get(lid)["reviews"][0]["sme"] is False
    assert store.get(lid)["trust"]["summary"] == "Checked by 1 peer."


def test_the_latest_review_counts(store):
    lid = store.add("Long forms drive abandonment", "finding", "Jo")["learning"]["id"]
    store.review(lid, "Sam", "changes", note="Narrow it")
    assert store.get(lid)["trust"]["state"] == "needs_changes"
    store.review(lid, "Sam", note="Fine now")
    f = store.get(lid)
    assert f["trust"]["state"] == "checked_by_peers"
    assert [(v["verdict"], v["current"]) for v in f["reviews"]] == [("approve", True), ("changes", False)]


def test_trust_is_in_query_results(store):
    lid = store.add("Mobile checkout conversion is 42 percent", "observation", "Jo")["learning"]["id"]
    store.review(lid, "Sam")
    hit = handle(store, "GET", "/api/learnings?q=checkout")[1][0]
    assert hit["trust"]["summary"] == "Checked by 1 peer." and hit["chip"]["key"] == "checked_by_peers"
