"""Everything the app can do, an AI tool can do over MCP, through the same core."""

import asyncio
import importlib
import inspect
import json

import pytest

from anchor import api
from anchor.core import Store

# Core methods that are building blocks for others rather than actions of their own.
NOT_ACTIONS = {"list_findings"}
# The one core action reached through a differently named MCP tool.
MCP_NAME = {"confirm_conflict": "check_conflict"}


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    # The MCP server opens its database on import, so give it a scratch folder.
    folder = tmp_path_factory.mktemp("mcp")
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(folder)
        mp.delenv("ANCHOR_USER", raising=False)
        mod = importlib.import_module("anchor.mcp_server")
        yield mod


def _tools(server):
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


def _call(server, tool, **args):
    result = asyncio.run(server.mcp.call_tool(tool, args))
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "structured_content") and content.structured_content is not None:
        data = content.structured_content
        return data.get("result", data)
    items = getattr(content, "content", content)
    return json.loads(items[0].text)


def test_every_core_action_is_in_the_api():
    public = {n for n, _ in inspect.getmembers(Store, inspect.isfunction) if not n.startswith("_")}
    served = set(api.ACTIONS) | {method for _, method in api.READS}
    assert public - NOT_ACTIONS - served == set(), "core actions with no API route"


def test_every_api_route_has_an_mcp_tool(server):
    tools = _tools(server)
    served = list(api.ACTIONS) + [method for _, method in api.READS]
    missing = [m for m in served if MCP_NAME.get(m, m) not in tools]
    assert missing == [], "API routes with no MCP tool"


def test_identity_is_set_once_per_session(server):
    assert _call(server, "whoami")["identity"] is None
    assert "error" in _call(server, "propose", statement="x is 1", tier="data_point")
    assert _call(server, "set_identity", name="Ana")["identity"]["role"] == "contributor"
    fid = _call(server, "propose", statement="Conversion is 42 percent", tier="data_point")["finding"]["id"]
    assert _call(server, "get", finding_id=fid)["owner"] == "Ana"
    assert "error" in _call(server, "validate", finding_id=fid)  # Ana owns it
    _call(server, "set_identity", name="Sam")
    r = _call(server, "validate", finding_id=fid, basis="source_data")
    assert r["finding"]["trust"]["summary"].startswith("Validated by 1 peer.")
    assert _call(server, "history", finding_id=fid)["history"][0]["kind"] == "proposed"


def test_query_suggests_asking_for_research(server):
    out = _call(server, "query", topic="why do people churn after trial")
    assert "request_research" in out["hint"]


def test_every_work_mode_has_a_guided_prompt(server):
    prompts = {p.name: p for p in asyncio.run(server.mcp.list_prompts())}
    by_mode = {
        "set up": "get_started", "plan": "plan_study", "analyze": "synthesize_notes",
        "insights": "shape_insight", "explore": "check_before_claim",
        "validate": "review_my_queue", "decide": "find_insights_for_decision",
    }
    assert set(by_mode.values()) | {"request_review", "log_decision"} <= set(prompts)
    assert all(p.title and p.description for p in prompts.values())
    text = asyncio.run(server.mcp.get_prompt("check_before_claim", {"claim": "Users hate forms"}))
    body = text.messages[0].content.text
    assert "Users hate forms" in body and "Never present a proposed or contested finding as settled" in body
