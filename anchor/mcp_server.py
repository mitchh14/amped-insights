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
    def run():
        findings = store.query(topic, tier=tier, status=status, limit=limit)
        out: dict[str, Any] = {"findings": findings}
        if topic.strip() and not any(f["status"] == "validated" for f in findings):
            out["hint"] = (
                "Nothing validated matches this yet. Say so plainly, and offer to ask the "
                "research team with request_research(question=..., from_query=topic)."
            )
        return out
    return _call(run)


@mcp.tool()
def get(finding_id: int) -> dict[str, Any]:
    """Everything needed to judge one finding: tier, status, trust summary,
    each review with role and how it was checked, evidence and what it
    supports, typed links from both sides, conflicts, the study it came from,
    promotion readiness, open review requests, and decisions it was used in."""
    return _call(store.get, finding_id)


@mcp.tool()
def history(finding_id: int) -> dict[str, Any]:
    """Every change to a finding, oldest first. Nothing is erased, so this shows
    what used to be believed and why it changed."""
    return _call(lambda: {"history": store.history(finding_id)})


@mcp.tool()
def activity(limit: int = 50) -> dict[str, Any]:
    """Recent activity across the team, newest first: proposals, reviews,
    conflicts, promotions, studies, decisions, and research requests."""
    return _call(lambda: {"activity": store.activity(limit)})


@mcp.tool()
def propose(
    statement: str,
    tier: str,
    evidence_links: list[int] | None = None,
    study_id: int | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    """Submit a new finding. It is created with status 'proposed'.

    tier is one of data_point, hypothesis, insight. evidence_links are ids of
    existing findings that support this one. study_id places it in a study so it
    carries that study's objective and decision. The response includes any
    validated findings that may contradict it, for a human to review. owner
    defaults to this session's identity.
    """
    return _call(lambda: store.propose(statement, tier, _who(owner), evidence_links, study_id))


@mcp.tool()
def promote(finding_id: int, statement: str | None = None, note: str | None = None) -> dict[str, Any]:
    """Promote a data point to a hypothesis, or a hypothesis to an insight.

    Creates a new finding one tier up, linked back to the original, which stays
    as it was. Pass statement to reword it for what the evidence now supports,
    and note to say why. Anyone can promote; check the finding's `promotion`
    field first to see whether it meets the team's rule. Warnings explain any
    gaps (not validated, contested, no evidence) and should be shown to the person.
    """
    return _call(lambda: store.promote(finding_id, _who(None), statement, note))


@mcp.tool()
def revise(finding_id: int, statement: str, note: str | None = None) -> dict[str, Any]:
    """Respond to review feedback with a new version of a finding. The new
    version keeps the tier, evidence, and study and links back to the original,
    which stays as it was. Reviewers who asked for changes are asked to look again."""
    return _call(lambda: store.revise(finding_id, _who(None), statement, note))


@mcp.tool()
def start_study(
    title: str,
    objective: str | None = None,
    decision: str | None = None,
    method: str | None = None,
    sample: str | None = None,
    status: str = "planned",
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Open a study: why we are looking (objective), the business decision it
    serves, how (method), and who or what (sample). Only a title is required;
    missing parts come back as warnings. fields holds the team's own template
    fields (see team_config). status is planned, running, done, requested, or closed.
    Capture findings into it with propose(study_id=...)."""
    return _call(lambda: store.start_study(
        title, _who(None), objective, decision, method, sample, status, fields))


@mcp.tool()
def request_research(
    question: str,
    decision: str | None = None,
    from_decision_id: int | None = None,
    from_query: str | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask the research team a question. It lands as a study with status
    'requested' for them to pick up. Say which decision it would inform.
    Link where it came from: from_decision_id when a decision's outcome raised
    it, or from_query when a search found nothing trusted. Suggest this when
    query returns nothing validated. fields holds any intake fields from the
    team's study template (see team_config)."""
    return _call(lambda: store.request_research(
        question, _who(None), decision, from_decision_id, from_query, fields))


@mcp.tool()
def update_study(
    study_id: int,
    title: str | None = None,
    objective: str | None = None,
    decision: str | None = None,
    method: str | None = None,
    sample: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update a study's details, move its status (requested, planned, running,
    done, closed), or change who owns it. Only the values you pass change.
    Previous values are kept in its history."""
    changes = {k: v for k, v in dict(
        title=title, objective=objective, decision=decision, method=method,
        sample=sample, status=status, owner=owner, fields=fields,
    ).items() if v is not None}
    return _call(lambda: store.update_study(study_id, _who(None), **changes))


@mcp.tool()
def get_study(study_id: int) -> dict[str, Any]:
    """A study's objective, the decision it serves, method, sample, template
    fields, history, and its findings grouped by tier."""
    return _call(store.get_study, study_id)


@mcp.tool()
def list_studies(status: str | None = None, owner: str | None = None) -> dict[str, Any]:
    """Studies, newest first. Filter by status (requested, planned, running,
    done, closed) or owner."""
    return _call(lambda: {"studies": store.list_studies(status, owner)})


@mcp.tool()
def validate(
    finding_id: int,
    outcome: str = "approve",
    note: str | None = None,
    basis: str | None = None,
    validated_by: str | None = None,
) -> dict[str, Any]:
    """Review a finding. outcome is approve, changes_requested (say what to
    change in note), or disagree (say why in note). basis is how the reviewer
    checked: a key from team_config's checks (for example evidence, source_data,
    reproduced, judgment).

    Each review stays visible with the reviewer's role. A person's latest
    review is the one that counts. A finding is validated while at least one
    current review approves it. The owner cannot review their own finding.
    Only record a review the person actually gave; never review on your own.
    validated_by defaults to this session's identity.
    """
    return _call(lambda: store.validate(finding_id, _who(validated_by), note, outcome, basis))


@mcp.tool()
def request_validation(
    finding_id: int,
    people: list[str] | None = None,
    roles: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Ask named people, or anyone in a role (for example ["researcher"]), to
    review a finding. It shows in their queue until one of them reviews it."""
    return _call(lambda: store.request_validation(finding_id, _who(None), people, roles, note))


@mcp.tool()
def withdraw_request(request_id: int) -> dict[str, Any]:
    """Withdraw an open review request that is no longer needed."""
    return _call(lambda: store.withdraw_request(request_id, _who(None)))


@mcp.tool()
def my_queue(who: str | None = None) -> dict[str, Any]:
    """What is waiting on this person: findings they were asked to review,
    their own findings where a reviewer asked for changes or disagreed, and
    review requests they made that are still open. who defaults to this
    session's identity."""
    return _call(lambda: store.my_queue(_who(who)))


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
def link(from_id: int, to_id: int, type: str, note: str | None = None) -> dict[str, Any]:
    """Say how two findings relate. type is one of:
    supports (from_id is evidence for to_id), extends (from_id builds on to_id),
    duplicates (they say the same thing), or contradicts (a human has confirmed
    they conflict; both become contested). get shows every link from both sides.
    """
    return _call(lambda: store.link(from_id, to_id, type, _who(None), note))


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
def log_decision(
    title: str, finding_ids: list[int] | None = None, note: str | None = None, outcome: str | None = None
) -> dict[str, Any]:
    """Record a decision and the findings used to make it, in one step. Use this
    when a person says they used insights in a decision. Findings that are not
    validated, or are contested, come back as warnings to show the person.
    The result lists everyone in the chain behind those findings."""
    return _call(lambda: store.log_decision(title, _who(None), finding_ids, note, outcome))


@mcp.tool()
def update_decision(
    decision_id: int,
    outcome: str | None = None,
    note: str | None = None,
    add_finding_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Add what happened after a decision (outcome), a note, or more findings
    that were used. If the outcome raises a new question, follow with
    request_research(from_decision_id=...)."""
    return _call(lambda: store.update_decision(decision_id, _who(None), outcome, note, add_finding_ids))


@mcp.tool()
def get_decision(decision_id: int) -> dict[str, Any]:
    """A decision with the findings it used (trust now and status when used),
    which of them are now contested (at_risk), research asked for from it, and
    credits: everyone in the chain behind it and what they did."""
    return _call(store.get_decision, decision_id)


@mcp.tool()
def list_decisions(made_by: str | None = None) -> dict[str, Any]:
    """Decisions, newest first, optionally only those made by one person."""
    return _call(lambda: {"decisions": store.list_decisions(made_by)})


@mcp.tool()
def person(name: str | None = None) -> dict[str, Any]:
    """A person's role, decisions they made, and decisions their work
    contributed to. name defaults to this session's identity."""
    return _call(lambda: store.person(_who(name)))


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
