"""MCP server: a thin wrapper that exposes the core Store as tools.

Run with:  python -m anchor.mcp_server
The database path comes from the ANCHOR_DB environment variable.

Each MCP client runs its own server process, so identity is per session: set
it once with set_identity (or the ANCHOR_USER environment variable) and every
action is recorded as that person.
"""

from __future__ import annotations

import os
from typing import Any

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .core import DEFAULT_DB_PATH, CoreError, Store

store = Store(DEFAULT_DB_PATH)

mcp = _Server(
    "anchor",
    instructions=(
        "A shared layer of research findings at three tiers (data_point, hypothesis, "
        "insight) and three statuses (proposed, validated, contested). Query before "
        "generating new claims. Propose findings with evidence links where possible. "
        "Never treat a proposed or contested finding as settled. "
        "At the start of a session, call whoami; if no one is set, ask the person "
        "their name and call set_identity so their actions are recorded as them."
    ),
)

# Who this session acts as. Set once, used as the default name on every action.
_me: str | None = os.environ.get("ANCHOR_USER") or None


class _NoIdentity(CoreError):
    pass


def _who(name: str | None) -> str:
    name = (name or "").strip() or _me
    if not name:
        raise _NoIdentity("no one is set for this session: ask the person their name, then call set_identity")
    return name


def _call(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except CoreError as e:
        return {"error": str(e)}


@mcp.tool()
def whoami() -> dict[str, Any]:
    """Who this session is acting as, and their role on the team."""
    if not _me:
        return {"identity": None, "hint": "ask the person their name, then call set_identity"}
    return _call(lambda: {"identity": store.whoami(_me)})


@mcp.tool()
def set_identity(name: str) -> dict[str, Any]:
    """Set who this session acts as. Every later action is recorded as this
    person, with their role shown. New names join with the team's default role."""
    global _me
    result = _call(store.whoami, name)
    if "error" not in result:
        _me = result["name"]
    return {"identity": result} if "error" not in result else result


@mcp.tool()
def people() -> dict[str, Any]:
    """Everyone on the team and their role. Roles inform how much weight a
    validation carries; they never block anyone from acting."""
    return {"people": store.people()}


@mcp.tool()
def set_role(name: str, role: str) -> dict[str, Any]:
    """Change someone's role (see team_config for the role keys). The change is
    logged in the activity feed so everyone can see it."""
    return _call(lambda: store.set_role(name, role, _who(None)))


@mcp.tool()
def query(
    topic: str = "", tier: str | None = None, status: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """Find what is already known about a topic or question.

    Returns matching findings with their tier, status, evidence links, individual
    validators, and any confirmed conflicts. Optional filters: tier (data_point,
    hypothesis, insight) and status (proposed, validated, contested).
    """
    return _call(lambda: {"findings": store.query(topic, tier=tier, status=status, limit=limit)})


@mcp.tool()
def propose(
    statement: str, tier: str, evidence_links: list[int] | None = None, owner: str | None = None
) -> dict[str, Any]:
    """Submit a new finding. It is created with status 'proposed'.

    tier is one of data_point, hypothesis, insight. evidence_links are ids of
    existing findings that support this one. The response includes any validated
    findings that may contradict it, for a human to review. owner defaults to
    this session's identity.
    """
    return _call(lambda: store.propose(statement, tier, _who(owner), evidence_links))


@mcp.tool()
def validate(finding_id: int, note: str | None = None, validated_by: str | None = None) -> dict[str, Any]:
    """Record that a person has validated a finding, with an optional note on why.

    The first validation moves a proposed finding to 'validated'. Each validation
    stays visible individually. The owner cannot validate their own finding.
    validated_by defaults to this session's identity.
    """
    return _call(lambda: store.validate(finding_id, _who(validated_by), note))


@mcp.tool()
def check_conflict(
    statement: str | None = None,
    finding_id: int | None = None,
    confirm_with: int | None = None,
    confirmed_by: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Check whether a finding contradicts an existing validated (or contested) finding.

    Step 1: pass a statement (or the finding_id of a proposed finding). Returns
    validated or contested findings on a similar topic with the signals that suggest a
    contradiction. Nothing is changed. Show these to a human.

    Step 2: only after a human confirms it is a real conflict, call again with
    finding_id, confirm_with (the id of the conflicting finding) and confirmed_by.
    Both findings are then marked 'contested' and stay visible side by side.
    """
    if confirm_with is not None:
        if finding_id is None:
            return {"error": "finding_id is required to confirm a conflict (propose the statement first)"}
        return _call(lambda: store.confirm_conflict(finding_id, confirm_with, _who(confirmed_by), note))
    return _call(store.check_conflict, statement=statement, finding_id=finding_id)


@mcp.tool()
def checkout(finding_id: int, who: str | None = None) -> dict[str, Any]:
    """Mark a finding as being worked on by someone. Advisory only: returns a
    warning if someone else already has it, but does not block."""
    return _call(lambda: store.checkout(finding_id, _who(who)))


@mcp.tool()
def release(finding_id: int, who: str | None = None) -> dict[str, Any]:
    """Release a checked out finding so others know it is free."""
    return _call(lambda: store.release(finding_id, _who(who)))


@mcp.tool()
def team_config() -> dict[str, Any]:
    """How this team has set up ANCHOR: role names and which roles are trusted,
    tier labels, the study template, promotion rules, and which work modes are on.
    Use these labels when talking to people."""
    return store.team_config()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
