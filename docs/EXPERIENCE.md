# The experience: calm, and in order

How the app decides what to show, and when. The goal: open it, see the one thing worth doing, and find everything else one click away. The words are defined in [GLOSSARY.md](GLOSSARY.md).

## The importance model

Every piece of information and every action gets one importance, and the importance decides how it shows.

| Importance | Name | How it shows |
|---|---|---|
| L1 | Do now | One per screen. The single most useful action, or an alert only when something is exceptional (contested, at risk). |
| L2 | Glance | What you judge in two seconds: the statement, a level shape, one chip. Lists show five items, then "See all". |
| L3 | On request | Folded sections with counts, a More menu, nudges that appear when they help. |
| L4 | Record | History and activity. Kept forever, shown only when opened. Never on home. |

## Design rules

1. One primary action per screen, chosen by context.
2. One chip per learning, not three labels.
3. Show state only when it is unusual. Only Contested, Needs changes, and at risk use color.
4. Ask for the least to start.
5. Ask for detail when it is needed, with "draft it with your AI" as a second path.
6. Level is a shape on lists (square: observation, dashed circle: finding, diamond: insight), spelled out on detail.
7. Short lists, then "See all".
8. Activity is a record, not a feed.
9. Celebrate contribution, never rank.
10. A change in what we know is news.
11. Show who made it. AI drafts are confirmed by their owner before review.

## Home

```
+--------------------------------------------------------------+
| Nice. Morgan used your work in "Fund address autofill".   x  |   moment, shown once
+--------------------------------------------------------------+
| Confirm your AI draft                                        |   L1: next step
| "Returning shoppers skip the address step..."                |
| [ Confirm ]  Not now   2 more waiting                        |
+--------------------------------------------------------------+
| Waiting on you (5 max)      | What changed for you (5 max)   |   L2
| Your work (5 max)           | See all activity               |
+--------------------------------------------------------------+
```

The next step is picked by the core (`next_step`), in this order:

1. A decision of yours relies on something now contested
2. Someone asked you to review a learning
3. Your AI drafts to confirm
4. A reviewer asked for changes on your learning
5. A research request is waiting (researchers and SMEs)
6. Something you use or follow changed
7. Your study needs its next detail
8. A decision of yours: what happened?
9. Nothing waiting: a suggestion for your role

"Not now" sets a step aside until something new happens. Stakeholders see "Find what we know", "Your decisions", and "What changed for you".

## A learning

```
[shape] Finding  [Contested]  #5
Shoppers abandon mobile web checkout because the address form is too long
Added by Jordan with AI · confirmed, wording changed · from <study>
+-- Contested. Lee flagged a conflict ----------------------------+   only when present
| This one            |  #7 Address form length does not matter  |
+-----------------------------------------------------------------+
Checked by 2 SMEs. How they checked: read the evidence (2).
[ Primary action ]  [ More v ]
> Why trust this   5
> Connected        6
> Used in decisions 0
> History          8
```

The primary action, by context: your draft, Confirm. Replaced, See the newer version. Yours with changes asked, Revise. Someone else's you have not reviewed, Review. Yours with no review and no request, Ask for review. Checked and ready, Promote. Checked, Use in a decision. Otherwise, Follow changes. Everything else is in More.

## Short flows

- **Add a learning:** what did you learn (one sentence), then what kind is it (three plain choices with an example each), with "An AI helped write this" and "Add evidence or a study" folded. The conflict check shows only when it finds something.
- **Review:** Approve, Ask for changes, or Disagree, then one follow-up that fits: how you checked (optional chips), what should change, or why.
- **Confirm an AI draft:** the draft, editable, and "What did you check or change?".
- **Studies:** start with the question and the decision. Marking it running asks for the method and who you studied. Wrapping it up asks what we learned. Team fields are asked at their stage.
- **Decisions:** what you decided, and which learnings it relied on. "What happened?" is asked later, on the decision and as a next step. The people behind it show as names, with what each did folded.

## Notices and moments

The core's digest (`digest`, and `whats_new` over MCP) picks what changed for each person: changes to what they own, reviewed, used in a decision, or follow, reviews asked of them, and moments. Joins, "working on" notes, and other people's plain activity are left out. Each item is one plain sentence, the same in the app and in an AI tool.

Moments: your work was used in a decision, someone built on it, an SME approved it or your insight became checked, and milestones for you or the whole team. Shown once as a banner, then kept in the digest. Teams turn them off in `anchor.toml`.
