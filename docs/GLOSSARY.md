# Glossary

The words ANCHOR uses, and what each one means. This page is the single source. The app, the MCP tools, the docs, and the issues all use these words and no others.

The rule: each thing gets one word, and each word means one thing.

## Where the work happens

| Word | Means |
|---|---|
| **Workspace** | One piece of analysis: the question, the decision it serves, its base, and its blocks. |
| **Base** | What every block rests on. It has four parts: the plan, context, method and approach, and notes. |
| **Plan** | The question, the decision it serves, and a few sub-questions. |
| **Sub-question** | Something we need to know to make the decision. It can say what we expect to find. A finding or insight says which sub-question it **answers**. |
| **Already known** | Checked blocks from other workspaces that speak to a sub-question. |
| **Source** | One piece of context in a workspace: a note, a quote, data, a query, a link, file text, or pasted AI text. |
| **Package** | The insights a workspace shares together, in order. |

## The thing we check

**Block**: one thing we learned, one claim. It is the unit you check and build with. Every block has a level, an origin, and one check state.

### Level: how far the block goes

| Level | Means | Example |
|---|---|---|
| **Observation** | What we saw or measured. No reading into it. It comes from a source. | "7 of 12 people left the address form before finishing." |
| **Finding** | What a set of observations means. Built on observations. | "People drop off when they have to type a full address." |
| **Insight** | What a finding means for us, and what to do. Built on findings. | "Address autofill is likely our biggest checkout win." |

Two questions tell the levels apart. Does it read into what we saw? If not, it is an observation. Does it say why it matters to us? If so, it is an insight. Anything in between is a finding.

Level says how far a block goes, not how far to trust it.

### How far a sub-question has got

| State | Means |
|---|---|
| **Open** | Nothing answers it yet. |
| **In progress** | Findings or insights answer it, but no insight that answers it is checked by someone other than its owner. |
| **Answered** | An insight that answers it is Checked by peers or Checked by an SME. |

### Built on

| Word | Means |
|---|---|
| **Built on** | What is under a block. An observation is built on sources. A finding or insight is built on other blocks. |
| **Rests on nothing** | A block with nothing under it: an observation with no source, or a finding or insight built on no blocks. Shown so it gets looked at. |
| **Built on unchecked** | Shown with ⚠ on a block when something directly under it still needs a check, needs changes, or has a disagreement. You can still build on it. The flag stays until those parts are checked. |

### Origin: who made it

| Origin | Means |
|---|---|
| **Person** | A person wrote it without AI. |
| **Person with AI** | A person worked with an AI tool to write it. |
| **AI agent** | An AI made it. A named person owns it. |

### What the AI says

Every block an AI makes carries what the AI said about it. It is shown apart from the check state and never counts as a check.

| Word | Means |
|---|---|
| **AI confidence** | How sure the AI says it is: **Low**, **Medium**, or **High**. |
| **Why** | The AI's one line reason. |
| **Assumes** | What the block takes as given without showing it. |

### Check state: how far to lean on it

One block shows one check state. The first that applies wins.

| Check state | Means |
|---|---|
| **Disagreement** | Someone disagrees, or it conflicts with another block. |
| **Needs changes** | Someone asked for changes. |
| **Needs a check** | Made with AI, and its owner has not checked it yet. |
| **Checked by an SME** | An SME said it looks right. |
| **Checked by peers** | Someone other than the owner said it looks right. |
| **Checked by owner** | Its owner stands behind it, and nobody else has checked it yet. |

In the app, how full a block looks says how far it has been checked: hollow, then light, then mid, then solid. Only the first three states get words and color.

## What we do

| Action | Who | Means |
|---|---|---|
| **Add** | anyone | Write down a block. |
| **Check** | anyone | Say **Looks right**, **Needs changes**, or **Disagree**, plus how you checked. The owner of an AI draft checks it first, and may fix the wording. When changes are asked for, the owner answers by changing the wording, which saves a new version. |
| **Connect** | anyone | Pick blocks and build the next level from them. |
| **Break down** | anyone | Take a long piece of AI text apart into blocks, one claim each. |
| **Add to package** | anyone | Put an insight in the workspace's package. |
| **Plan** | anyone | Add, change, or remove the sub-questions, and say which one a finding or insight answers. |

**How I checked:** **Read the evidence**, **Checked the source data**, **Reran it**, **Expert judgment**. Teams can change these.

## People

| Role | Means |
|---|---|
| **Researcher** | Does research as their main job. |
| **PwDR** | People who do research: PMs, designers, analysts, and others doing research as part of their job. |
| **Stakeholder** | Uses insights to make decisions. |

**SME** (subject matter expert): a person the team trusts to check work in their area. Anyone can be an SME, whatever their role.

**AI agent** is not a role. It is an origin, and it always has a named owner.

## Coming later

**Decisions** (a call someone made, and the insights it relied on), **Narratives** (a package turned into a story you can follow back to the parts), and **Requests** (asking for research when nothing checked exists). The core already has decisions and requests; the app shows them as later.

## In the code

The code keeps some older names. This is how they map.

| In the app and docs | In the code |
|---|---|
| Workspace | study (`start_study`, `get_workspace`) |
| Sub-question | question (`add_question`, `question_id`) |
| Block | learning |
| Built on (blocks) | evidence |
| Check, by the owner of a draft | confirm |
| Check, by anyone else | review (verdicts approve, changes, disagree) |
| New version | revise, and the old one is Replaced |
| Disagreement | contested |

## Words we do not use

| Instead of | Say |
|---|---|
| claim, finding (as the umbrella), learning (in the app) | block |
| data point | observation |
| study (in the app) | workspace |
| validate, verify, review (in the app) | check |
| validated | Checked by peers, Checked by an SME |
| draft (as a state) | Needs a check |
| contested | Disagreement |
| evidence (in the app) | built on |
| unsupported | rests on nothing |
| trusted reviewer | SME |
