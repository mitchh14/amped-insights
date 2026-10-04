# The experience: the workbench

How the app shows the work, and why. The goal: open a workspace, see how the insights are built and what still needs a check, and check it in a few clicks, even when the workspace holds hundreds of blocks. The words are defined in [GLOSSARY.md](GLOSSARY.md).

## Design rules

1. One idea per element. A block shows its statement. How full it looks says how far it has been checked.
2. Only trouble gets words and color: Needs changes, Disagreement, Unsupported, ⚡ for a conflict, and ⚠ for something unchecked underneath. A block that needs a check is dashed, with no words.
3. Show what is under everything. Each block connects to what it is based on, down to the sources, and to what it supports, up to the decision.
4. What the AI says (confidence, why, assumes) sits apart from the check, and never counts as one.
5. Ask for the least first. Pick a verdict, then say how you checked or why.
6. Never get lost. The details panel always says where you are, and the detail lives there, not in a new page.
7. Say the plain thing. Buttons say what they do: Check, Resolve, Retire, Delete for good.

It works on a phone and on a desktop. On a desktop the details panel sits on the right. On a phone it is a sheet at the bottom that you pull up (peek, open, full).

## Home

A card per workspace: its question, the decision it serves, a strip of small squares (one per block, filled by how far it is checked), how many blocks wait on you, and how far the plan has got ("1 of 4 answered"). **New workspace** asks for the question and the decision it will inform, then opens the plan.

## Map or Flow

A workspace opens in one of two views. The switch sits at the top and the app remembers your pick. Both show the same blocks and use the same details panel, so you can switch at any time, even in the middle of a Focus session.

```
 ANCHOR [Map|Flow]  Why do mobile shoppers leave checkout...?        You are [Sam]
 [Everything][Waiting on you 1][Trouble 2][Conflicts 1][Retired 1]  [Check 1 block] [Connect blocks] [Break down AI text]
+------------------------------------------------------------+-----------------------------+
|  Map: one area per sub-question, zoom to read              | Workspace › Finding #10     |
|  Flow: Sources | Observations | Findings | Insights | Decision                            |
+------------------------------------------------------------+-----------------------------+
```

### Map

The whole workspace as one picture you zoom into.

- Each sub-question in the plan gets its own area. Blocks that answer nothing sit in "Not tied to a sub-question". The decision sits on top.
- Inside an area, blocks stack by level: insights at the top, then findings, observations, and sources at the bottom.
- Zoomed out, each area shows as a card: the sub-question, a bar of how far its blocks are checked, how many wait on you, and how many are in a conflict. Tap a card to zoom into it.
- Zoomed in, blocks show their words. Pinch, drag, scroll, or use + and −. The ⤢ button fits everything.
- Tap a block to open it. Its whole line lights up: everything under it, down to the sources, and everything it supports. The rest fades.
- A conflict is a red zigzag between two blocks, with a ⚡ badge on each.
- The blocks you opened leave a trail line, so you can see the path you took.

### Flow

The same work as columns, left to right: **Sources**, **Observations**, **Findings**, **Insights**, **Decision**.

- Pick a block, and every column pulls the blocks linked to it to the top under "Linked to #10". The rest fold under "Not linked".
- With nothing picked, each column groups its blocks by sub-question.
- The path bar above the columns shows what is picked at each level. Tap a step to jump to that column. On a phone the columns swipe.
- **Find a block** searches every column.
- On a desktop, lines join the linked blocks across columns.

### Show

The chips under the bar narrow what you see in either view: **Everything**, **Waiting on you**, **Trouble** (changes asked, a disagreement, unsupported, based on a retired block, or a link source with no spot), **Conflicts**, and **Retired** (hidden unless you turn it on).

## The details panel

- **The trail** at the top says where you are: `Workspace › Insight #13 › Finding #10`. Picking something in the work starts a new trail. Following a link inside the panel adds a step. Tap any step to go back. **Wider** makes room to think. **×** goes back to the workspace.
- **Nothing picked**: the workspace.
  - **To do**: what needs you, as cards. Resolve conflicts, Waiting on you, Check the evidence for an insight, and Tidy up. Each starts a Focus session.
  - The plan, with each sub-question's state (Open, In progress, Answered).
  - The package. The base, folded. How to work with your AI tool, folded.
- **A block**:
  1. The statement, its check state, and who made it.
  2. Any conflict it is in, with **Resolve it**, and any block it might conflict with, with **Mark as a conflict**.
  3. **From** (an observation's sources) or **Based on** (the blocks under it, each with its state). A link source shows **Open ↗** and the **spot**: where in the source this comes from ("S7 at 18:02", "Row 4", "page 12"). If the spot is missing, it says so and lets you add it.
  4. **AI says**, for blocks made with AI: confidence, why, and what it assumes. "This is the AI's own view. It never counts as a check."
  5. **Check**:
     - The owner of an AI draft reads it, fixes the wording if needed, and says **Looks right**.
     - When someone asked for changes or disagrees, the owner can **change the wording** (a new version), **add what it is based on**, **keep as is** (with a reason, and an SME is asked to look), or **retire it**.
     - Anyone else picks **Looks right**, **Needs changes**, or **Disagree**, then says how they checked or why.
  6. **Answers**: pick the sub-question it answers. It is not a check.
  7. Folded: **Things to consider** (questions for this level, and private notes kept in your browser), **Supports**, **History**, **Ask your AI about it**, and **Clean up** (Retire, It conflicts with, and Delete for good for the person who made it).
- **A source**: its link with **Open the source ↗**, **Change the link**, the observations that cite it with their spots, **Add an observation from it** (with its spot), and **Delete source**.

## Focus

Tap a card in **To do**, or **Check N blocks**, to start a Focus session. A bar at the top replaces the toolbar: what you are working through, "2 of 5", ← and → to walk the chain, the Map or Flow switch, and **←** to leave (or Esc). Everything that is not part of the session fades.

- **Waiting on you** goes from the bottom up, so what you check first supports what comes next.
- **Check the evidence for** walks everything under one insight that still needs a check.
- **Resolve conflicts** opens each conflict in turn.
- After each check or resolve, the next item opens. **Skip** moves on without doing anything.
- At the end a short summary says how many you worked through.

## Conflicts

Anyone can mark two blocks as a conflict: they can't both be true. Both show Disagreement until someone resolves it. The conflict panel shows both side by side (A vs B) with what each is based on and what it supports, then asks **How should it end?**

- **Pick one**: keep one. The other is retired, and the blocks based on it can move onto the one you keep.
- **Keep both, narrow each**: rewrite each so it says when it is true. Each gets a new version.
- **Not a conflict**: they fit together.
- **Not sure yet**: add an open question to the plan. Both stay marked until someone resolves it.

Every outcome needs a short **why**. The owners and everyone who checked either block hear about it.

## Retire and delete

- **Retire** (anyone): takes a block out of the live work with a reason (Out of date, Out of scope, Wrong, Replaced by another block, Duplicate of another block). It keeps its history and can be brought back. Blocks based on it show "Based on a retired block", and can move onto the replacement. Retired blocks leave the counts, the plan, and the package.
- **Delete for good** (only the person who made it): removes the block, its earlier versions, and its checks. It asks first. Blocks based on it lose it.
- **Tidy up** finds duplicates, loose ends (AI drafts nobody checked and nothing is based on), and blocks based on retired ones, and retires the ones you pick in one go.

## Connect blocks

Tap **Connect blocks**, then pick blocks in either view. Write the finding or insight they add up to, or copy a prompt for your AI tool. Starting from a sub-question in the plan picks it for you.

## Break down AI text

It opens in the work area. Paste a long AI answer and **Break it down**. The built-in splitter shows the pieces first, one per sentence, with a guessed level, and writes nothing yet. A summary counts how many are unsupported, how many take things as given, and how many look clean. Fix a level or the wording, or remove a piece. The panel shows the pasted text with the row you are on marked. **Add N draft blocks** keeps the text as a source and adds the pieces you kept, as AI drafts for you to check first. **Copy prompt for your AI** hands the same job to your own AI tool over MCP.

## The plan

The first part of the base. Blocks build up from the bottom; the plan breaks the question down from the top, and the two meet at insights.

- **Sub-questions**: what you need to know to make the decision, each with what you expect to find. Each one folds open to show what answers it, what is **already known** in other workspaces, and its wording to change or **Remove**.
- **Add a sub-question**, and **Copy prompt for your AI**.
- Folded at the bottom: the question and the decision.

## The base

The plan, the sources, the method, and notes for checkers. A source is added as a **Link** (a title and the URL) or a **Note** (a title and the text). Links are the default: the source stays where it lives, and each observation says the spot in it.

## The package

The checked insights the workspace shares for the decision, grouped by sub-question. Each shows what it is based on (blocks, observations, sources) and how much of that still needs a check, plus any observations two insights share.
