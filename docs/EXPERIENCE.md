# The experience: the workbench

How the app shows the work, and why. The goal: open a workspace, see how the insights are built and what still needs a check, and check it in a few clicks. The words are defined in [GLOSSARY.md](GLOSSARY.md).

## Design rules

1. One idea per element. A block shows its statement. How full it looks says how far it has been checked.
2. Only trouble gets words and color: Needs a check, Needs changes, Disagree, Rests on nothing, and ⚠ for something unchecked underneath.
3. Show what is under everything. Lines connect each block to what it is built on, down to the sources.
4. What the AI says (confidence, why, assumes) sits apart from the check, and never counts as one.
5. Ask for the least first. Pick a verdict, then say how you checked or why.
6. The rest is one click away: history, what a block holds up, and the full source text.
7. One primary button per screen: **Check N blocks**.

## Home

A card per workspace: its question, the decision it serves, a strip of small squares (one per block, filled by how far it is checked), and how many blocks wait on you. Below: **New workspace** asks for the question and the decision it will inform.

## A workspace: Build

```
Why do mobile shoppers leave checkout before paying?
For the decision: Whether to fund address autofill in Q3
[Check 3 blocks] [Break down AI text] [Connect] [Build | Review]
Package  (Address autofill is likely our biggest...  x)  Open
+--------------------------------------------------------------+
| INSIGHTS        [ solid, glowing ]     [ hollow, Needs a check ]|
| FINDINGS   [ solid ⚠ ]   [ mid ⚠ ]   [ red, Disagree ]          |
| OBSERVATIONS [light][mid][hollow][solid][hollow][amber]...      |
| BASE          (source) (source) (source) (source)               |
| [Question and decision][Context][Method and approach][Notes +]  |
+--------------------------------------------------------------+
Fuller means more checked: not yet, owner, peers, SME
```

- Blocks build up from the base: sources, then observations, findings, and insights. Lines show what each block is built on. Dashed amber lines lead into parts that still need a check.
- Hover a block to trace its whole line: everything under it, down to the sources, and everything built on it. The rest fades.
- A thin base shows. A part of the base that is empty is striped, with "+ add".
- An insight glows once someone other than its owner has checked it.
- **Connect**: click blocks to pick them, then write the finding or insight they add up to, or copy a prompt for your AI tool.

## A workspace: Review

The same blocks as a list, for working through checks.

- **Needs a check**, **Needs attention** (changes asked, a disagreement, or resting on nothing), and **Checked** (folded).
- Each row: a level shape (square: observation, dashed circle: finding, diamond: insight), the statement, who made it, what the AI says, what it is built on, and its state.
- Filters by level, and **Mine**.

## The check panel

Opened by clicking any block or row, or stepped through with **Check N blocks**.

1. The statement, its check state, and who made it.
2. **From** (an observation's sources, with the matching lines marked) or **Built on** (the blocks under it, each with its state).
3. **AI says**, for blocks made with AI: confidence, why, and what it assumes. "This is the AI's own view. It never counts as a check."
4. **Your check**:
   - The owner of an AI draft reads it, fixes the wording if needed, and says **Looks right**.
   - When changes were asked for, the owner changes the wording, which saves a new version.
   - Anyone else picks **Looks right**, **Needs changes**, or **Disagree**, then says how they checked or why.
   - A draft is checked by its owner first. Others see who it is waiting on.
5. Folded: **Holds up** (what is built on it) and **History** (each check, and the AI's original wording if the owner changed it).

## Break down AI text

Paste a long AI answer. The built-in splitter keeps the text as a source and makes one draft block per sentence, with a guessed level. Claims with nothing under them are flagged as resting on nothing, and words like "most", "clearly", or "because" are listed as what the block assumes. Nothing leaves the app. **Copy prompt for your AI** hands the same job to your own AI tool over MCP, which can cite the right sources, build findings on observations, and say how sure it is.

## The base

Click a part of the base to fill it in: the question and decision, the sources (add one, or copy a prompt for your AI to draft observations from them), the method, and notes for checkers.

## The package

Insights added to the package show at the top. Opened, each shows what it rests on (blocks, observations, sources) and how much of that still needs a check, plus any observations two insights share. Narratives come later.
