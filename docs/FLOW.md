# How ANCHOR works: the full loop

This page shows how research moves through ANCHOR, who does what, and how a team sets it up. The words are defined in [GLOSSARY.md](GLOSSARY.md). The backlog lives in [GitHub issues](https://github.com/mitchh14/amped-insights/issues), with the live roadmap in [#47](https://github.com/mitchh14/amped-insights/issues/47).

**Current focus.** The app today is the workbench: the Plan, Learn, and Review parts of this loop. A plan breaks the question into sub-questions, blocks are built up from a base of context and checked one by one, and each sub-question shows what other workspaces already know. See [EXPERIENCE.md](EXPERIENCE.md). Plan, Decide, and Loop back below are the wider vision. The core supports them, and the app shows them as coming later.

Two ideas shape everything below:

- **Everyone generates insights.** That is the intended state, not a side effect. Researchers, PwDR, and the AI tools they work with all turn what they see into learnings.
- **Review is open, with varied trust.** Anyone can review. SMEs, the people a team trusts in an area, on any team, carry the most weight. Roles inform, they never block.

See [PRINCIPLES.md](../PRINCIPLES.md) for the why.

## 1. The full loop

Research starts with a question tied to a decision, moves through learnings, connections, and review, and ends with a decision. Decisions and gaps raise new questions, which start the next round.

```mermaid
flowchart LR
    Q(["Question or gap<br/>tied to a decision"])

    subgraph M1["1. Plan"]
        S["Study<br/>question and decision first,<br/>method and sample when running"]
    end

    subgraph M2["2. Learn"]
        O["Observations<br/>what we saw"]
        F["Findings<br/>what we think it means"]
        I["Insights<br/>what it means for us,<br/>not what to do"]
        O -->|supports| F
        F -->|promote| I
    end

    subgraph M3["3. Review"]
        V["Reviews<br/>anyone can,<br/>SMEs weigh most"]
    end

    subgraph M4["4. Decide"]
        U["Decision log<br/>what happened, asked later"]
    end

    Q --> S
    S --> O
    O --> V
    F --> V
    I --> V
    V --> U
    U -->|outcome or new gap| Q
    U -. "nothing checked yet?<br/>ask for research" .-> Q
```

| Mode | Main user | What happens |
|---|---|---|
| Home | Everyone | One next step, what changed for you, and moments when your work mattered |
| Plan | Researcher, PwDR | Start a workspace with its question and decision, then break it into sub-questions; see what is already known |
| Learn | Everyone | Add observations, findings, and insights, alone or with AI; promote one level up |
| Review | Everyone; SMEs weigh most | Confirm your AI drafts, ask for review, approve, ask for changes, or disagree, and revise |
| Decide | Stakeholder | Log a decision and what it relied on; say what happened later |
| Loop back | Everyone | Ask for research from a decision or an empty search |

## 2. Who does what, and where

Every person can work in the app, in their own AI tool over MCP, or both. The AI tool is the everyday companion. The app shows the one next step and is a full place to work. Both write through the same core, so there is one version of the truth.

```mermaid
flowchart TB
    subgraph People["People"]
        R["Researcher"]
        P["PwDR<br/>PMs, analysts, designers, ops"]
        SH["Stakeholder"]
        SME(["SMEs: anyone the team<br/>trusts in an area"])
    end

    subgraph Surfaces["Where they work"]
        AI["Their AI tool<br/>Claude, ChatGPT, Copilot,<br/>internal agents<br/>(MCP tools and guided prompts)"]
        APP["ANCHOR web app<br/>next step, learnings,<br/>review, decisions"]
    end

    CORE[("ANCHOR core<br/>one write path<br/>self hosted, plain storage")]

    R --> AI
    R --> APP
    P --> AI
    P --> APP
    SH --> APP
    SH --> AI
    SME -.-> R
    SME -.-> P

    AI -->|MCP| CORE
    APP -->|same functions| CORE
```

| Step | Researcher | PwDR | Stakeholder | AI tool |
|---|---|---|---|---|
| Plan a study | Leads | Often | Asks for it | Helps draft |
| Add learnings | Yes | Yes | Yes | Drafts, marked as made with AI |
| Confirm an AI draft | Owner does | Owner does | Owner does | Never on its own |
| Review | Yes | Yes | Yes | Never on its own |
| Log a decision | | | Leads | Helps record |
| Ask for new research | Yes | Yes | Leads | Suggests when nothing checked exists |

Anyone can be an SME, whatever their role. Their approvals show as Checked by an SME.

## 3. The life of a learning

A learning keeps its full history. Nothing is erased.

Its **stage** says where it is in its life:

```mermaid
stateDiagram-v2
    [*] --> Draft: made with AI
    [*] --> Shared: written by a person
    Draft --> Shared: the owner confirms it
    Shared --> Replaced: a newer version is written
    Draft --> Retired: a person takes it out of use, with a reason
    Shared --> Retired: a person takes it out of use, with a reason
    Retired --> Shared: brought back
    Replaced --> [*]
```

Retired is how anything is cleared out. It is never a delete: a retired learning keeps its history, leaves the live work, and can be brought back. What was built on it shows that it rests on a retired learning, or moves onto what replaced it.

Its **trust** says how far to lean on it, and is worked out from reviews and conflicts. One state shows at a time. When more than one could apply, the first match wins:

| Trust | When |
|---|---|
| Contested | A person confirmed a conflict with another learning that nobody has settled yet, or a current review disagrees |
| Needs changes | A current review asks for changes |
| Checked by an SME | At least one SME approves |
| Checked by peers | At least one person approves, and no SME yet |
| Not reviewed | Nobody but the owner has checked it |

Anyone can promote an observation to a finding, or a finding to an insight. Promotion adds a new learning linked back to the original, which stays as it was, so the chain from evidence to insight stays readable. A team can set a "ready to promote" rule in `anchor.toml`. When a reviewer asks for changes, the owner revises into a new, linked version, and the reviewer is asked to look again.

Anyone who owns, reviewed, used, or follows a learning hears when it is revised, promoted, newly checked, or contested. A decision that relied on something now contested becomes its maker's next step. The same goes for one that relied on something now retired.

A conflict is settled by a person, with a reason, in one of four ways: one holds (the other is retired), both hold in their own scope (each gets a new version), not a conflict, or can't tell yet (an open sub-question goes into the plan and both stay contested). See [GLOSSARY.md](GLOSSARY.md#conflicts).

## 4. Setting it up: a framework powered by your team

ANCHOR does not come with one fixed process. The team that implements it decides how it fits their way of working. Defaults are open, and each team adds only the structure it wants.

```mermaid
flowchart LR
    subgraph Setup["Day 1: make it yours"]
        direction TB
        A1["Install on your own<br/>machine or server"]
        A2["Name your people<br/>and their roles"]
        A3["Name your SMEs<br/>(on any team)"]
        A4["Name your levels and<br/>study template fields"]
        A5["Connect your AI tools<br/>over MCP"]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    subgraph Week1["Week 1: first loop"]
        direction TB
        B1["Start one real study"]
        B2["Add learnings<br/>in the app or AI tool"]
        B3["Run one review round"]
        B4["A stakeholder logs<br/>one decision"]
        B1 --> B2 --> B3 --> B4
    end

    subgraph Grow["Then: grow and adjust"]
        direction TB
        C1["More teams and studies"]
        C2["Tune roles, SMEs,<br/>and templates"]
        C3["Optional extra structure<br/>(promotion rule, access)"]
        C4["Show impact:<br/>decisions informed"]
        C1 --> C2 --> C3 --> C4
    end

    Setup --> Week1 --> Grow
    Grow -. "learn and adjust" .-> Setup
```

| What the team decides | Where |
|---|---|
| People, roles, and SMEs | `anchor.toml`, or from a person's page in the app |
| Level names, "how I checked" choices, study template and when each field is asked | `anchor.toml` |
| Promotion rule, and whether it is a signal or required | `anchor.toml` |
| Moments, and when to ask what happened after a decision | `anchor.toml` |
| How to install and connect AI tools | [SETUP.md](SETUP.md) |
