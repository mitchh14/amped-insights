# Project Context: ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

See [PRINCIPLES.md](PRINCIPLES.md) for why this exists and the values behind it. This doc covers the build: schema, actions, architecture.

## The problem

As AI makes it fast for anyone to generate an analysis or a claim about users, the risk is not slow research. It is ungrounded research. Findings live in decks, docs, and chat threads with no shared place to check what the organization already knows. People re-research questions that already have answers, contradictions pile up quietly, and nobody can tell what is still true, what was a one-time guess, or what has been checked at all.

The fix is not a better search tool. It is a shared, checkable layer of findings, at different levels of confidence, that any person or AI agent can query before generating something new, and that stays honest about who said what and how sure anyone should be.

## Why now

Researcher roles are shifting from executing every study personally to orchestrating and curating a shared body of knowledge that AI agents and other contributors can draw from and add to. This framework is built for that shift. Researchers become the people who hold and grow the trust layer, not the only people allowed to produce findings.

## Core principles

1. Transparency over authority. The system does not grant credibility by role. It makes the basis for credibility visible: who stated something, what evidence backs it, who reviewed it. Trust is earned by the work, not handed out by a badge.
2. Not all findings are equal, and the system should never pretend they are. A raw data point, an unproven hypothesis, and a validated insight are different things and should look different.
3. More than one person can validate a finding. Validations are shown individually, not merged into a single verdict, so agreement and disagreement are both visible.
4. Contradictions get surfaced, not hidden or silently overwritten. When a new finding conflicts with a validated one, both stay visible and the conflict triggers a re-evaluation, with the history of what changed and why kept intact.
5. Framework over system. This should be a small set of primitives (propose, validate, query, check for duplicates or conflicts) that orgs can run themselves, not a heavy platform people have to migrate into.
6. Data stays where the org already trusts it, self-hosted by default, no required outbound calls, storage that stays boring and inspectable so nobody is locked in. See PRINCIPLES.md for the full reasoning.
7. Everyone generates insights, by design. Validation is open to everyone, with varied trust: the most trusted validations come from researchers and trusted reviewers the team names. Roles inform, they never block.
8. Fit the team, not the other way around. Teams trust different roles differently and work in their own ways. Setup bends ANCHOR to the team. Defaults are open, and the people implementing it decide how much structure to add.

## The user types

Everyone generates insights. That is the intended state. Anyone can also validate, but trust varies by who is validating, and the system shows that instead of blocking anyone.

- Researchers: the core users. They are accountable for the trust layer, and their validations carry the most weight. They are the ones most likely to chase down contradictions and follow up on hypotheses tied to real decisions, because they have the most at stake in getting it right.
- Trusted reviewers: people the team chooses to give validation standing, inside or outside the research team (for example a data science lead or a domain expert). Their validations are weighted like a researcher's.
- People who do research: everyone else contributing findings. PMs, analysts, designers, ops folks, and AI agents acting on someone's behalf. They propose, connect, and generate insights, and they can validate each other's work. Their validations are shown as peer validations.
- Stakeholders: the people who use insights to make decisions. They find trusted insights, record when they used one, and raise new questions that start the next round of research.

See [docs/FLOW.md](docs/FLOW.md) for how these people move through the work modes.

## The three tiers of a finding

1. Data point: a fact or observation with no interpretation attached (example: mobile checkout conversion is 42 percent). Can be validated on accuracy alone, since there is no judgment call involved.
2. Hypothesis or observation: someone's read on what a data point or pattern might mean. Not yet safe to act on. This tier needs the most guardrails since it is the easiest thing to generate quickly and the easiest to mistake for something solid.
3. Validated insight: a hypothesis that has been through peer review and promoted. Safe to build recommendations or decisions on.

Escalation path: data point supports a hypothesis, hypothesis gets reviewed and becomes an insight.

## Validation model

- Each finding carries: who stated it, what evidence backs it (linked data points or sources), and a list of who validated it and when.
- Multiple validators are allowed and expected. Their individual validations stay visible, not collapsed into one status. Each one shows the validator's role, so a researcher or trusted reviewer validation reads differently from a peer one.
- A finding can be contested. If a new finding conflicts with an already-validated one, the system flags both as contested rather than silently favoring one.
- Resolution updates the record but never erases the prior state. The history of "this used to be believed, here is why it changed" is part of what makes the source of truth credible over time.

## Architecture shape

Three layers, one core:

1. Core layer: the data store and the logic for propose, validate, query, check for duplicates or conflicts, checkout. No UI opinion.
2. MCP server: a thin wrapper exposing the core layer's functions as tools. This is the primary way researchers, PMs, and enterprise AI agents interact with the system, directly inside whatever AI tool they already use (Claude, ChatGPT, an internal agent).
3. Web app: a lightweight client on the same core functions, not a separate data path. Used for a live status view (what is checked out, what is in the validation queue, what got contested), for manual actions without opening an AI chat, and as the place an org connects its own AI tools or manages permissions.

Roles and trusted reviewers are set up by the team that implements ANCHOR (a config file first, the web app later). The web app and the MCP server always write through the same core functions, so there is never a second, competing version of the truth.

## Scope decision for v1

Keep the schema and actions as small as possible:
- A finding only needs three things to exist: what it says, which tier it is (data point, hypothesis, insight), and its status (proposed, validated, contested).
- Everything else (assignment, full provenance chain, links between findings) is metadata added over time, not required at creation.
- Validation should be a single action, not a form.

## Future direction (not part of this build)

Open source first, as a way to contribute to the community and open industry dialogue about this problem.
