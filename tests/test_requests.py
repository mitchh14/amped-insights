from anchor.api import handle


def test_question_from_a_decision_lands_as_a_draft_study(store):
    did = store.log_decision("Fund address autofill", "Morgan")["decision"]["id"]
    r = store.request_research("Does autofill help returning users too?", "Morgan", from_decision_id=did)
    study = r["study"]
    assert r["warnings"] == []
    assert study["status"] == "requested" and study["owner"] is None
    assert study["requested_by"] == "Morgan"
    assert study["decision"] == "Fund address autofill"  # taken from the decision
    assert study["from_decision"]["id"] == did
    assert store.get_decision(did)["requests"][0]["id"] == study["id"]
    assert [s["id"] for s in store.list_studies(status="requested")] == [study["id"]]

    # A researcher picks it up, and the loop continues in Mode 1.
    picked = store.update_study(study["id"], "Lee", status="planned", owner="Lee",
                                objective="Learn if autofill helps returning users")["study"]
    assert picked["status"] == "planned" and picked["owner"] == "Lee"
    kinds = [h["kind"] for h in picked["history"]]
    assert kinds == ["research_requested", "study_updated"]


def test_question_from_an_empty_search(make_store):
    store = make_store({"study": {"fields": [{"key": "intake_link", "label": "Intake ticket"}]}})
    r = store.request_research("Why do users skip onboarding?", "Kim",
                               from_query="onboarding skip", fields={"intake_link": "https://tracker/123"})
    assert r["study"]["from_query"] == "onboarding skip"
    assert r["study"]["fields"] == {"intake_link": "https://tracker/123"}
    assert "which decision" in r["warnings"][0]
    event = store.activity()[0]
    assert event["kind"] == "research_requested" and event["study_title"] == "Why do users skip onboarding?"


def test_requests_over_the_api(store):
    status, r = handle(store, "POST", "/api/request_research",
                       {"question": "What stops trial users converting?", "requested_by": "Kim",
                        "decision": "Pricing page redesign"})
    assert status == 200 and r["study"]["status"] == "requested"
    assert handle(store, "POST", "/api/request_research", {"question": "", "requested_by": "Kim"})[0] == 400
