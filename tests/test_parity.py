"""Everything the app can do, an AI tool can do over MCP, through the same core."""

import asyncio
import importlib
import inspect
import json

import pytest

from anchor import api
from anchor.core import Store

# Core methods that are building blocks for others rather than actions of their own.
NOT_ACTIONS: set[str] = set()
# Core reads reached through a differently named MCP tool.
MCP_NAME = {"digest": "whats_new"}


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
    assert "error" in _call(server, "add", statement="x is 1", level="observation")
    assert _call(server, "set_identity", name="Ana")["identity"]["role"] == "pwdr"
    lid = _call(server, "add", statement="Conversion is 42 percent", level="observation",
                origin="person_with_ai")["learning"]["id"]
    assert _call(server, "get", learning_id=lid)["owner"] == "Ana"
    assert _call(server, "next_step")["step"]["kind"] == "confirm"
    assert _call(server, "confirm", learning_id=lid, note="Checked the dashboard")["learning"]["stage"] == "shared"
    assert "error" in _call(server, "review", learning_id=lid)  # Ana owns it
    _call(server, "set_identity", name="Sam")
    r = _call(server, "review", learning_id=lid, how="source_data")
    assert r["learning"]["trust"]["summary"].startswith("Checked by 1 peer.")
    assert _call(server, "history", learning_id=lid)["history"][0]["kind"] == "added"
    _call(server, "set_identity", name="Ana")
    assert _call(server, "whats_new")["items"][0]["text"] == f"Sam approved #{lid}"


def test_query_suggests_asking_for_research(server):
    out = _call(server, "query", topic="why do people churn after trial")
    assert "ask_for_research" in out["hint"]


def test_every_work_mode_has_a_guided_prompt(server):
    prompts = {p.name: p for p in asyncio.run(server.mcp.list_prompts())}
    by_mode = {
        "home": "get_started", "plan": "plan_study", "synthesize": "synthesize_notes",
        "learn": "shape_insight", "find": "check_before_claim",
        "review": "review_my_queue", "decide": "find_insights_for_decision",
    }
    assert set(by_mode.values()) | {"request_review", "log_decision", "break_down_text"} <= set(prompts)
    assert all(p.title and p.description for p in prompts.values())
    text = asyncio.run(server.mcp.get_prompt("check_before_claim", {"claim": "Users hate forms"}))
    body = text.messages[0].content.text
    assert "Users hate forms" in body and 'origin="person_with_ai"' in body


def test_ai_tools_add_blocks_with_confidence(server):
    _call(server, "set_identity", name="Ana")
    sid = _call(server, "start_study", question="Why do trials churn?")["study"]["id"]
    src = _call(server, "add_source", study_id=sid, title="Survey", body="12 of 40 said setup was confusing")
    out = _call(server, "add_blocks", study_id=sid, blocks=[
        {"ref": "a", "level": "observation", "statement": "12 of 40 said setup was confusing",
         "sources": [src["source"]["id"]], "confidence": "high", "why": "Direct count"},
        {"level": "finding", "statement": "Setup confusion drives churn", "built_on": ["a"],
         "confidence": "low", "why": "One survey", "assumes": ["Survey takers are like churned users"]}])
    ws = _call(server, "get_workspace", study_id=sid)
    assert [b["confidence"] for b in ws["blocks"]] == ["high", "low"]
    assert all(b["check"]["state"] == "needs_check" for b in ws["blocks"])
    assert _call(server, "check", learning_id=out["ids"][0])["learning"]["check"]["state"] == "checked_by_owner"
    text = asyncio.run(server.mcp.get_prompt("break_down_text", {"text": "Users hate forms.", "study_id": str(sid)}))
    assert "add_blocks" in text.messages[0].content.text


def test_ai_tools_plan_the_analysis(server):
    _call(server, "set_identity", name="Ana")
    sid = _call(server, "start_study", question="Why do trials churn?", decision="Fund onboarding")["study"]["id"]
    q = _call(server, "add_question", study_id=sid, text="Where in setup do trial users get stuck?")["question"]["id"]
    out = _call(server, "add", statement="Trial users get stuck on setup", level="finding", study_id=sid,
                question_id=q, origin="person_with_ai")
    assert out["learning"]["answers"]["id"] == q
    plan = _call(server, "get_workspace", study_id=sid)["plan"]
    assert plan[0]["state"] == "in_progress" and "already_known" in plan[0]
    assert "blocks" in _call(server, "already_known", question_id=q)
    text = asyncio.run(server.mcp.get_prompt("plan_analysis", {"study_id": str(sid)}))
    assert "add_question" in text.messages[0].content.text
