# Set up ANCHOR for your team

This guide takes a research lead from nothing to a working team instance: install it, make the key choices for your team, connect your AI tools, and run a first loop in week one.

It takes about 30 minutes, most of it deciding who is on your team.

## 1. What you are setting up

ANCHOR is a shared, checkable layer of research findings. Anyone on your team, and the AI tools they work with, can check what is already known before making a new claim, and see how much to trust each finding.

It is a framework, not a fixed process. The defaults are open: anyone can propose, review, promote, and log decisions, and roles only show how much weight a review carries. Your team decides how much structure to add, in one plain file.

Three pieces, one core:

- **The core** holds everything in one SQLite file you own. There is one write path.
- **The web app** is the shared status board: studies, findings, review queues, decisions.
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

To explore first, load the sample team and findings into a separate file:

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
"Dana" = "trusted_reviewer"   # for example your data science lead
"Jordan" = "contributor"
"Morgan" = "stakeholder"
```

The four built-in roles are researcher, trusted reviewer, people who do research (`contributor`), and stakeholder. Anyone not listed can still join: they get `default_role` the first time they act, and anyone can change a role from a person's page. Every role change is logged. People listed in the file get their role from it each time ANCHOR starts.

### Whose reviews count as trusted

```toml
[roles.researcher]
label = "Researcher"
trusted = true

[roles.data_science]      # add your own
label = "Data science"
trusted = true
```

Reviews from trusted roles are counted by role in each finding's trust summary, for example "Validated by 2 researcher, 1 peer". Everyone else counts as a peer. Nothing is blocked by role. Pick trusted reviewers for their judgment, inside or outside research.

### What you call things

```toml
[tiers]
insight = "Learning"

[checks]
source_data = "Checked the query"
```

Rename tiers and the "how I checked" choices to match your team's language. The meaning of each tier stays the same.

### What a study captures

Every study has a title, objective, the decision it serves, method, and sample. Add what your team also tracks:

```toml
[[study.fields]]
key = "intake_link"
label = "Intake ticket"
help = "Link to the request in our tracker"

[[study.fields]]
key = "participants"
label = "Participant criteria"
required = true
```

Required fields show a warning when empty. They never block, so people can start a study and fill it in later. If you already run an intake and prioritization process, add a field for its link so every study and research request points back to it.

### When something is ready to promote

Anyone can promote a data point to a hypothesis, or a hypothesis to an insight. Promotion creates a new, linked finding, so the original stays as it was. Set a readiness rule if you want one:

```toml
[promote]
min_trusted_validations = 1   # or min_validations = 2
trusted_roles_ready = true    # a researcher's promotion counts as ready
enforce = "signal"            # or "required" to stop promotion until ready
```

Start with `signal`. Move to `required` only if the team finds it needs the gate.

### Which work modes to show

```toml
modes = ["home", "findings", "validate", "decisions"]
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
| Set up | Get started with ANCHOR |
| Plan | Plan a study |
| Analyze | Synthesize my notes |
| Insights | Shape an insight |
| Explore | Check before I claim |
| Validate | Review my queue, Request validation |
| Decide | Find insights for a decision, Log a decision |

Each prompt tells the AI to query first, show trust and conflicts, never treat proposed or contested findings as settled, and never review on a person's behalf.

## 5. Your first week

Aim for one full loop, small and real.

1. **Start one real study.** Pick a question tied to a decision someone is about to make. In the app, go to Studies and start it with its objective and the decision it serves.
2. **Invite people who do research.** Share the app link. Each person picks their name the first time. Suggest they connect their AI tool and try "Synthesize my notes" on something they already have.
3. **Capture findings in the study.** Data points first, then hypotheses linked to them as evidence.
4. **Run one validation round.** Ask for reviews from a role ("any researcher") or named people. Reviewers approve, ask for changes, or disagree, and say how they checked. Owners revise when asked.
5. **Promote one insight** when the evidence supports it.
6. **Have a stakeholder log one decision** using that insight. They will see everyone behind it, and hear if something it relied on is later contested.
7. **Loop back.** If the decision raises a new question, ask for research from the decision page. It lands as a requested study.

After the week, look at what felt heavy or missing and adjust `anchor.toml`: roles, template fields, or the promotion rule. That is the point: the framework bends to the team.

## 6. Where to go next

- [FLOW.md](FLOW.md): the full loop, who does what, and the roadmap
- [PRINCIPLES.md](../PRINCIPLES.md): the why
- [README.md](../README.md): the actions table, data model, and how the browser demo works
- [Roadmap (#47)](https://github.com/mitchh14/amped-insights/issues/47)
