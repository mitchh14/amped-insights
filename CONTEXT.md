# Project Context: ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

See [PRINCIPLES.md](PRINCIPLES.md) for why this exists and the values behind it. This doc covers the build: schema, actions, architecture. The words are defined in [docs/GLOSSARY.md](docs/GLOSSARY.md).

## The problem

The full statement, with causes and symptoms for each audience, is in [docs/PROBLEM.md](docs/PROBLEM.md). In short:

As AI makes it fast for anyone to generate an analysis or a claim about users, the risk is not slow research. It is ungrounded research. What teams learn lives in decks, docs, and chat threads with no shared place to check what the organization already knows. People re-research questions that already have answers, contradictions pile up quietly, and nobody can tell what is still true, what was a one-time guess, or what has been checked at all.

The fix is not a better search tool. It is a shared, checkable layer of learnings, at different levels, that any person or AI agent can query before generating something new, and that stays honest about who said what, whether an AI drafted it, and how sure anyone should be.

The sharpest part of the problem is long AI text. An AI can write a confident page of analysis in seconds, and the assumptions inside it are easy to miss. ANCHOR governs insights, not people: it takes that work apart into building blocks, one claim each, shows what each block rests on, and asks a person to check each one before anything is built on it.

## Current focus: the workbench

The workbench is the core the rest builds on. A workspace holds a question, the decision it serves, and a base of context, method, and notes. Blocks build up from it: observations from sources, findings from observations, insights from findings. Each block has one check state, and anything built on an unchecked block shows it. A plan breaks the question into a few sub-questions from the top, findings and insights say which one they answer, and each sub-question shows what other workspaces already know about it. AI blocks say how confident the AI is, why, and what it assumes. Long AI text can be broken down into blocks. Checked insights go into a package. Decisions, narratives, and research requests come later; see [docs/EXPERIENCE.md](docs/EXPERIENCE.md).

## Why now

Researcher roles are shifting from executing every study personally to orchestrating and curating a shared body of knowledge that AI agents and other contributors can draw from and add to. This framework is built for that shift. Researchers become the people who hold and grow the trust layer, not the only people allowed to produce insights.

## Core principles

1. Govern insights, not people. What gets checked is a claim and every part that makes it up. Nobody is ranked or blocked.
2. Transparency over authority. The system does not grant credibility by role. It makes the basis for credibility visible: who stated something, what evidence backs it, who reviewed it. Trust is earned by the work, not handed out by a badge.
3. Not all learnings are equal, and the system should never pretend they are. An observation, a finding, and an insight are different things, and one that nobody has reviewed looks different from one an SME has checked.
4. More than one person can review a learning. Reviews are shown individually, not merged into a single verdict, so agreement and disagreement are both visible.
5. Contradictions get surfaced, not hidden or silently overwritten. When a new learning conflicts with a checked one, both stay visible as Contested and the conflict triggers a re-evaluation, with the history of what changed and why kept intact.
6. Framework over system. This should be a small set of primitives (add, confirm, review, query, check for conflicts) that teams can run and adapt themselves, not a heavy platform people have to migrate into.
7. Data stays where the org already trusts it, self-hosted by default, no required outbound calls, storage that stays boring and inspectable so the data always stays yours. See PRINCIPLES.md for the full reasoning.
8. Everyone generates insights, by design. Review is open to everyone, with varied trust: the most trusted reviews come from the SMEs the team names, from any team. Roles inform, they never block.
9. Fit the team, not the other way around. Teams trust different roles differently and work in their own ways. Setup bends ANCHOR to the team. Defaults are open, and the people implementing it decide how much structure to add.
10. Slow and steady. Speed is good, but taking time to check each part and understand how it fits the whole is what gets to the right outcome. Slow can be fast: checking a small block now is quicker than unwinding a decision later. See [PRINCIPLES.md](PRINCIPLES.md).

## The user types

Everyone generates insights. That is the intended state. Anyone can also review, but trust varies by who is reviewing, and the system shows that instead of blocking anyone.

- Researchers: accountable for the trust layer. They are the ones most likely to chase down contradictions and follow up on findings tied to real decisions, because they have the most at stake in getting it right. The framework lets the most engaged people lead; it does not make researchers look more important than anyone else.
- PwDR (people who do research): everyone else contributing learnings. PMs, analysts, designers, ops folks. They add, connect, and generate insights, and they review each other's work.
- Stakeholders: the people who use learnings to make decisions. They find checked learnings, record when they used one, say what happened, and raise new questions that start the next round of research.
- SMEs: not a role but a standing the team gives people it trusts in an area, inside or outside research (for example a data science lead or a domain expert). Their approvals show as "Checked by an SME".
- AI agents: not a role but an origin. What an AI drafts is marked as such, always has a named owner, and stays a draft until that owner confirms it.

See [docs/FLOW.md](docs/FLOW.md) for how these people move through the work modes.

## The three levels of a learning

1. Observation: what we saw or measured, with no reading into it (example: mobile checkout conversion is 42 percent). Can be checked on accuracy alone.
2. Finding: a pattern or reading across observations. Not yet an insight. This level needs the most guardrails since it is the easiest thing to generate quickly and the easiest to mistake for something solid.
3. Insight: what a finding means for us, and why it matters to our goal. It does not say what to do. That call is a decision, made by the people who own it, and it relies on insights.

Level says how far a learning goes, not how far to trust it. Anyone can add at any level, and one nobody has reviewed says so. A hypothesis is what a study sets out to test, not a level.

Escalation path: observations are taken from sources, findings are built on observations, and insights are built on findings. Each is one claim, so each can be checked on its own. A block with nothing under it is shown as resting on nothing.

When an AI makes a block, it states its confidence (low, medium, high), a one line why, and what it assumes. That helps the person checking it, and it never counts as a check.

## Trust model

- Each learning carries: who stated it, whether an AI drafted it and whether its owner confirmed it, what evidence backs it, and each review with who gave it, their role, whether they are an SME, and how they checked.
- Multiple reviewers are allowed and expected. Their reviews stay visible individually, never collapsed. The learning shows one trust state, worked out from them: Not reviewed, Needs changes, Checked by peers, Checked by an SME, or Contested.
- If a new learning conflicts with a checked one, a person can confirm the conflict and both become Contested rather than silently favoring one.
- A person settles a conflict, with a reason: one holds (the other is retired), both hold in their own scope (each gets a new version), not a conflict, or can't tell yet (it becomes an open sub-question). Settling updates the record but never erases the prior state. The history of "this used to be believed, here is why it changed" is part of what makes the source of truth credible over time.
- Nothing is deleted. A block that no longer belongs is retired, with a reason, and can be brought back.
- Sources that live elsewhere are kept as links, and each observation says the spot in its source, so anyone can open it there and check. ANCHOR never opens links itself, which keeps it free of outbound calls: people, or their AI tools, say what they found.

## Architecture shape

Three layers, one core:

1. Core layer: the data store and the logic for add, confirm, review, query, check for conflicts, the digest, and the next step. No UI opinion.
2. MCP server: a thin wrapper exposing the core layer's functions as tools. This is the primary way researchers, PMs, and enterprise AI agents interact with the system, directly inside whatever AI tool they already use (Claude, ChatGPT, an internal agent).
3. Web app: a lightweight client on the same core functions, not a separate data path. It is the workbench: blocks built up from the base, a list of what waits on you, a cabinet on the right with the detail and the check, and a way to break down AI text. It is a full place to work without opening an AI chat.

Roles and SMEs are set up by the team that implements ANCHOR in `anchor.toml` (see [docs/SETUP.md](docs/SETUP.md)), and can also be changed from the web app, with every change logged. The web app and the MCP server always write through the same core functions, so there is never a second, competing version of the truth.

## Scope decision for v1

Keep the schema and actions as small as possible:
- A learning only needs three things to exist: what it says, its level, and its owner. Its stage and origin default to shared and person.
- Everything else (study, evidence, links, reviews) is added over time, not required at creation.
- Reviewing is a single action with one follow-up, not a form.
- Nobody runs ANCHOR yet, so there is no migration code. Old ways are dropped freely.

## Open source and built together

ANCHOR is open source. It is meant to be shared, forked, adapted, and improved by the research teams who use it, and to open a wider conversation about how what a team learns stays trustworthy as AI makes claims faster to produce. See [docs/FLOW.md](docs/FLOW.md) for the roadmap.
