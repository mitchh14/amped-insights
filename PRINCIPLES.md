# Principles

This is the why behind Amped Insights (ANCHOR): what we believe, and why the framework is built the way it is. See [CONTEXT.md](CONTEXT.md) for how it's built.

ANCHOR is an open source framework. It is meant to be used, adapted, and improved together by the people and teams who run it.

## We govern insights, not people

ANCHOR checks claims, not the people who make them. What gets looked at is an insight and every part that makes it up: the observations under it, the sources those came from, the method, and what was assumed along the way. Nobody is ranked, and nobody is blocked because of who they are.

This matters most for work made with AI. An AI can write a long, confident answer in seconds. The words read well, and the assumptions inside them are easy to miss. So ANCHOR takes that work apart into small building blocks, one claim each, and asks a person to check each block before anything is built on it. A claim with nothing under it shows up as resting on nothing. When an AI makes a block, it also says how confident it is, why, and what it took as given. That is useful for a checker, and it never counts as a check.

## The problem we're actually solving

The full statement, with causes and symptoms for leadership, researchers, and people using AI, is in [docs/PROBLEM.md](docs/PROBLEM.md). The short version:

As AI makes it fast for anyone to generate an analysis or a claim, the risk isn't slow research, it's ungrounded research. What teams learn lives in decks, docs, and chat threads with no shared, checkable place for what the org actually knows. People re-research settled questions, contradictions pile up quietly, and nobody can tell what's proven, what's a guess, or what's already been checked.

This isn't new. Non-specialists picking up specialist work, PMs doing research, analysts doing strategy, has always happened. AI didn't start that drift, it just made it a lot more feasible and a lot more common, because it hands anyone the confidence to operate outside their own domain. We're not exempt from this either: this whole project is a research-minded person building software with AI's help.

That drift isn't something to fight. It's an opening. Research's highest-value move right now isn't guarding who's allowed to produce insights, it's becoming the thing that makes everyone's insights trustworthy. That's not a defensive posture, it's an evolution, and it needs to happen fast, because the value research brings to the organization it serves has to be proven, not assumed.

## Slow and steady

Speed is good. But a claim that moves fast and rests on parts nobody looked at is not fast, it is a delay you have not paid for yet. It gets built on, shared, and decided on, and then someone has to take it apart.

Taking the time to check each part and understand how it fits the whole is what gets you to the right outcome. Slow can be fast. It is faster to check a small block now than to unwind a decision later.

This is why ANCHOR works in small blocks, one claim each, checked one at a time. It is why you can build on something unchecked but see a flag on everything above it. And it is why an AI draft waits for its owner before others lean on it. The point is not to slow people down. It is to put the care where it saves the most time: early, in small pieces, before anything big rests on them.

## Own your infrastructure, own your context

Research data, like interview transcripts, user quotes, and survey responses, is sensitive. It should stay where the team already trusts it. The core is a local database. The MCP server and the web app are interfaces on top of it, not a separate path the data has to travel through. A team can run the whole thing on its own machine, its own server, or inside its own infrastructure.

Storage stays plain and inspectable, the same idea behind tools like Obsidian: files you own, with tools built on top. Your learnings, evidence, and review history belong to you and should keep working no matter what happens to this project or any tool around it.

## An insight is a chain, not a sentence

An insight usually gets treated as the deliverable. Really, it's the last visible link in a chain: why we looked into something, how we planned to answer it, what business decision it was in service of, and only then, what we found.

Strip away the objective and the plan, and what's left is a claim nobody can check the limits of. A usability observation from five people and a stat-sig result from a thousand respondents are not the same kind of claim, and a system that lets them look the same is doing real damage, not just being imprecise. Documenting the objective and business context behind a piece of work isn't overhead, it's part of the insight itself, and it's what lets someone six months from now know whether it still applies to the question they're actually asking.

## Insight work happens in public

Collaborative insight generation matters more than who gets credit for it. Anyone can have an insight or look at data, and the work of getting to the right answer, questioning the framing, building on someone else's read, catching a bad generalization, should happen while the work is still in progress, not in a review pass after it's already written up.

That includes working with AI. The collaboration between a person and an AI agent shouldn't happen behind closed doors either. It should be visible enough that the rest of the team can see it, question it, and add to it, the same way they would with a colleague's work.

The risk isn't that people can't be trusted. It's that judgment gets lost when a person hands the work to an AI. So anything an AI drafts is marked as a draft, and stays one until the person who owns it has checked it. Only then is it open for others to check.

## Everyone generates insights, and every part gets checked

Everyone generating insights is the goal, not a side effect. Researchers, people who do research, and AI agents working for them should all be able to turn what they see into insights.

Checking is open in the same way. Anyone can check a block, and people who do research will often check each other's work. What the system tracks is how well each block has been checked: by its owner, by peers, or by an SME, the people the team trusts in an area, on any team, including research. A block shows that plainly, and so does anything built on a block that still needs a check. The system never blocks someone because of who they are. It shows who checked what, and how, so anyone reading can judge how far to lean on the insight.

## Fit the team, not the other way around

Teams run research differently. They trust different roles to different degrees, and they have their own habits and steps. ANCHOR should bend to that through setup instead of forcing one process on everyone. The defaults are open, and the people who implement it decide how much structure to add. It is a framework powered by the people running it.

## What this pivot is, and isn't

The point of this project is a change in what research does for an organization: from being the only people allowed to produce insights, to being the people who hold and grow a shared, trustworthy layer that anyone, including AI agents, can build on. That is the whole purpose.

If that also makes it easier for people outside research to do good analysis, that's a welcome side effect. It's not the goal, and it's not why this exists. The goal is research proving its value to the organizations it serves, quickly and clearly, by becoming the thing that makes everyone's work trustworthy instead of the thing that gatekeeps who's allowed to have an opinion.
