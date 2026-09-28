import pytest

from anchor.api import handle
from anchor.core import CoreError


def test_start_with_two_fields_and_carry_the_chain(store):
    r = store.start_study("Why do mobile shoppers drop at checkout?", "Sam",
                          decision="Whether to fund an address autofill project")
    assert r["warnings"] == [] and r["study"]["needs"] == []
    sid = r["study"]["id"]
    lid = store.add("Drop off peaks on the address step", "observation", "Priya", study_id=sid)["learning"]["id"]
    assert store.get(lid)["study"]["decision"] == "Whether to fund an address autofill project"
    study = store.get_study(sid)
    assert [x["id"] for x in study["by_level"]["observation"]] == [lid] and study["by_level"]["insight"] == []
    assert store.list_studies()[0]["learning_count"] == 1


def test_each_stage_asks_for_its_own_details(make_store):
    store = make_store({"study": {"fields": [
        {"key": "participants", "required": True},
        {"key": "intake_link", "ask_at": "start"},
    ]}})
    r = store.start_study("Quick look", "Sam")
    # At start: the decision (a warning) and start fields (a nudge, not required).
    assert [n["key"] for n in r["study"]["needs"]] == ["decision", "field:intake_link"]
    assert r["warnings"] == ["Decision it serves is empty"]
    sid = r["study"]["id"]
    r = store.update_study(sid, "Sam", decision="y", status="running")
    assert [n["key"] for n in r["study"]["needs"]] == ["field:intake_link", "method", "sample", "field:participants"]
    r = store.update_study(sid, "Sam", method="Survey", sample="200 shoppers",
                           fields={"participants": "Mobile shoppers", "intake_link": "T-1"})
    assert r["study"]["needs"] == [] and r["warnings"] == []
    r = store.update_study(sid, "Sam", status="finished")
    assert [n["key"] for n in r["study"]["needs"]] == ["learned"]
    assert store.update_study(sid, "Sam", learned="Autofill matters most")["study"]["needs"] == []


def test_update_keeps_previous_values_in_history(store):
    sid = store.start_study("Pricing", "Sam")["study"]["id"]
    store.update_study(sid, "Lee", status="running", method="Survey", fields={"a": "1"})
    store.update_study(sid, "Lee", method="Survey and interviews", fields={"b": "2"})
    study = store.get_study(sid)
    assert study["status"] == "running" and study["fields"] == {"a": "1", "b": "2"}
    change = study["history"][2]
    assert change["actor"] == "Lee" and change["detail"]["previous"]["method"] == "Survey"
    assert study["history"][1]["text"] == 'Lee moved "Pricing" to Running'
    assert [s["id"] for s in store.list_studies(status="running")] == [sid]
    assert store.list_studies(owner="sam")[0]["id"] == sid


def test_bad_study_input(store):
    with pytest.raises(CoreError):
        store.start_study("", "Sam")
    sid = store.start_study("x", "Sam")["study"]["id"]
    with pytest.raises(CoreError):
        store.update_study(sid, "Sam", colour="blue")
    with pytest.raises(CoreError):
        store.update_study(sid, "Sam", status="done")
    with pytest.raises(CoreError):
        store.add("y is 2", "observation", "Sam", study_id=99)


def test_research_requests_need_only_a_question(store):
    r = store.ask_for_research("Do returning shoppers use saved addresses?", "Morgan")
    assert r["study"]["status"] == "requested" and "which decision" in r["warnings"][0]
    sid = r["study"]["id"]
    s = store.update_study(sid, "Sam", status="planned", owner="Sam")["study"]
    assert s["owner"] == "Sam" and s["requested_by"] == "Morgan"


def test_studies_over_the_api(store):
    status, r = handle(store, "POST", "/api/start_study", {"question": "Onboarding", "owner": "Sam"})
    assert status == 200
    sid = r["study"]["id"]
    assert handle(store, "GET", f"/api/studies/{sid}")[1]["question"] == "Onboarding"
    assert handle(store, "GET", "/api/studies?status=planned")[1][0]["id"] == sid
    status, r = handle(store, "POST", "/api/update_study", {"study_id": sid, "by": "Sam", "status": "dropped"})
    assert status == 200 and r["study"]["status"] == "dropped"
