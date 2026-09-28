# ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

An open source framework for research teams. A shared, checkable layer of what the team has learned, that people and AI tools can query before making new claims, and that stays honest about who said what, whether an AI drafted it, and how far to trust it. Use it, adapt it to how your team works, and help shape it. The roadmap is in [issue #47](https://github.com/mitchh14/amped-insights/issues/47).

**[Try the demo](https://mitchh14.github.io/amped-insights/)** in any browser, on desktop or phone. It runs the real Python core in your browser, so nothing you type leaves your device. See [Browser demo](#browser-demo) for how it works.

**Setting it up for your team?** Start with [docs/SETUP.md](docs/SETUP.md).

See [PRINCIPLES.md](PRINCIPLES.md) for the why, [CONTEXT.md](CONTEXT.md) for the background and architecture, [docs/FLOW.md](docs/FLOW.md) for the full research loop and who does what, and [docs/EXPERIENCE.md](docs/EXPERIENCE.md) for how the app decides what to show. The words we use are defined in [docs/GLOSSARY.md](docs/GLOSSARY.md).

It closes the research loop end to end:

1. **Plan**: a study starts with its question and the decision it serves. Method and who took part are asked for when it is running, and what we learned when it is finished. Learnings inside it carry that context.
2. **Learn**: anyone adds a learning at one of three levels: an observation (what we saw), a finding (what we think it means, not yet an insight), or an insight (what it means for us and what to do). Promotion takes one up a level as a new, linked learning.
3. **Show who made it**: every learning records whether a person wrote it, a person worked with AI, or an AI agent made it. Anything made with AI is a draft until its owner confirms it, and the record keeps whether they changed the AI's wording.
4. **Connect**: links (supports, builds on, same as, conflicts with), and conflicts surface instead of hiding.
5. **Review**: anyone reviews (approve, ask for changes, or disagree) and says how they checked. Each learning shows one trust state: Not reviewed, Needs changes, Checked by peers, Checked by an SME, or Contested.
6. **Decide**: a stakeholder logs a decision and the learnings it relied on, which credits everyone in the chain and flags the decision if something it relied on is later contested. The app asks what happened later.
7. **Loop back**: a decision or an empty search raises a research request.

Each person sees one next step, what changed for them, and moments when their work mattered. The same actions work the same way from an AI tool (MCP) or the web app, because both call the same core functions. A team shapes it with one plain config file, `anchor.toml`.

## Layout

```
anchor/
  core.py         data store and all actions (the only write path)
  config.py       loads the team's anchor.toml over open defaults
  api.py          JSON API routing as a plain function (shared by web.py and the demo)
  seed.py         a sample team walking the full loop (used by scripts/seed.py and the demo)
  mcp_server.py   MCP tools and guided prompts, a thin wrapper on core
  web.py          small JSON API + static page, also a thin wrapper on core
  static/index.html   the web app: one next step, then short lists, then folded detail
anchor.example.toml   every team choice, explained
docs/SETUP.md     setup guide for a research lead
docs/GLOSSARY.md  the words ANCHOR uses, and what each means
docs/EXPERIENCE.md  how the app decides what to show, and when
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

The demo is the same web page and the same Python code, running inside the browser with [Pyodide](https://pyodide.org) (Python compiled to WebAssembly). `demo/demo.js` loads `core.py`, `api.py`, and `seed.py`, and answers the page's `/api/` requests in the browser instead of sending them to a server. The database is SQLite, stored in the browser's IndexedDB, so changes stay put between visits. "Reset demo" reloads the sample team. Pick any person to see their next step: Jordan confirms an AI draft, Sam (an SME) reviews, and Morgan (stakeholder) says what happened after a decision.

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

Everything is plain SQLite tables. There is no migration code yet: an older database is refused with a clear message, so start a new file.

- **learnings**: `statement`, `level` (observation, finding, insight), `stage` (draft, shared, replaced), `origin` (person, person_with_ai, ai_agent), `owner`, `evidence`, `study_id`, `promoted_from`, `revises`, and who is working on it. Trust is not stored: it is worked out from reviews and conflicts.
- **reviews**: one row per review, never collapsed. `verdict` (approve, changes, disagree), `how` they checked, `note`, and the reviewer's `role` and SME standing at the time. A person's latest review counts; earlier ones stay visible.
- **review_requests**: who was asked (a person, anyone in a role, or any SME), and whether it is open, done, or withdrawn.
- **links**: builds_on and same_as. Supports is evidence and conflicts_with is a conflict, so each fact lives in one place.
- **conflicts**: confirmed conflicts. Both sides stay visible.
- **studies**: the question, the decision it serves, an optional hypothesis, method, sample, what we learned, stage (requested, planned, running, finished, dropped), owner, team template `fields`, and where a request came from.
- **decisions** and **decision_uses**: what was decided, by whom, the learnings it relied on and their trust at the time, and the outcome once known.
- **people**: name, role, and whether they are an SME. Names match without regard to case.
- **follows** and **seen**: what a person follows, and what they have seen or set aside with "Not now".
- **events**: append only record of every action. Drives history, the digest, and moments.

## Actions

Every action is one core function, served by the web API and by an MCP tool, so the app and an AI tool can always do the same things. A test (`tests/test_parity.py`) fails if a core action is missing from either.

In MCP, the person's name is set once per session with `set_identity` (or the `ANCHOR_USER` environment variable) and every tool acts as them.

| Mode | Core function | MCP tool | Web API |
|---|---|---|---|
| Set up | `whoami(name)` | `whoami`, `set_identity` | `POST /api/whoami` |
| Set up | `people()`, `person(name)` | `people`, `person` | `GET /api/people`, `/api/people/{name}` |
| Set up | `set_person(name, by, role, sme)` | `set_person` | `POST /api/set_person` |
| Set up | `team_config()` | `team_config` | `GET /api/config` |
| Home | `next_step(who)` | `next_step` | `GET /api/next?who=` |
| Home | `digest(who, since, limit)` | `whats_new` | `GET /api/digest?who=` |
| Home | `mark_seen(who, keys)` | `mark_seen` | `POST /api/mark_seen` |
| Plan | `start_study(question, owner, decision, hypothesis, fields)` | `start_study` | `POST /api/start_study` |
| Plan | `update_study(study_id, by, ...)` | `update_study` | `POST /api/update_study` |
| Plan | `get_study(id)`, `list_studies(status, owner)` | `get_study`, `list_studies` | `GET /api/studies/{id}`, `/api/studies` |
| Learn | `add(statement, level, owner, evidence, study_id, origin)` | `add` | `POST /api/add` |
| Learn | `confirm(learning_id, by, statement, note)` | `confirm` | `POST /api/confirm` |
| Learn | `promote(learning_id, by, statement, note, origin)` | `promote` | `POST /api/promote` |
| Learn | `revise(learning_id, by, statement, note, origin)` | `revise` | `POST /api/revise` |
| Find | `query(topic, level, trust)` | `query` | `GET /api/learnings?q=&level=&trust=` |
| Find | `get(id)`, `history(id)` | `get`, `history` | `GET /api/learnings/{id}`, `/api/learnings/{id}/history` |
| Connect | `link(from_id, to_id, type, by, note)` | `link` | `POST /api/link` |
| Connect | `check_conflict(statement or learning_id)` | `check_conflict` | `POST /api/check_conflict` |
| Review | `review(learning_id, by, verdict, how, note)` | `review` | `POST /api/review` |
| Review | `ask_for_review(learning_id, by, people, roles, note)` | `ask_for_review` | `POST /api/ask_for_review` |
| Review | `withdraw_request(request_id, by)` | `withdraw_request` | `POST /api/withdraw_request` |
| Review | `my_queue(who)` | `my_queue` | `GET /api/queue?who=` |
| Review | `working_on(learning_id, who, on)`, `follow(learning_id, who, on)` | `working_on`, `follow` | `POST /api/working_on`, `/api/follow` |
| Decide | `log_decision(title, made_by, learning_ids, note)` | `log_decision` | `POST /api/log_decision` |
| Decide | `update_decision(decision_id, by, outcome, note, add_learning_ids)` | `update_decision` | `POST /api/update_decision` |
| Decide | `get_decision(id)`, `list_decisions(made_by)` | `get_decision`, `list_decisions` | `GET /api/decisions/{id}`, `/api/decisions` |
| Loop back | `ask_for_research(question, by, decision, from_decision_id, from_query)` | `ask_for_research` | `POST /api/ask_for_research` |
| All | `activity(limit)` | `activity` | `GET /api/activity` |

## Rules

Open by default. Roles inform, they never block, unless a team turns on a rule that says so.

- A learning a person writes starts as Shared and Not reviewed. One made with AI starts as a Draft that only its owner can confirm. A draft cannot be reviewed, asked about, or promoted.
- Trust is one state, first match wins: Contested (a confirmed conflict, or a current review disagrees), Needs changes, Checked by an SME, Checked by peers, Not reviewed.
- The owner cannot review their own learning. A person can review again; their latest review counts.
- A review request closes when that person, anyone in the requested role, or any SME (for an SME request) reviews. Anyone can review without being asked.
- Promotion adds a new, linked learning; the original stays as it was. Revision adds a new version and the old one becomes Replaced.
- Promotion readiness comes from the team's `[promote]` rule. It is a signal unless the team sets `enforce = "required"`.
- `add`, `promote`, and `revise` run a conflict check and return possible conflicts. They never block.
- Missing evidence, learnings used in a decision before they are checked, and study details a stage asks for come back as warnings.
- "I'm working on this" is a soft hold. It never stops anyone.

## How the conflict check works

It is a simple text heuristic, so there are no model or API dependencies:

1. Compare topic words (stop words and direction words removed, light stemming) against every shared learning that is checked or contested. A candidate needs an overlap score of at least 0.5 and at least two shared words.
2. For each candidate, look for signs that the two disagree: one is negated and the other is not, they point in opposite directions (increase vs decrease), or they cite different numbers.

The check only suggests. Nothing changes until a person confirms, at which point both learnings become Contested and show side by side. The heuristic is isolated in `core.py` so it can be swapped for embeddings or an LLM judge later.

## Not yet

Sign in and access controls, remote MCP over HTTP, conflict resolution, saving the prompt and query behind a learning, evidence quality fields, notifications outside the app, and the impact dashboard. See the [roadmap](https://github.com/mitchh14/amped-insights/issues/47).
