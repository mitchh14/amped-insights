# Set up ANCHOR for your team

This guide takes a research lead from nothing to a working team instance: install it, make the key choices for your team, connect your AI tools, and run a first loop in week one.

It takes about 30 minutes, most of it deciding who is on your team.

## 1. What you are setting up

ANCHOR is a shared, checkable layer of what your team has learned. Anyone on your team, and the AI tools they work with, can check what is already known before making a new claim, see how far to trust each learning, and see whether an AI drafted it.

It is a framework, not a fixed process. The defaults are open: anyone can add, review, promote, and log decisions. Your team names its SMEs, the people whose reviews count most in their area. Your team decides how much structure to add, in one plain file. The words used here are defined in [GLOSSARY.md](GLOSSARY.md).

Three pieces, one core:

- **The core** holds everything in one SQLite file you own. There is one write path.
- **The web app** is the workbench: workspaces where blocks build up from a base of context, a review list of what needs a check, and a way to break down long AI text.
- **The MCP server** lets each person use ANCHOR from their own AI tool.

Both the app and the MCP server call the same core functions, so there is one version of the truth. See [FLOW.md](FLOW.md) for the full research loop and who does what.

## 2. Install and run

You need Python 3.10 or newer.

```bash
git clone https://github.com/mitchh14/amped-insights.git anchor
cd anchor
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Start the web app:

```bash
.venv/bin/python -m anchor.web --db /path/to/anchor.db
```

Open http://127.0.0.1:8000. The database file is created on first run. Back it up like any other file.

To explore first, load the sample team and learnings into a separate file:

```bash
.venv/bin/python scripts/seed.py /tmp/anchor-sample.db
.venv/bin/python -m anchor.web --db /tmp/anchor-sample.db
```

### On a shared server

Run the same command on a machine your team can reach, with `--host 0.0.0.0`. Point everyone at the same database file.

**There is no sign in yet.** Names are chosen, not proven, so keep ANCHOR on your internal network or behind your VPN or single sign-on proxy. Sign in and access controls are on the roadmap ([#39](https://github.com/mitchh14/amped-insights/issues/39)). Research data is sensitive, so treat the database file with the same care as interview recordings.

## 3. Make it yours: `anchor.toml`

Copy the example and edit it:

```bash
cp anchor.example.toml anchor.toml
```

ANCHOR reads `anchor.toml` from the folder you start it in, or from the path in `ANCHOR_CONFIG`. Every section is optional. Changes apply on the next start. The example file explains every option. These are the choices that matter most.

### Who is on the team, and in what role

```toml
[people]
"Sam" = "researcher"
"Dana" = "pwdr"        # for example your data science lead
"Jordan" = "pwdr"
"Morgan" = "stakeholder"
```

The three built-in roles are researcher, PwDR (people who do research), and stakeholder. A role says what someone mainly does, and shapes their home page. Anyone not listed can still join: they get `default_role` the first time they act, and anyone can change a role from a person's page. Every change is logged. People listed in the file get their role from it each time ANCHOR starts.

### Who your SMEs are

```toml
smes = ["Sam", "Dana"]
```

SMEs are the people whose reviews show as "Checked by an SME". Everyone else's show as "Checked by peers". Anyone can be an SME, whatever their role: a researcher, a data science lead, a PM who knows the area best. Pick them for their judgment. Nothing is ever blocked by who someone is. You can also mark someone as an SME from their page in the app.

### What you call things

```toml
[levels]
insight = "Big idea"

[checks]
source_data = "Checked the query"
```

Rename the levels and the "how I checked" choices to match your team's language. The meaning of each level stays the same.

### What a study asks for, and when

A study starts with just its question and the decision it serves. The method and who took part are asked for when it is marked running, and "what we learned" when it is finished. Add what your team also tracks, and say at which stage to ask:

```toml
[[study.fields]]
key = "intake_link"
label = "Intake ticket"
help = "Link to the request in our tracker"
ask_at = "start"

[[study.fields]]
key = "participants"
label = "Participant criteria"
required = true          # ask_at defaults to "running"
```

Required fields show a warning at their stage. They never block. If you already run an intake and prioritization process, add a field for its link so every study points back to it.

### When something is ready to promote

Anyone can promote an observation to a finding, or a finding to an insight. Promotion adds a new, linked learning, so the original stays as it was. Set a readiness rule if you want one:

```toml
[promote]
min_sme_approvals = 1   # or min_approvals = 2
enforce = "signal"      # or "required" to stop promotion until ready
```

Start with `signal`. Move to `required` only if the team finds it needs the gate. With no rule, the app does not mention readiness at all.

### Moments, and asking what happened

```toml
moments = ["used", "built_on", "checked", "milestone"]
outcome_after_days = 28
```

Moments are small notes of good news: your work was used in a decision, someone built on it, an SME approved it, or a milestone. They never compare people. Leave the list empty to turn them off. `outcome_after_days` is when the app asks a decision maker what happened.

### Which work modes to show

```toml
modes = ["home", "learnings", "review", "decisions"]
```

Hide modes you are not using yet. Everything still works over MCP.

## 4. Connect your AI tools

The MCP server runs on each person's machine and talks to the shared database file. Set `ANCHOR_USER` to the person's name so every action is recorded as them, or leave it out and the AI will ask.

### Claude Code

```bash
claude mcp add anchor \
  -e ANCHOR_DB=/path/to/anchor.db \
  -e ANCHOR_CONFIG=/path/to/anchor.toml \
  -e ANCHOR_USER="Sam" \
  -- /path/to/anchor/.venv/bin/python -m anchor.mcp_server
```

### Claude Desktop

Add this to Claude Desktop's MCP config (Settings, Developer, Edit config):

```json
{
  "mcpServers": {
    "anchor": {
      "command": "/path/to/anchor/.venv/bin/python",
      "args": ["-m", "anchor.mcp_server"],
      "env": {
        "ANCHOR_DB": "/path/to/anchor.db",
        "ANCHOR_CONFIG": "/path/to/anchor.toml",
        "ANCHOR_USER": "Sam"
      }
    }
  }
}
```

### GitHub Copilot in VS Code

Add `.vscode/mcp.json` to a workspace:

```json
{
  "servers": {
    "anchor": {
      "type": "stdio",
      "command": "/path/to/anchor/.venv/bin/python",
      "args": ["-m", "anchor.mcp_server"],
      "env": { "ANCHOR_DB": "/path/to/anchor.db", "ANCHOR_USER": "Sam" }
    }
  }
}
```

### Any other MCP client

Run `python -m anchor.mcp_server` over stdio with the same environment variables. Tools that only connect to remote MCP servers, such as ChatGPT connectors, need the remote server in [#35](https://github.com/mitchh14/amped-insights/issues/35).

### Try the guided prompts

Once connected, look in your AI tool's prompt picker for ANCHOR's prompts:

| Mode | Prompt |
|---|---|
| Home | Get started with ANCHOR (what changed, and your next step) |
| Plan | Plan a study |
| Learn | Synthesize my notes, Break down AI text, Shape an insight |
| Find | Check before I claim |
| Review | Review my queue, Ask for review |
| Decide | Find insights for a decision, Log a decision |

Each prompt tells the AI to query first, show trust and conflicts, never treat a learning that is not checked as settled, and never review on a person's behalf. Anything the AI helps write is added as a draft with its confidence, why, and what it assumes, and the AI asks the person what they checked or changed before checking it for them.

## 5. Your first week

Aim for one full loop, small and real.

1. **Start one real study.** Pick a question tied to a decision someone is about to make. In the app, go to Studies and start it with the question and the decision it serves. Mark it running when you start, and add the method and who you are studying then.
2. **Invite PwDR.** Share the app link. Each person picks their name the first time and lands on the workspaces. Suggest they connect their AI tool and try "Break down AI text" on an AI summary they already have, then check the blocks it makes.
3. **Add learnings in the study.** Observations first, then findings that use them as evidence.
4. **Run one review round.** Ask any SME, a role, or named people. Reviewers approve, ask for changes, or disagree, and say how they checked. Owners revise when asked.
5. **Promote one insight** when the evidence supports it.
6. **Have a stakeholder log one decision** that relies on that insight. They will see everyone behind it, hear if something it relied on changes, and be asked what happened later.
7. **Loop back.** If the decision raises a new question, ask for research from the decision page. It lands as a requested study.

After the week, look at what felt heavy or missing and adjust `anchor.toml`: roles, SMEs, template fields, or the promotion rule. That is the point: the framework bends to the team.

## 6. Where to go next

- [FLOW.md](FLOW.md): the full loop, who does what, and the roadmap
- [PRINCIPLES.md](../PRINCIPLES.md): the why
- [GLOSSARY.md](GLOSSARY.md): the words, and what each means
- [README.md](../README.md): the actions table, data model, and how the browser demo works
- [Roadmap (#47)](https://github.com/mitchh14/amped-insights/issues/47)
