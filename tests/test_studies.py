import pytest

from anchor.api import handle
from anchor.core import CoreError


def test_study_carries_its_chain_to_findings(store):
    r = store.start_study(
        "Mobile checkout friction", "Sam",
        objective="Find why mobile users drop at checkout",
        decision="Whether to fund an address autofill project",
        method="Interviews and funnel analysis", sample="8 users, 30 days of events",
    )
    assert r["warnings"] == []
    sid = r["study"]["id"]
    fid = store.propose("Drop off peaks on the address step", "data_point", "Priya", study_id=sid)["finding"]["id"]
    f = store.get(fid)
    assert f["study"]["decision"] == "Whether to fund an address autofill project"
    study = store.get_study(sid)
    assert [x["id"] for x in study["findings_by_tier"]["data_point"]] == [fid]
    assert study["findings_by_tier"]["insight"] == []
    assert store.list_studies()[0]["finding_count"] == 1
    assert store.history(fid)[0]["kind"] == "proposed"


def test_missing_parts_warn_but_never_block(make_store):
    store = make_store({"study": {"fields": [{"key": "participants", "required": True}]}})
    r = store.start_study("Quick look", "Sam")
    assert r["study"]["status"] == "planned"
    assert len(r["warnings"]) == 3  # objective, decision, participants
    r = store.update_study(r["study"]["id"], "Sam", objective="x", decision="y",
                           fields={"participants": "Mobile shoppers"})
    assert r["warnings"] == []
    assert r["study"]["fields"] == {"participants": "Mobile shoppers"}


def test_update_keeps_previous_values_in_history(store):
    sid = store.start_study("Pricing", "Sam", method="Survey")["study"]["id"]
    store.update_study(sid, "Lee", status="running", method="Survey and interviews", fields={"a": "1"})
    store.update_study(sid, "Lee", fields={"b": "2"})
    study = store.get_study(sid)
    assert study["status"] == "running"
    assert study["fields"] == {"a": "1", "b": "2"}
    change = study["history"][1]
    assert change["actor"] == "Lee"
    assert change["detail"]["previous"]["method"] == "Survey"
    assert change["detail"]["previous"]["status"] == "planned"
    assert [s["id"] for s in store.list_studies(status="running")] == [sid]
    assert store.list_studies(owner="sam")[0]["id"] == sid


def test_bad_study_input(store):
    with pytest.raises(CoreError):
        store.start_study("", "Sam")
    with pytest.raises(CoreError):
        store.start_study("x", "Sam", status="someday")
    sid = store.start_study("x", "Sam")["study"]["id"]
    with pytest.raises(CoreError):
        store.update_study(sid, "Sam", colour="blue")
    with pytest.raises(CoreError):
        store.propose("y is 2", "data_point", "Sam", study_id=99)


def test_studies_over_the_api(store):
    status, r = handle(store, "POST", "/api/start_study", {"title": "Onboarding", "owner": "Sam"})
    assert status == 200
    sid = r["study"]["id"]
    assert handle(store, "GET", f"/api/studies/{sid}")[1]["title"] == "Onboarding"
    assert handle(store, "GET", "/api/studies?status=planned")[1][0]["id"] == sid
    status, r = handle(store, "POST", "/api/update_study", {"study_id": sid, "by": "Sam", "status": "done"})
    assert status == 200 and r["study"]["status"] == "done"
