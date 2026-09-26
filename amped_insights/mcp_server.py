"""MCP server: a thin wrapper that exposes the core Store as tools.

Run with:  python -m amped_insights.mcp_server
The database path comes from the AMPED_DB environment variable.
"""

from __future__ import annotations

from typing import Any

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .core import DEFAULT_DB_PATH, CoreError, Store

store = Store(DEFAULT_DB_PATH)

mcp = _Server(
    "amped-insights",
    instructions=(
        "A shared layer of research findings at three tiers (data_point, hypothesis, "
        "insight) and three statuses (proposed, validated, contested). Query before "
        "generating new claims. Propose findings with evidence links where possible. "
        "Never treat a proposed or contested finding as settled."
    ),
)


def _call(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except CoreError as e:
        return {"error": str(e)}


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
    statement: str, tier: str, owner: str, evidence_links: list[int] | None = None
) -> dict[str, Any]:
    """Submit a new finding. It is created with status 'proposed'.

    tier is one of data_point, hypothesis, insight. evidence_links are ids of
    existing findings that support this one. The response includes any validated
    findings that may contradict it, for a human to review.
    """
    return _call(store.propose, statement, tier, owner, evidence_links)


@mcp.tool()
def validate(finding_id: int, validated_by: str, note: str | None = None) -> dict[str, Any]:
    """Record that a person has validated a finding, with an optional note on why.

    The first validation moves a proposed finding to 'validated'. Each validation
    stays visible individually. The owner cannot validate their own finding.
    """
    return _call(store.validate, finding_id, validated_by, note)


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
        return _call(store.confirm_conflict, finding_id, confirm_with, confirmed_by, note)
    return _call(store.check_conflict, statement=statement, finding_id=finding_id)


@mcp.tool()
def checkout(finding_id: int, who: str) -> dict[str, Any]:
    """Mark a finding as being worked on by someone. Advisory only: returns a
    warning if someone else already has it, but does not block."""
    return _call(store.checkout, finding_id, who)


@mcp.tool()
def release(finding_id: int, who: str) -> dict[str, Any]:
    """Release a checked out finding so others know it is free."""
    return _call(store.release, finding_id, who)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
