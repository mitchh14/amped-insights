# Project Context: ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

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
6. Data stays where the org already trusts it. No new vendor should have to be trusted with sensitive research data just to get a shared source of truth working.

## Why local-first is the wedge

Research findings are full of the kind of data that makes enterprise procurement slow: interview transcripts, user quotes, survey responses, sometimes PII. Every existing insights SaaS platform asks an org to ship that data into someone else's cloud before anyone can even try the product. That is not just an integration step, it is a legal and security review that can take months and kill a deal before the team ever gets real value from it.

ANCHOR does not have to ask for that. The core layer is a local database. The MCP server and web app are just interfaces on top of it, not a separate data path. An org can run the whole stack on its own machine, its own internal server, or inside its own VPC, and the findings, evidence, and validation history never have to leave infrastructure it already controls.

This is the same bet Obsidian made for personal notes: plain files you own, on your own disk, with tools built on top instead of a database that holds your content hostage. For one person, the pitch is "own your notes." For an enterprise research team, the same shape becomes a way to skip the procurement fight, since the answer to "where does our data live" is "wherever you already run it."

What this means in practice:

- Self-hostable by default, not an enterprise upsell. The open source core should never need a hosted account to be useful.
- No required outbound calls. Query, validation, and conflict-check logic run locally, so a deployment can be fully air-gapped.
- A data format someone else can read. Storage should stay boring and inspectable, not turned into an opaque blob, so an org is never locked into ANCHOR to get its own findings back out.
- Compliance becomes the org's own problem, solved with infrastructure and reviews it already trusts, not a new vendor's problem to convince them to trust.

One tension worth naming: "local-first" for a team is not the same as "local-first" for one person on Obsidian. A single SQLite file works for a single deployment, but real teams need it running somewhere shared, like an internal server, not on one researcher's laptop. The promise is org-controlled infrastructure, not literally local disk, and the architecture should stay honest about that distinction as it scales past a single-server deployment.

This does not replace the trust-layer principles above, it protects them. A shared source of truth that requires handing sensitive research data to a third party is a much harder sell than one that runs entirely inside walls the org already has.

## The two user types

- Researchers: the core users. They hold validation authority and are accountable for the trust layer. Anyone can review a finding, but researchers are the ones most likely to chase down contradictions and follow up on hypotheses tied to real decisions, because they have the most at stake in getting it right.
- People who do research: everyone else contributing findings. PMs, analysts, ops folks, AI agents acting on someone's behalf. They can propose and connect findings but cannot unilaterally promote something to validated status.

## The three tiers of a finding

1. Data point: a fact or observation with no interpretation attached (example: mobile checkout conversion is 42 percent). Can be validated on accuracy alone, since there is no judgment call involved.
2. Hypothesis or observation: someone's read on what a data point or pattern might mean. Not yet safe to act on. This tier needs the most guardrails since it is the easiest thing to generate quickly and the easiest to mistake for something solid.
3. Validated insight: a hypothesis that has been through peer review and promoted. Safe to build recommendations or decisions on.

Escalation path: data point supports a hypothesis, hypothesis gets reviewed and becomes an insight.

## Validation model

- Each finding carries: who stated it, what evidence backs it (linked data points or sources), and a list of who validated it and when.
- Multiple validators are allowed and expected. Their individual validations stay visible, not collapsed into one status.
- A finding can be contested. If a new finding conflicts with an already-validated one, the system flags both as contested rather than silently favoring one.
- Resolution updates the record but never erases the prior state. The history of "this used to be believed, here is why it changed" is part of what makes the source of truth credible over time.

## Architecture shape

Three layers, one core:

1. Core layer: the data store and the logic for propose, validate, query, check for duplicates or conflicts, checkout. No UI opinion.
2. MCP server: a thin wrapper exposing the core layer's functions as tools. This is the primary way researchers, PMs, and enterprise AI agents interact with the system, directly inside whatever AI tool they already use (Claude, ChatGPT, an internal agent).
3. Web app: a lightweight client on the same core functions, not a separate data path. Used for a live status view (what is checked out, what is in the validation queue, what got contested), for manual actions without opening an AI chat, and as the place an org connects its own AI tools or manages permissions.

Permissions and validation authority are managed by the research team inside the web app. The web app and the MCP server always write through the same core functions, so there is never a second, competing version of the truth.

## Scope decision for v1

Keep the schema and actions as small as possible:
- A finding only needs three things to exist: what it says, which tier it is (data point, hypothesis, insight), and its status (proposed, validated, contested).
- Everything else (assignment, full provenance chain, links between findings) is metadata added over time, not required at creation.
- Validation should be a single action, not a form.

## Future direction (not part of this build)

Open source first, as a way to contribute to the community and open industry dialogue about this problem.
