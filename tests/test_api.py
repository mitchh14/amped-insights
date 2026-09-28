import json

import pytest

from anchor.api import handle, handle_json
from anchor.core import Store
from anchor.seed import seed


def test_propose_then_query(store):
    status, r = handle(store, "POST", "/api/propose",
                       {"statement": "Conversion is 42 percent", "tier": "data_point", "owner": "ana"})
    assert status == 200
    fid = r["finding"]["id"]
    status, found = handle(store, "GET", "/api/findings?q=conversion&status=proposed")
    assert status == 200 and [f["id"] for f in found] == [fid]
    assert handle(store, "GET", f"/api/findings/{fid}")[1]["statement"] == "Conversion is 42 percent"
    assert handle(store, "GET", f"/api/findings/{fid}/history")[1][0]["kind"] == "proposed"
    assert handle(store, "GET", "/api/activity?limit=5")[0] == 200


def test_errors_are_400_or_404(store):
    assert handle(store, "POST", "/api/validate", {"finding_id": 99, "validated_by": "sam"})[0] == 400
    assert handle(store, "POST", "/api/propose", {"nope": 1})[0] == 400
    assert handle(store, "POST", "/api/propose", ["not", "a", "dict"])[0] == 400
    assert handle(store, "GET", "/api/findings/abc")[0] == 400
    assert handle(store, "GET", "/api/unknown")[0] == 404
    assert handle(store, "POST", "/api/query", {})[0] == 404
    assert handle(store, "DELETE", "/api/findings")[0] == 404


def test_handle_json_round_trip(store):
    out = json.loads(handle_json(store, "POST", "/api/propose",
                                 json.dumps({"statement": "x", "tier": "data_point", "owner": "ana"})))
    assert out["status"] == 200 and out["data"]["finding"]["id"] == 1
    assert json.loads(handle_json(store, "POST", "/api/propose", "{bad"))["status"] == 400


def test_seed_has_every_tier_and_a_contested_pair(store):
    seed(store)
    findings = store.query("", limit=500)
    assert {f["tier"] for f in findings} == {"data_point", "hypothesis", "insight"}
    assert sum(f["status"] == "contested" for f in findings) == 2
    assert store.list_studies(status="requested") and store.list_decisions()
    assert {p["role"] for p in store.people()} >= {"researcher", "trusted_reviewer", "contributor", "stakeholder"}
