# The problem

This is the single place for the problem ANCHOR exists to solve. [PRINCIPLES.md](../PRINCIPLES.md) and [CONTEXT.md](../CONTEXT.md) point here.

## The problem in one line

Nobody can tell how far to lean on a claim, and AI is making claims faster than people can check them.

## The problem statement

Organizations now produce insights faster than they can check them. A claim from a researcher, a PM, or an AI looks the same on a slide: fluent, confident, and cut off from the question, method, and evidence behind it. What a team has learned sits in decks and chats, not in claims that can be found, checked, or compared. So people redo settled work, contradictions build up unseen, and leaders decide on claims they cannot weigh. The value researchers bring, making answers trustworthy, has no visible home.

## Underlying causes

These are the structural reasons. Fix these and the symptoms ease.

1. **Making a claim got nearly free. Checking one did not.** AI writes a page of analysis in seconds. A person still needs time to read it, test it, and understand it.
2. **Fluent writing hides its assumptions.** How confident the prose sounds says nothing about how strong the basis is.
3. **The unit of knowledge is a document, not a claim.** A deck or a chat thread cannot be checked or linked below the page, so nothing inside it can be reused or challenged on its own.
4. **The basis gets dropped when an insight is lifted out.** The question, the sample, the method, and the decision it served fall away. A 5-person usability note and a stat-sig result end up looking alike.
5. **Different kinds of claim are blurred into one sentence.** What we saw, what it means, what to do, and what was decided all sit in the same line, so no one can say which part they checked.
6. **There is no shared place to look before generating.** People and AI agents start from nothing each time, so they cannot build on what is already known.
7. **Trust comes from role and authority, not visible evidence.** As more people outside research produce work, teams either gatekeep or accept blindly.
8. **Judgment gets lost on the handoff to AI.** When an AI drafts, nobody clearly owns the claim, so nobody stands behind it.
9. **Incentives reward producing, not checking.** Reconciling contradictions and retiring old claims is nobody's job.
10. **The researcher role is shifting, and the new role is not defined.** Value used to come from running every study. It now comes from holding the trust layer, and few places make that visible.
11. **Speed is rewarded and the cost of skipping checks shows up late.** A weak claim moves fast, gets built on, and is expensive to unwind. The time saved at the start is paid back, with interest, at the end.

## Symptoms

What each group sees day to day.

### Insights leadership

- Cannot tell which claims are safe to decide on.
- Different teams give conflicting answers to the same question.
- Pays twice for questions that were already answered.
- More AI output, but not more clarity.
- No record of why a call was made or what it relied on.
- Hard to show what research is worth.

### Researchers and analysts

- Review AI and PM work after the fact, as a gate that gets skipped or as a bottleneck.
- Rigor is invisible, because strong and weak evidence look the same.
- Caveats fall off as findings travel.
- Old insights outlive the moment they were true.
- Unclear what their role becomes.

### People using AI to generate insights, findings, and data

- Confident output they cannot ground.
- Cannot see what the AI assumed.
- Do not know if the question was already asked or answered.
- Unsure what to check, so checking feels like busywork or blame.
- Get challenged late, after the claim has already spread.

### AI agents

- No checked knowledge to query, so they invent context or start over each time.
- No way to say how sure they are in a form a person can act on.

## What this means for the design

| Cause | What ANCHOR does about it |
|---|---|
| Claims are cheap, checks are not | Break long text into one-claim blocks so each check is small |
| Fluent text hides assumptions | AI blocks say confidence, why, and what they assume |
| Document is the wrong unit | The block is the unit. Each can be checked and built on |
| Basis gets dropped | Every block shows what it is built on, and the workspace keeps the question and plan |
| Kinds of claim are blurred | Observation, finding, and insight are separate. Actions go in a decision |
| No shared place to look | Already known shows checked blocks from other workspaces |
| Authority stands in for evidence | Check states show who checked what and how. Roles inform, they never block |
| Judgment lost on handoff | AI drafts have a named owner and stay unchecked until the owner checks them |
| Producing is rewarded | Disagreement is surfaced and kept, and what waits on you is shown |
| Researcher role unclear | Researchers hold and grow the trust layer |
| Speed hides cost | Build fast, but show what is still unchecked under what you build. See "Slow and steady" in the principles |
