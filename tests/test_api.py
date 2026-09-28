import json

from anchor.api import handle, handle_json
from anchor.seed import seed


def test_add_then_query(store):
    status, r = handle(store, "POST", "/api/add",
                       {"statement": "Conversion is 42 percent", "level": "observation", "owner": "ana"})
    assert status == 200
    lid = r["learning"]["id"]
    status, found = handle(store, "GET", "/api/learnings?q=conversion&trust=not_reviewed")
    assert status == 200 and [f["id"] for f in found] == [lid]
    assert handle(store, "GET", f"/api/learnings/{lid}")[1]["statement"] == "Conversion is 42 percent"
    assert handle(store, "GET", f"/api/learnings/{lid}/history")[1][0]["kind"] == "added"
    assert handle(store, "GET", "/api/activity?limit=5")[0] == 200
    assert handle(store, "GET", "/api/next?who=sam")[1]["step"]["kind"] == "suggest"
    assert handle(store, "GET", "/api/digest?who=sam")[1]["items"] == []


def test_errors_are_400_or_404(store):
    assert handle(store, "POST", "/api/review", {"learning_id": 99, "by": "sam"})[0] == 400
    assert handle(store, "POST", "/api/add", {"nope": 1})[0] == 400
    assert handle(store, "POST", "/api/add", ["not", "a", "dict"])[0] == 400
    assert handle(store, "GET", "/api/learnings/abc")[0] == 400
    assert handle(store, "GET", "/api/unknown")[0] == 404
    assert handle(store, "POST", "/api/query", {})[0] == 404
    assert handle(store, "DELETE", "/api/learnings")[0] == 404


def test_handle_json_round_trip(store):
    out = json.loads(handle_json(store, "POST", "/api/add",
                                 json.dumps({"statement": "x", "level": "observation", "owner": "ana"})))
    assert out["status"] == 200 and out["data"]["learning"]["id"] == 1
    assert json.loads(handle_json(store, "POST", "/api/add", "{bad"))["status"] == 400


def test_seed_walks_the_whole_loop(store):
    seed(store)
    learnings = store.query("", limit=500, trust=None)
    assert {f["level"] for f in learnings} == {"observation", "finding", "insight"}
    assert {f["origin"] for f in learnings} == {"person", "person_with_ai", "ai_agent"}
    chips = [f["chip"]["key"] for f in learnings]
    assert chips.count("contested") == 2 and "draft" in chips and "checked_by_sme" in chips
    assert store.query("", trust="replaced")
    assert store.list_studies(status="requested") and store.list_decisions()[0]["outcome_due"]
    assert {p["role"] for p in store.people()} == {"researcher", "pwdr", "stakeholder"}
    assert sorted(p["name"] for p in store.people() if p["sme"]) == ["Dana", "Sam"]
