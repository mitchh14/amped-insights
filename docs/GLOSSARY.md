# Glossary

The words ANCHOR uses, and what each one means. This page is the single source. The app, the MCP tools, the docs, and the issues all use these words and no others.

The rule: each thing gets one word, and each word means one thing. A learning is described along five separate dimensions, and each dimension has exactly one value at a time.

## The thing we capture

**Learning**: anything the team writes down that it learned. Every learning has a level, an origin, a stage, and a trust state.

### Level: how far the learning goes

| Level | Means | Example |
|---|---|---|
| **Observation** | What we saw or measured. No reading into it. | "7 of 12 people left the address form before finishing." |
| **Finding** | A pattern or reading across observations. Not yet an insight. | "People drop off when they have to type a full address." |
| **Insight** | What a finding means for us, and what to do about it. | "Address autofill is likely our biggest checkout win." |

Two questions tell the levels apart. Does it read into what we saw? If not, it is an observation. Does it say why it matters to us? If so, it is an insight. Anything in between is a finding.

"Level" only ever means this. How loudly the app shows something is its **importance** (do now, glance, on request, record), never its level.

Anyone can add a learning at any level. Level says how far a learning goes, not how far to trust it. An insight nobody has reviewed shows **Not reviewed** next to it. See Trust.

**Hypothesis** is not a level. It is what a study sets out to test, before any research happens.

### Origin: who made it

| Origin | Means |
|---|---|
| **Person** | A person wrote it without AI. |
| **Person with AI** | A person worked with an AI tool to write it. |
| **AI agent** | An AI agent wrote it. A named person owns it. |

### Stage: where it is in its life

| Stage | Means |
|---|---|
| **Draft** | Made with AI, and the owner has not confirmed it yet. Visible to everyone. Cannot be sent for review. |
| **Shared** | Its owner stands behind it. Open for review. |
| **Replaced** | A newer version, or a resolved conflict, took its place. Kept in the record. |

A learning a person writes on their own starts as Shared.

### Trust: how far to lean on it

| Trust | Means |
|---|---|
| **Not reviewed** | Nobody but the owner has checked it. |
| **Needs changes** | A reviewer asked for changes. |
| **Checked by peers** | Approved, and no SME has approved it yet. |
| **Checked by an SME** | Approved by at least one SME. |
| **Contested** | Another learning conflicts with it, or a reviewer disagrees. |

One learning shows one trust state. When more than one could apply, the first match wins: Contested, then Needs changes, then Checked by an SME, then Checked by peers, then Not reviewed.

### Use

**Used in a decision**: a count, not a state. "Used in 2 decisions."

## What we do

| Action | Who | Means |
|---|---|---|
| **Add** | anyone | Write down a learning. |
| **Confirm** | owner | "I checked this AI draft and I stand behind it." Moves Draft to Shared. |
| **Ask for review** | anyone | Ask a person or a role to check a learning. |
| **Review** | anyone but the owner | Give one verdict, plus how you checked. |
| **Revise** | owner | Write a new version. The old one becomes Replaced. |
| **Promote** | anyone | Take a learning up a level, as a new linked learning. |
| **Link** | anyone | Say how two learnings relate. |
| **Use in a decision** | anyone | Record that a decision relied on a learning. |
| **Ask for research** | anyone | Start a study request. |
| **I'm working on this** | anyone | A soft hold so people do not duplicate work. |

**Review verdicts:** **Approve**, **Ask for changes**, **Disagree**.

**How I checked:** **Read the evidence**, **Checked the source data**, **Reran it**, **Expert judgment**. Teams can change these.

**Links:** **Supports**, **Builds on**, **Same as**, **Conflicts with**.

## Where the work comes from

| Word | Means |
|---|---|
| **Study** | A piece of research: the question, the decision it serves, the method, and who took part. |
| **Hypothesis** | What a study expects to find. Optional. |
| **Research request** | A study someone asked for that nobody has picked up yet. |
| **Decision** | A call someone made, and the learnings it relied on. |

**Study stages:** **Requested**, **Planned**, **Running**, **Finished** (we learned something), **Dropped** (we did not need to run it).

## Showing the work

| Word | Means |
|---|---|
| **Evidence** | The learnings a learning builds on, linked with Supports. |
| **Source** | Where an observation came from: a link, a file, a quote, or a query. |
| **Query** | The exact query that pulled the data, and the system it ran on, so anyone can rerun it. |
| **Prompt** | The prompt given to the AI tool that drafted a learning. |

## People

| Role | Means |
|---|---|
| **Researcher** | Does research as their main job. |
| **PwDR** | People who do research: PMs, designers, analysts, and others doing research as part of their job. |
| **Stakeholder** | Uses learnings to make decisions. |

**SME** (subject matter expert): a person the team trusts to review in their area. Anyone can be an SME, whatever their role. An SME's approval shows as Checked by an SME. Everyone else's shows as Checked by peers.

**AI agent** is not a role. It is an origin, and it always has a named owner.

## Words we do not use

| Instead of | Say |
|---|---|
| finding (as the umbrella), claim | learning |
| tier, kind | level |
| data point | observation |
| hypothesis (as a level) | finding |
| propose | add |
| validate, verify, validation | review, checked |
| validated | Checked by peers, Checked by an SME |
| proposed | Not reviewed |
| superseded | Replaced |
| trusted reviewer, trusted role | SME |
| contributor, people who do research | PwDR |
| extends, duplicates, contradicts | Builds on, Same as, Conflicts with |
| check out | I'm working on this |
| done, closed (studies) | Finished, Dropped |
