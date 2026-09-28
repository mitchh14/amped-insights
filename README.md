# ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

An open source framework for research teams. A shared, checkable layer of research findings that people and AI agents can query before making new claims, and that stays honest about who said what and how sure anyone should be. Use it, adapt it to how your team works, and help shape it. The roadmap is in [issue #47](https://github.com/mitchh14/amped-insights/issues/47).

**[Try the demo](https://mitchh14.github.io/amped-insights/)** in any browser, on desktop or phone. It runs the real Python core in your browser, so nothing you type leaves your device. See [Browser demo](#browser-demo) for how it works.

**Setting it up for your team?** Start with [docs/SETUP.md](docs/SETUP.md).

See [PRINCIPLES.md](PRINCIPLES.md) for the why, [CONTEXT.md](CONTEXT.md) for the background and architecture, and [docs/FLOW.md](docs/FLOW.md) for the full research loop, who does what, and the roadmap. The words we use are defined in [docs/GLOSSARY.md](docs/GLOSSARY.md).

It closes the research loop end to end:

1. **Plan**: a study records why we looked, the decision it serves, the method, and the sample. Findings inside it carry that context.
2. **Analyze and generate insights**: anyone proposes data points, hypotheses, and insights with evidence, and promotes one tier up. Promotion creates a new, linked finding, so the chain stays readable.
3. **Explore**: typed links (supports, extends, duplicates, contradicts), and contradictions surface instead of hiding.
4. **Validate**: anyone reviews (approve, request changes, or disagree) and says how they checked. Each finding shows a trust summary by role, like "Validated by 2 researcher, 1 peer". Owners ask named people or a role for review, and revise when asked.
5. **Decide**: a stakeholder logs a decision and the findings used, which credits everyone in the chain behind it and flags the decision if something it used is later contested.
6. **Loop back**: a decision or an empty search raises a research request, which lands as a draft study.

The same actions work the same way from an AI tool (MCP) or the web app, because both call the same core functions. A team shapes it with one plain config file, `anchor.toml`.

## Layout

```
anchor/
  core.py         data store and all actions (the only write path)
  config.py       loads the team's anchor.toml over open defaults
  api.py          JSON API routing as a plain function (shared by web.py and the demo)
  seed.py         a sample team walking the full loop (used by scripts/seed.py and the demo)
  mcp_server.py   MCP tools and guided prompts, a thin wrapper on core
  web.py          small JSON API + static page, also a thin wrapper on core
  static/index.html   the web app, organized by work mode
anchor.example.toml   every team choice, explained
docs/SETUP.md     setup guide for a research lead
docs/GLOSSARY.md  the words ANCHOR uses, and what each means
scripts/seed.py   loads the sample team into a new database
scripts/build_demo.py  builds the static browser demo
demo/             browser demo loader (Pyodide)
tests/            core tests
```

Stack: Python 3.10+, SQLite (stdlib), the `mcp` Python SDK. The web app uses only the Python standard library and plain HTML and JavaScript, with no build step.

## Quick start

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest

.venv/bin/python scripts/seed.py            # creates anchor.db with test data
.venv/bin/python -m anchor.web              # http://127.0.0.1:8000
.venv/bin/python -m pytest
```

The database path is `anchor.db` in the current folder unless you set `ANCHOR_DB`. The team config is `anchor.toml` in the current folder unless you set `ANCHOR_CONFIG`. With no config file, ANCHOR runs with open defaults. See [docs/SETUP.md](docs/SETUP.md) for the choices a team makes.

## Browser demo

The demo is the same web page and the same Python code, running inside the browser with [Pyodide](https://pyodide.org) (Python compiled to WebAssembly). `demo/demo.js` loads `core.py`, `api.py`, and `seed.py`, and answers the page's `/api/` requests in the browser instead of sending them to a server. The database is SQLite, stored in the browser's IndexedDB, so changes stay put between visits. "Reset demo" reloads the sample team. Pick any person to see their role's home: Morgan (stakeholder) or Sam (researcher) are good places to start.

There is no server, so there is nothing to host or secure. Each visitor has their own copy of the data.

A GitHub Action (`.github/workflows/demo.yml`) runs the tests, builds the demo, and publishes it to GitHub Pages on every push to `main`. One-time setup: in the repo, go to Settings > Pages and set Source to "GitHub Actions".

To build and try it locally:

```bash
python scripts/build_demo.py _site
python -m http.server -d _site 8001   # http://127.0.0.1:8001
```

The first load downloads Pyodide (about 10 MB) from the jsDelivr CDN. Browsers cache it after that.

## Connect an AI tool over MCP

The MCP server runs over stdio. For Claude Code:

```bash
claude mcp add anchor -e ANCHOR_DB=/absolute/path/anchor.db -e ANCHOR_USER="Your name" -- \
  /absolute/path/.venv/bin/python -m anchor.mcp_server
```

For Claude Desktop or other clients, add this to the MCP config:

```json
{
  "mcpServers": {
    "anchor": {
      "command": "/absolute/path/.venv/bin/python",
      "args": ["-m", "anchor.mcp_server"],
      "cwd": "/absolute/path/amped-insights",
      "env": { "ANCHOR_DB": "/absolute/path/anchor.db", "ANCHOR_USER": "Your name" }
    }
  }
}
```

Point the web app and the MCP server at the same database file and changes from one show up in the other (the page refreshes every 15 seconds). More clients, and the guided prompts for each work mode, are in [docs/SETUP.md](docs/SETUP.md#4-connect-your-ai-tools).

## Data model

Everything is plain SQLite tables. Older databases upgrade in place when opened.

- **findings**: `statement`, `tier` (data_point, hypothesis, insight), `status` (proposed, validated, contested), `owner`, `evidence_links`, `study_id`, `promoted_from`, `revises`, checkout fields.
- **validations**: one row per review, never collapsed. `outcome` (approve, changes_requested, disagree), `basis` (how they checked), the reviewer's `role` at the time, `note`. A person's latest review counts; earlier ones stay visible.
- **validation_requests**: who was asked to review (a person or anyone in a role), and whether it is open, done, or withdrawn.
- **links**: extends and duplicates between findings. Supports is an evidence link and contradicts is a conflict, so each fact lives in one place.
- **conflicts**: confirmed contradictions. Both sides stay visible.
- **studies**: title, objective, the decision it serves, method, sample, status (requested, planned, running, done, closed), owner, team template `fields`, and where a request came from.
- **decisions** and **decision_uses**: what was decided, by whom, the findings used and their status at the time, and the outcome.
- **people**: name and role. Names match without regard to case.
- **events**: append only log of every action. Drives the activity feed and keeps prior state.

## Actions

Every action is one core function, served by the web API and by an MCP tool with the same name, so the app and an AI tool can always do the same things. A test (`tests/test_parity.py`) fails if a core action is missing from either.

In MCP, the person's name is set once per session with `set_identity` (or the `ANCHOR_USER` environment variable) and every tool acts as them.

| Mode | Core function | MCP tool | Web API |
|---|---|---|---|
| Set up | `whoami(name)` | `whoami`, `set_identity` | `POST /api/whoami` |
| Set up | `people()`, `person(name)` | `people`, `person` | `GET /api/people`, `/api/people/{name}` |
| Set up | `set_role(name, role, by)` | `set_role` | `POST /api/set_role` |
| Set up | `team_config()` | `team_config` | `GET /api/config` |
| Plan | `start_study(title, owner, objective, decision, method, sample, status, fields)` | `start_study` | `POST /api/start_study` |
| Plan | `update_study(study_id, by, ...)` | `update_study` | `POST /api/update_study` |
| Plan | `get_study(id)`, `list_studies(status, owner)` | `get_study`, `list_studies` | `GET /api/studies/{id}`, `/api/studies` |
| Analyze | `propose(statement, tier, owner, evidence_links, study_id)` | `propose` | `POST /api/propose` |
| Insights | `promote(finding_id, by, statement, note)` | `promote` | `POST /api/promote` |
| Explore | `query(topic, tier, status)` | `query` | `GET /api/findings?q=&tier=&status=` |
| Explore | `get(id)`, `history(id)` | `get`, `history` | `GET /api/findings/{id}`, `/api/findings/{id}/history` |
| Explore | `link(from_id, to_id, type, by, note)` | `link` | `POST /api/link` |
| Explore | `check_conflict(statement or finding_id)` | `check_conflict` | `POST /api/check_conflict` |
| Explore | `confirm_conflict(finding_id, conflicting_id, confirmed_by, note)` | `check_conflict` with `confirm_with` | `POST /api/confirm_conflict` |
| Validate | `validate(finding_id, validated_by, note, outcome, basis)` | `validate` | `POST /api/validate` |
| Validate | `revise(finding_id, by, statement, note)` | `revise` | `POST /api/revise` |
| Validate | `request_validation(finding_id, requested_by, people, roles, note)` | `request_validation` | `POST /api/request_validation` |
| Validate | `withdraw_request(request_id, by)` | `withdraw_request` | `POST /api/withdraw_request` |
| Validate | `my_queue(who)` | `my_queue` | `GET /api/queue?who=` |
| Validate | `checkout(finding_id, who)`, `release(finding_id, who)` | `checkout`, `release` | `POST /api/checkout`, `/api/release` |
| Decide | `log_decision(title, made_by, finding_ids, note, outcome)` | `log_decision` | `POST /api/log_decision` |
| Decide | `update_decision(decision_id, by, outcome, note, add_finding_ids)` | `update_decision` | `POST /api/update_decision` |
| Decide | `get_decision(id)`, `list_decisions(made_by)` | `get_decision`, `list_decisions` | `GET /api/decisions/{id}`, `/api/decisions` |
| Loop back | `request_research(question, requested_by, decision, from_decision_id, from_query, fields)` | `request_research` | `POST /api/request_research` |
| All | `activity(limit)` | `activity` | `GET /api/activity` |

## Rules

Open by default. Roles inform, they never block, unless a team turns on a rule that says so.

- New findings always start as `proposed`. A finding is `validated` while at least one current review approves it.
- Asking for changes or disagreeing is shown to everyone but never contests a finding on its own. A conflict is confirmed separately, and then both findings become `contested`.
- The owner cannot review their own finding. A person can review again; their latest review counts.
- A review request closes when that person, or anyone in the requested role, reviews. Anyone can review without being asked.
- Promotion and revision create new, linked findings. The original stays as it was.
- Promotion readiness comes from the team's `[promote]` rule. It is a signal unless the team sets `enforce = "required"`.
- `propose` and `promote` run a conflict check and return possible conflicts. They never block.
- Missing evidence, unvalidated or contested findings used in a decision, and empty study fields come back as warnings.
- Checkout is advisory.

## How the conflict check works

It is a simple text heuristic, so there are no model or API dependencies:

1. Compare topic words (stop words and direction words removed, light stemming) against every validated or contested finding. A candidate needs an overlap score of at least 0.5 and at least two shared words.
2. For each candidate, look for signals that the two disagree: one is negated and the other is not, they point in opposite directions (increase vs decrease), or they cite different numbers.

The check only suggests. Nothing changes until a person confirms, at which point both findings become `contested` and show side by side. The heuristic is isolated in `core.py` so it can be swapped for embeddings or an LLM judge later.

## Not yet

Sign in and access controls, remote MCP over HTTP, conflict resolution, evidence quality fields, notifications, and the impact dashboard. See the [roadmap](https://github.com/mitchh14/amped-insights/issues/47).
