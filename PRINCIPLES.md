# Principles

This is the why behind Amped Insights (ANCHOR): what we believe, and why the product is built the way it is. See [CONTEXT.md](CONTEXT.md) for how it's built.

## The problem we're actually solving

As AI makes it fast for anyone to generate an analysis or a claim, the risk isn't slow research, it's ungrounded research. Findings live in decks, docs, and chat threads with no shared, checkable place for what the org actually knows. People re-research settled questions, contradictions pile up quietly, and nobody can tell what's proven, what's a guess, or what's already been checked.

This isn't new. Non-specialists picking up specialist work, PMs doing research, analysts doing strategy, has always happened. AI didn't start that drift, it just made it a lot more feasible and a lot more common, because it hands anyone the confidence to operate outside their own domain. We're not exempt from this either: this whole project is a research-minded person building software with AI's help.

That drift isn't something to fight. It's an opening. Research's highest-value move right now isn't guarding who's allowed to produce findings, it's becoming the thing that makes everyone's findings trustworthy. That's not a defensive posture, it's an evolution, and it needs to happen fast, because the value research brings to the people who pay for it has to be proven, not assumed.

## Own your infrastructure, own your context

Enterprise research data, interview transcripts, user quotes, survey responses, is full of the kind of information that makes a security or legal review take months. Every existing insights platform asks an org to ship that data into someone else's cloud before anyone gets real value from it.

We don't ask for that. The core is a local database. The MCP server and the web app are interfaces on top of it, not a separate path the data has to travel through. An org can run the whole thing on its own server or inside its own infrastructure, and nothing has to leave walls it already trusts.

This is the same bet Obsidian made for personal notes: plain files you own, tools built on top, instead of a database that holds your content hostage. Lock-in through fear, you have three years of work in here, leaving means starting over, is a business model, not a value proposition. We would rather earn renewal every year by being useful than by being hard to leave. If we disappeared tomorrow, your findings, evidence, and validation history should still work.

## An insight is a chain, not a sentence

A finding usually gets treated as the deliverable. Really, it's the last visible link in a chain: why we looked into something, how we planned to answer it, what business decision it was in service of, and only then, what we found.

Strip away the objective and the plan, and what's left is a claim nobody can check the limits of. A usability observation from five people and a stat-sig result from a thousand respondents are not the same kind of claim, and a system that lets them look the same is doing real damage, not just being imprecise. Documenting the objective and business context behind a piece of work isn't overhead, it's part of the finding itself, and it's what lets someone six months from now know whether it still applies to the question they're actually asking.

## Insight work happens in public

Collaborative insight generation matters more than who gets credit for it. Anyone can have an insight or look at data, and the work of getting to the right answer, questioning the framing, building on someone else's read, catching a bad generalization, should happen while the work is still in progress, not in a review pass after it's already written up.

That includes working with AI. The collaboration between a person and an AI agent shouldn't happen behind closed doors either. It should be visible enough that the rest of the team can see it, question it, and add to it, the same way they would with a colleague's work.

## Everyone generates insights, and trust varies

Everyone generating insights is the goal, not a side effect. Researchers, people who do research, and AI agents working for them should all be able to turn what they see into insights.

Validation is open in the same way. Anyone can validate, and people who do research will often check each other's work. But not every validation carries the same weight. The most trusted ones come from researchers and from trusted reviewers: people, inside or outside the research team, that the team has chosen to give that standing. The system never blocks someone because of their role. It shows who validated what, and in what role, so anyone reading can judge how much to lean on it.

## Fit the team, not the other way around

Teams run research differently. They trust different roles to different degrees, and they have their own habits and steps. ANCHOR should bend to that through setup instead of forcing one process on everyone. The defaults are open, and the people who implement it decide how much structure to add. It is a framework powered by the people running it.

## What this pivot is, and isn't

The point of this project is a change in what research does for an organization: from being the only people allowed to produce findings, to being the people who hold and grow a shared, trustworthy layer that anyone, including AI agents, can build on. That is the whole purpose.

If that also makes it easier for people outside research to do good analysis, that's a welcome side effect. It's not the goal, and it's not why this exists. The goal is research proving its value to the organizations that fund it, quickly and clearly, by becoming the thing that makes everyone's work trustworthy instead of the thing that gatekeeps who's allowed to have an opinion.
