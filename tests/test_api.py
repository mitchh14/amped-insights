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


def test_seed_shows_every_check_state(store):
    seed(store)
    ws = handle(store, "GET", "/api/workspaces/1")[1]
    assert {b["check"]["state"] for b in ws["blocks"]} == {
        "needs_check", "checked_by_owner", "checked_by_peers", "checked_by_sme", "needs_changes", "disagreement"}
    assert {b["level"] for b in ws["blocks"]} == {"observation", "finding", "insight"}
    assert len(ws["sources"]) == 4 and ws["package"]
    assert [p["ok"] for p in ws["base"]] == [True, True, True, False]
    assert any(b["unchecked_parts"] for b in ws["blocks"]) and any(b["confidence"] == "low" for b in ws["blocks"])
    assert handle(store, "GET", "/api/needs-check?who=Jordan")[1]["items"][0]["reason"] == "Your AI draft to check"
    assert sorted(p["name"] for p in store.people() if p["sme"]) == ["Dana", "Sam"]
