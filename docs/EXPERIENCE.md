# The experience: the workbench

How the app shows the work, and why. The goal: open a workspace, see how the insights are built and what still needs a check, and check it in a few clicks. The words are defined in [GLOSSARY.md](GLOSSARY.md).

## Design rules

1. One idea per element. A block shows its statement. How full it looks says how far it has been checked.
2. Only trouble gets words and color: Needs changes, Disagree, Unsupported, and ⚠ for something unchecked underneath. A block that needs a check is dashed, with no words.
3. Show what is under everything. Lines connect each block to what it is based on, down to the sources. They stay faint until you trace one.
4. What the AI says (confidence, why, assumes) sits apart from the check, and never counts as one.
5. Ask for the least first. Pick a verdict, then say how you checked or why.
6. Never get lost. The cabinet on the right always says where you are, and the detail lives there, not in a new page.
7. One primary button per screen: **Check N blocks**.

The workbench is built for a desktop, side by side with your AI tool (paired over MCP), or inside it. On a phone the cabinet slides over the work.

## Home

A card per workspace: its question, the decision it serves, a strip of small squares (one per block, filled by how far it is checked), how many blocks wait on you, and how far the plan has got ("1 of 4 answered"). Below: **New workspace** asks for the question and the decision it will inform, then opens the plan so the first thing you do is say what you need to know.

## A workspace

```
+--------------------------------------------------+------------------------------+
| Why do mobile shoppers leave checkout...?        | Workspace › Insight #11 ›    |
| For the decision: fund address autofill in Q3    |   Finding #8        Wider  x |
| [Check 3 blocks] [Break down AI text] [Build|List]| Checking 2 of 3  Skip  Stop |
|                    Lines: Faint · Traced only ·  | Finding #8                   |
|                    Connect blocks                | Shoppers leave mobile ...    |
|  INSIGHTS      [ solid, glowing ] [ dashed ]     | Checked by an SME · Jordan   |
|  FINDINGS   [ solid ⚠ ] [ mid ] [ red, Disagree ]| Based on: 3 blocks           |
|  OBSERVATIONS [light][mid][dashed][solid]...     | AI says (apart from checks)  |
|  BASE          (source) (source) (source)        | Your check                   |
|  [The plan][Context][Method][Notes]              | > Things to consider         |
|                                                  | > Supports · History · Ask AI|
+--------------------------------------------------+------------------------------+
```

The work is on the left, the cabinet on the right. The header holds the question, the decision, and three controls: **Check N blocks**, **Break down AI text**, and **Build | List**.

## Build

- Blocks build up from the base: sources, then observations, findings, and insights. Lines show what each block is based on. Dashed amber lines lead into parts that still need a check.
- Lines are faint. Hover a block, or open it, to trace its whole line: everything under it, down to the sources, and everything based on it. The rest fades. **Traced only** hides every other line.
- A thin base shows. A part of the base that is empty is striped, with "+ add".
- An insight glows once someone other than its owner has checked it.
- **Connect blocks**: click blocks to pick them, then write the finding or insight they add up to, or copy a prompt for your AI tool. Pick the sub-question it answers; starting from a sub-question picks it for you.

## List

The same blocks as rows, for working through checks.

- **Waiting on you** (with why: your AI draft, changes asked, asked of you, or nobody else has checked it), **Needs attention** (changes asked, a disagreement, or resting on nothing), and **Everything else** (folded).
- Each row: a level shape (square: observation, dashed circle: finding, diamond: insight), the statement, its number, who made it, and only trouble on the right.
- J and K move through the list.

## The cabinet

The panel on the right. Beside a workspace it is always open.

- **The trail** at the top says where you are: `Workspace › Insight #11 › Finding #8`. Picking something in the work starts a new trail. Following a link inside the cabinet adds a step. Click any step to go back. **Wider** makes room to think. **×** goes back to the workspace.
- **Nothing picked**: the workspace. The plan, with each sub-question's state (Open, In progress, Answered) and a note when something is already known. What waits on you, with **Start**. What needs attention. The package. The base, folded. How to pair your AI tool, folded.
- **A block**:
  1. The statement, its check state, and who made it.
  2. **From** (an observation's sources, with the matching lines marked) or **Based on** (the blocks under it, each with its state).
  3. **AI says**, for blocks made with AI: confidence, why, and what it assumes. "This is the AI's own view. It never counts as a check."
  4. **Answers**, on a finding or insight when the workspace has a plan: pick the sub-question it answers. It is not a check.
  5. **Your check**:
     - The owner of an AI draft reads it, fixes the wording if needed, and says **Looks right**.
     - When changes were asked for, the owner changes the wording, which saves a new version.
     - Anyone else picks **Looks right**, **Needs changes**, or **Disagree**, then says how they checked or why.
     - A draft is checked by its owner first. Others see who it is waiting on.
  6. Folded: **Things to consider** (questions for this level, and private notes kept in your browser, open when the cabinet is wider), **Supports** (what is based on it), **History** (each check, and the AI's original wording if the owner changed it), and **Ask your AI about it** (a prompt for your AI tool to test the block against what it rests on, without checking it for you).
- **Check N blocks** steps through what waits on you, in the cabinet: "Checking 2 of 3", **Skip**, **Stop**. The block is lit up on the left with its line. After each check the next one opens.

## Break down AI text

It opens in the work area. Paste a long AI answer and **Break it down**. The built-in splitter shows the pieces first, one per sentence, with a guessed level, and writes nothing yet. A summary line counts them: how many rest on nothing, how many take things as given, how many look clean. Filter by **All**, **Needs a look**, or **Clean**. Fix a level or the wording, or remove a piece; the flags update from the core. The cabinet shows the pasted text with the row you are on marked. **Add N draft blocks** keeps the text as a source and adds exactly the pieces you kept, as AI drafts for you to check first. Claims with nothing under them are flagged as resting on nothing, and words like "most", "clearly", or "because" are listed as what the block assumes. Nothing leaves the app. **Copy prompt for your AI** hands the same job to your own AI tool over MCP, which can cite the right sources, build findings on observations, and say how sure it is.

## The plan

The first part of the base. Blocks build up from the bottom; the plan breaks the question down from the top, and the two meet at insights.

- **Sub-questions**: what you need to know to make the decision, each with what you expect to find. A few sharp ones beat many. Each one folds open to show:
  - **Answered by**: the findings and insights that answer it, with their check state, and **Connect blocks to answer it**.
  - **Already known**: up to three checked blocks from other workspaces that share its words, most checked first. Opening one shows it in the cabinet, marked as from elsewhere, with a link to its workspace. You can check it there.
  - The wording and what you expect, to change, and **Remove**. Blocks that answered a removed sub-question stay, and answer nothing.
- **Add a sub-question**, and **Copy prompt for your AI**, which asks your AI tool to draft sub-questions and say what is already known about each.
- Folded at the bottom: the question and the decision, to change.

## The base

Click a part of the base to fill it in: the plan, the sources (add one, or copy a prompt for your AI to draft observations from them), the method, and notes for checkers.

## The package

Insights added to the package show at the top. Opened, the package groups them by the sub-question they answer, and each shows what it is based on (blocks, observations, sources) and how much of that still needs a check, plus any observations two insights share. Narratives come later.
