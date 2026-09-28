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
        "A shared layer of team learnings. Each learning has a level (observation: what we saw; "
        "finding: what we think it means, not yet an insight; insight: what it means for us and what "
        "to do), an origin (person, person_with_ai, ai_agent), a stage (draft, shared, replaced), and "
        "one trust state (Not reviewed, Needs changes, Checked by peers, Checked by an SME, Contested). "
        "Query before claiming anything new. When you mention a learning, give its trust summary, and "
        "never present one that is Not reviewed, Needs changes, or Contested as settled. Anything you "
        "draft is added with origin person_with_ai (or ai_agent when acting on your own), which makes it "
        "a draft the person confirms. Never review on a person's behalf unless they tell you their review. "
        "At the start of a session, call whoami; if no one is set, ask the person their name and call "
        "set_identity so their actions are recorded as them. Then next_step says what is most worth doing."
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
    """Who this session is acting as, their role, and whether they are an SME."""
    if not _me:
        return {"identity": None, "hint": "ask the person their name, then call set_identity"}
    return _call(lambda: {"identity": store.whoami(_me)})


@mcp.tool()
def set_identity(name: str) -> dict[str, Any]:
    """Set who this session acts as. Every later action is recorded as this
    person. New names join with the team's default role."""
    global _me
    result = _call(store.whoami, name)
    if "error" not in result:
        _me = result["name"]
    return {"identity": result} if "error" not in result else result


@mcp.tool()
def people() -> dict[str, Any]:
    """Everyone on the team, their role, and who is an SME. SME approvals show
    as Checked by an SME; roles never block anyone from acting."""
    return {"people": store.people()}


@mcp.tool()
def set_person(name: str, role: str | None = None, sme: bool | None = None) -> dict[str, Any]:
    """Change someone's role (see team_config for role keys), or whether they
    are an SME. The change is logged so everyone can see it."""
    return _call(lambda: store.set_person(name, _who(None), role, sme))


@mcp.tool()
def query(topic: str = "", level: str | None = None, trust: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Find what the team already knows about a topic or question.

    Returns matching learnings with level, stage, origin, trust, evidence,
    reviews, and conflicts. Optional filters: level (observation, finding,
    insight) and trust (not_reviewed, needs_changes, checked_by_peers,
    checked_by_sme, contested, draft, replaced).
    """
    def run():
        found = store.query(topic, level=level, trust=trust, limit=limit)
        out: dict[str, Any] = {"learnings": found}
        if topic.strip() and not any(f["trust"]["state"] in ("checked_by_sme", "checked_by_peers") for f in found):
            out["hint"] = (
                "Nothing checked matches this yet. Say so plainly, and offer to ask for research "
                "with ask_for_research(question=..., from_query=topic)."
            )
        return out
    return _call(run)


@mcp.tool()
def get(learning_id: int) -> dict[str, Any]:
    """Everything needed to judge one learning: level, stage, origin and
    whether its owner confirmed it, trust with each review, evidence, links,
    conflicts, its study, promotion readiness, open review requests, and
    decisions it was used in."""
    return _call(store.get, learning_id)


@mcp.tool()
def history(learning_id: int) -> dict[str, Any]:
    """Every change to a learning, oldest first, each as a plain sentence.
    Nothing is erased, so this shows what used to be believed and why it changed."""
    return _call(lambda: {"history": store.history(learning_id)})


@mcp.tool()
def activity(limit: int = 50) -> dict[str, Any]:
    """The team's full record, newest first. For what matters to this person,
    use whats_new instead."""
    return _call(lambda: {"activity": store.activity(limit)})


@mcp.tool()
def whats_new(since: str | None = None, limit: int = 30) -> dict[str, Any]:
    """What changed for this person: changes to learnings they own, reviewed,
    used, or follow; reviews asked of them; decisions at risk; and moments
    worth celebrating. Ranked by importance (1 do now, 2 news, 3 digest only).
    since is an ISO time. Use this to brief the person at the start of a session."""
    return _call(lambda: store.digest(_who(None), since, limit))


@mcp.tool()
def next_step() -> dict[str, Any]:
    """The one thing most worth doing now for this person, plus any moment to share."""
    return _call(lambda: store.next_step(_who(None)))


@mcp.tool()
def mark_seen(keys: list[str]) -> dict[str, Any]:
    """Mark digest items or moments as seen (keys like "e12"), or set a next
    step aside (its key) when the person says "not now"."""
    return _call(lambda: store.mark_seen(_who(None), keys))


@mcp.tool()
def add(
    statement: str,
    level: str,
    origin: str = "person",
    evidence: list[int] | None = None,
    study_id: int | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    """Write down a learning. level is observation, finding, or insight.

    origin is who made it: person (the person wrote it), person_with_ai (you
    helped write it), or ai_agent (you made it on your own). Anything made
    with AI starts as a draft until its owner confirms it. evidence is the ids
    of learnings that support it. study_id places it in a study. The response
    includes checked learnings that may conflict with it, for a person to judge.
    owner defaults to this session's identity.
    """
    return _call(lambda: store.add(statement, level, _who(owner), evidence, study_id, origin))


@mcp.tool()
def confirm(learning_id: int, statement: str | None = None, note: str | None = None) -> dict[str, Any]:
    """The owner confirms an AI draft: they checked it and stand behind it.
    Only call this when the person says so. Pass statement if they changed the
    wording, and note for what they checked or changed."""
    return _call(lambda: store.confirm(learning_id, _who(None), statement, note))


@mcp.tool()
def promote(learning_id: int, statement: str | None = None, note: str | None = None,
            origin: str = "person") -> dict[str, Any]:
    """Take a learning up a level: an observation to a finding, or a finding
    to an insight. Adds a new learning linked back to the original, which stays
    as it was. Pass statement to reword it for what the evidence supports. Check
    `promotion` on the learning first. Show any warnings to the person."""
    return _call(lambda: store.promote(learning_id, _who(None), statement, note, origin))


@mcp.tool()
def revise(learning_id: int, statement: str, note: str | None = None, origin: str = "person") -> dict[str, Any]:
    """Write a new version of a learning, for example after review feedback.
    The old one becomes Replaced. Reviewers who asked for changes are asked to
    look again."""
    return _call(lambda: store.revise(learning_id, _who(None), statement, note, origin))


@mcp.tool()
def start_study(question: str, decision: str | None = None, hypothesis: str | None = None,
                fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Start a study with its question and the decision it serves. Method and
    sample are asked for when it is marked running (update_study). hypothesis is
    what the study expects to find, if anything. Add learnings into it with
    add(study_id=...)."""
    return _call(lambda: store.start_study(question, _who(None), decision, hypothesis, fields))


@mcp.tool()
def ask_for_research(question: str, decision: str | None = None, from_decision_id: int | None = None,
                     from_query: str | None = None) -> dict[str, Any]:
    """Ask a research question. It lands as a Requested study for someone to
    pick up. Say which decision it would inform. Suggest this when query finds
    nothing checked (from_query), or a decision's outcome raises a question
    (from_decision_id)."""
    return _call(lambda: store.ask_for_research(question, _who(None), decision, from_decision_id, from_query))


@mcp.tool()
def update_study(
    study_id: int,
    question: str | None = None,
    decision: str | None = None,
    hypothesis: str | None = None,
    method: str | None = None,
    sample: str | None = None,
    learned: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update a study, move it to another stage (requested, planned, running,
    finished, dropped), or change its owner. Only the values you pass change.
    The result's study.needs lists what the stage still asks for."""
    changes = {k: v for k, v in dict(
        question=question, decision=decision, hypothesis=hypothesis, method=method, sample=sample,
        learned=learned, status=status, owner=owner, fields=fields,
    ).items() if v is not None}
    return _call(lambda: store.update_study(study_id, _who(None), **changes))


@mcp.tool()
def get_study(study_id: int) -> dict[str, Any]:
    """A study's question, decision, hypothesis, method, sample, wrap up,
    history, learnings by level, and what its stage still needs."""
    return _call(store.get_study, study_id)


@mcp.tool()
def list_studies(status: str | None = None, owner: str | None = None) -> dict[str, Any]:
    """Studies, newest first. Filter by status (requested, planned, running,
    finished, dropped) or owner."""
    return _call(lambda: {"studies": store.list_studies(status, owner)})


@mcp.tool()
def review(learning_id: int, verdict: str = "approve", how: str | None = None, note: str | None = None,
           by: str | None = None) -> dict[str, Any]:
    """Record a person's review. verdict is approve, changes (say what should
    change in note), or disagree (say why in note). how is how they checked: a
    key from team_config's checks. Only record a review the person actually
    gave; never review on your own. by defaults to this session's identity."""
    return _call(lambda: store.review(learning_id, _who(by), verdict, how, note))


@mcp.tool()
def ask_for_review(learning_id: int, people: list[str] | None = None, roles: list[str] | None = None,
                   note: str | None = None) -> dict[str, Any]:
    """Ask named people, anyone in a role, or any SME (roles=["sme"]) to review
    a learning. It shows in their queue until one of them reviews it."""
    return _call(lambda: store.ask_for_review(learning_id, _who(None), people, roles, note))


@mcp.tool()
def withdraw_request(request_id: int) -> dict[str, Any]:
    """Withdraw an open review request that is no longer needed."""
    return _call(lambda: store.withdraw_request(request_id, _who(None)))


@mcp.tool()
def my_queue(who: str | None = None) -> dict[str, Any]:
    """What is waiting on this person: reviews asked of them, their AI drafts to
    confirm, feedback on their learnings, their open requests, decisions at
    risk, and decisions whose outcome is due."""
    return _call(lambda: store.my_queue(_who(who)))


@mcp.tool()
def check_conflict(statement: str | None = None, learning_id: int | None = None,
                   confirm_with: int | None = None, note: str | None = None) -> dict[str, Any]:
    """Check whether a learning conflicts with one already checked (or contested).

    Step 1: pass a statement, or a learning_id. Returns learnings on a similar
    topic with the signals that suggest a conflict. Nothing changes. Show them
    to the person.

    Step 2: only after the person confirms a real conflict, call again with
    learning_id and confirm_with (the other learning's id). Both become Contested.
    """
    if confirm_with is not None:
        if learning_id is None:
            return {"error": "learning_id is required to confirm a conflict (add the statement first)"}
        return _call(lambda: store.link(learning_id, confirm_with, "conflicts_with", _who(None), note))
    return _call(store.check_conflict, statement=statement, learning_id=learning_id)


@mcp.tool()
def link(from_id: int, to_id: int, type: str, note: str | None = None) -> dict[str, Any]:
    """Say how two learnings relate. type is supports (from_id is evidence for
    to_id), builds_on (from_id builds on to_id), same_as (they say the same
    thing), or conflicts_with (the person confirmed they conflict)."""
    return _call(lambda: store.link(from_id, to_id, type, _who(None), note))


@mcp.tool()
def working_on(learning_id: int, on: bool = True) -> dict[str, Any]:
    """Say this person is working on a learning (on=False when they stop).
    A soft hold: it never stops anyone else."""
    return _call(lambda: store.working_on(learning_id, _who(None), on))


@mcp.tool()
def follow(learning_id: int, on: bool = True) -> dict[str, Any]:
    """Follow a learning to hear about changes to it in whats_new."""
    return _call(lambda: store.follow(learning_id, _who(None), on))


@mcp.tool()
def log_decision(title: str, learning_ids: list[int] | None = None, note: str | None = None) -> dict[str, Any]:
    """Record a decision and the learnings it relied on. Learnings that are not
    checked, or are contested, come back as warnings to show the person. What
    happened is added later with update_decision."""
    return _call(lambda: store.log_decision(title, _who(None), learning_ids, note))


@mcp.tool()
def update_decision(decision_id: int, outcome: str | None = None, note: str | None = None,
                    add_learning_ids: list[int] | None = None) -> dict[str, Any]:
    """Add what happened after a decision (outcome), a note, or more learnings
    it relied on. If the outcome raises a question, follow with
    ask_for_research(from_decision_id=...)."""
    return _call(lambda: store.update_decision(decision_id, _who(None), outcome, note, add_learning_ids))


@mcp.tool()
def get_decision(decision_id: int) -> dict[str, Any]:
    """A decision with the learnings it relied on (trust now and when used),
    which are now contested (at_risk), whether its outcome is due, research it
    raised, and everyone in the chain behind it."""
    return _call(store.get_decision, decision_id)


@mcp.tool()
def list_decisions(made_by: str | None = None) -> dict[str, Any]:
    """Decisions, newest first, optionally only those made by one person."""
    return _call(lambda: {"decisions": store.list_decisions(made_by)})


@mcp.tool()
def person(name: str | None = None) -> dict[str, Any]:
    """A person's role, SME standing, decisions they made, and decisions their
    work contributed to. name defaults to this session's identity."""
    return _call(lambda: store.person(_who(name)))


@mcp.tool()
def team_config() -> dict[str, Any]:
    """How this team set up ANCHOR: role names, level labels, how-I-checked
    choices, the study template, and promotion rules. Use these labels when
    talking to people."""
    return store.team_config()


# ---------------------------------------------------------------------------
# Guided prompts: one or more per work mode, so people can pick a task in
# their AI tool's prompt picker instead of knowing which tools to call.
# ---------------------------------------------------------------------------

GROUND_RULES = """Ground rules for working with ANCHOR (words from its glossary):
- Start with whoami. If no one is set, ask the person their name and call set_identity.
- Query before you claim anything. Say what the team already knows, and cite learning ids.
- For every learning you mention, give its level and its trust in plain words.
- Never present a learning that is Not reviewed, Needs changes, Contested, or a Draft as settled.
- Surface conflicts. If a learning is contested, show both sides.
- You draft; the person decides. Anything you helped write is added with origin="person_with_ai", so it stays a draft until the person confirms it. Ask them what they checked or changed, then call confirm.
- Never review on your own, and check with the person before adding, promoting, or logging anything."""


def _prompt(task: str, steps: str) -> str:
    return f"{task}\n\n{steps}\n\n{GROUND_RULES}"


@mcp.prompt(name="get_started", title="Get started with ANCHOR")
def prompt_get_started() -> str:
    """Set who you are, hear what changed, and get one next step."""
    return _prompt(
        "Help me get started with ANCHOR, my team's shared layer of learnings.",
        "1. Call whoami, and set_identity if needed.\n"
        "2. Call team_config and explain, briefly, the levels and trust states in my team's words.\n"
        "3. Call whats_new and tell me, in a few lines, what changed for me. Lead with anything to do now.\n"
        "4. Call next_step and offer to help with it. If there is a moment, share it first.",
    )


@mcp.prompt(name="plan_study", title="Plan a study")
def prompt_plan_study(question: str, decision: str = "") -> str:
    """Mode 1: plan a study tied to a decision, after checking what is already known."""
    return _prompt(
        f"Help me plan a study to answer: {question}"
        + (f"\nThe decision it serves: {decision}" if decision else ""),
        "1. query the question first. If checked learnings already answer it, say so plainly: "
        "the best outcome may be no new study at all.\n"
        "2. Check list_studies(status='requested') for a matching request I could pick up instead.\n"
        "3. If a study is still needed, draft the question, the decision it serves, a hypothesis if one "
        "is useful, and the method and sample. Ask me about anything unclear.\n"
        "4. Once I agree, call start_study, then update_study with method, sample, and status='running' "
        "when I am ready to run it.",
    )


@mcp.prompt(name="synthesize_notes", title="Synthesize my notes")
def prompt_synthesize_notes(notes: str, study_id: str = "") -> str:
    """Mode 2: turn raw notes into observations and findings with evidence."""
    return _prompt(
        "Help me turn these notes into learnings:\n\n" + notes,
        "1. Separate what we saw (observations, with no reading into them) from what we think it means "
        "(findings).\n"
        "2. For each, query for learnings that already say it, support it, or conflict with it.\n"
        "3. Show me the draft list: statement, level, evidence, and any duplicates or conflicts found.\n"
        "4. For the ones I keep, add them with origin=\"person_with_ai\""
        + (f" and study_id={study_id}" if study_id else "")
        + ", observations first so findings can use them as evidence.\n"
        "5. Then walk me through confirming each draft: ask what I checked or changed, and call confirm.",
    )


@mcp.prompt(name="shape_insight", title="Shape an insight")
def prompt_shape_insight(topic: str) -> str:
    """Mode 3: find findings ready to become insights, and promote with care."""
    return _prompt(
        f"Help me find what is ready to become an insight about: {topic}",
        "1. query the topic for findings. For each, get it and show its trust, evidence, conflicts, "
        "and its promotion readiness under the team's rule.\n"
        "2. Tell me which look ready and which do not, and why. Point out gaps honestly.\n"
        "3. If I choose one, help me word the insight: what it means for us and what to do. "
        "Then call promote with that statement, a short note, and origin=\"person_with_ai\" if you "
        "wrote the wording, and help me confirm it.",
    )


@mcp.prompt(name="check_before_claim", title="Check before I claim")
def prompt_check_before_claim(claim: str) -> str:
    """Check a claim against what is known before sharing it."""
    return _prompt(
        f"Before I share this, check it against what we know: {claim}",
        "1. query the claim and call check_conflict with it as the statement.\n"
        "2. Tell me what supports it, what conflicts with it, and what is not checked yet.\n"
        "3. Give me a one line verdict: well supported, partly supported, contradicted, or unknown.\n"
        "4. If nothing checked exists, offer ask_for_research. If I want to record the claim, offer to "
        "add it with evidence.",
    )


@mcp.prompt(name="request_review", title="Ask for review")
def prompt_request_review(learning_id: str) -> str:
    """Mode 5: ask the right people to review a learning."""
    return _prompt(
        f"Help me get learning {learning_id} reviewed.",
        "1. get the learning and summarize its trust so far. If it is a draft, help me confirm it first.\n"
        "2. Suggest who to ask, using people and team_config: an SME in the topic weighs most, and "
        "SMEs can sit on any team.\n"
        "3. After I choose, call ask_for_review with the people or roles (\"sme\" for any SME) and a note.",
    )


@mcp.prompt(name="review_my_queue", title="Review my queue")
def prompt_review_my_queue() -> str:
    """Mode 5: work through what is waiting on you."""
    return _prompt(
        "Walk me through what is waiting on me in ANCHOR.",
        "1. Call my_queue.\n"
        "2. For each learning I was asked to review, show its statement, origin, evidence, study, and "
        "trust. Ask me: approve, ask for changes, or disagree, how I checked, and a note. Record exactly "
        "what I say with review. Do not decide for me.\n"
        "3. For my AI drafts, show each one and ask what I checked or changed, then confirm it.\n"
        "4. For feedback on my learnings, show each concern and offer to revise.\n"
        "5. Mention decisions at risk, and decisions whose outcome is due.",
    )


@mcp.prompt(name="find_insights_for_decision", title="Find insights for a decision")
def prompt_find_insights(decision: str) -> str:
    """Mode 6: find what the team knows that bears on a decision."""
    return _prompt(
        f"I need to decide: {decision}\nWhat do we already know that bears on this?",
        "1. query the decision's key topics. Lead with checked insights, then checked findings and "
        "observations. Clearly separate anything not reviewed, needing changes, or contested.\n"
        "2. For each, give its trust summary and the study it came from, if any.\n"
        "3. Say plainly where the evidence is thin. If nothing checked exists, offer ask_for_research "
        "with the decision filled in.\n"
        "4. When I decide, offer to log_decision with the learnings I used.",
    )


@mcp.prompt(name="log_decision", title="Log a decision")
def prompt_log_decision(decision: str) -> str:
    """Mode 6: record a decision and the learnings it relied on."""
    return _prompt(
        f"Log this decision in ANCHOR: {decision}",
        "1. Ask which learnings I used, or query to help me find them.\n"
        "2. Show their trust, and warn me about anything not checked.\n"
        "3. Call log_decision with a clear title, the learning ids, and my note.\n"
        "4. Tell me the app will ask what happened later. If a new question comes up, offer "
        "ask_for_research(from_decision_id=...).",
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
