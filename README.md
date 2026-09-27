# ANCHOR

**A**mped **N**etwork for **C**redible **H**ypotheses, **O**bservations, and **R**esearch

An open source framework for research teams. A shared, checkable layer of research findings that people and AI agents can query before making new claims, and that stays honest about who said what and how sure anyone should be.

See [PRINCIPLES.md](PRINCIPLES.md) for the why, and [CONTEXT.md](CONTEXT.md) for the background and architecture.

This is the first prototype slice. It proves out three things:

1. A finding's trust is visible and inspectable, not a single flag. You can see its tier, its evidence, and every person who validated it.
2. Contradictions surface instead of hiding. Both sides stay visible, and the history of what changed is kept.
3. The same actions work the same way from an AI agent (MCP) or from the web UI, because both call the same core functions.

## Layout

```
anchor/
  core.py         data store and all actions (the only write path)
  mcp_server.py   MCP tools, a thin wrapper on core
  web.py          small JSON API + static page, also a thin wrapper on core
  static/index.html
scripts/seed.py   loads a handful of test findings
tests/            core tests
```

Stack: Python 3.10+, SQLite (stdlib), the `mcp` Python SDK. The web app uses only the Python standard library and plain HTML and JavaScript.

## Quick start

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest

.venv/bin/python scripts/seed.py            # creates anchor.db with test data
.venv/bin/python -m anchor.web              # http://127.0.0.1:8000
.venv/bin/python -m pytest
```

The database path is `anchor.db` in the current folder unless you set `ANCHOR_DB`.

## Connect an AI tool over MCP

The MCP server runs over stdio. For Claude Code:

```bash
claude mcp add anchor -e ANCHOR_DB=/absolute/path/anchor.db -- \
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
      "env": { "ANCHOR_DB": "/absolute/path/anchor.db" }
    }
  }
}
```

Point the web app and the MCP server at the same database file and changes from one show up in the other (the page refreshes every 10 seconds).

## Data model

**findings**: `id`, `statement`, `tier` (data_point, hypothesis, insight), `status` (proposed, validated, contested), `owner`, `evidence_links` (list of finding ids), `created_at`, `checked_out_by`, `checked_out_at`.

**validations**: one row per validation. `finding_id`, `validated_by`, `validated_at`, `note`. Many people can validate the same finding and each one stays visible.

**conflicts**: one row per confirmed contradiction. `finding_id`, `conflicting_id`, `flagged_by`, `flagged_at`, `note`.

**events**: append only log of every action. Drives the activity feed and keeps prior state (for example, the status a finding had before it was contested).

## Actions

| Core function | MCP tool | Web API |
|---|---|---|
| `query(topic, tier, status)` | `query` | `GET /api/findings?q=&tier=&status=` |
| `propose(statement, tier, owner, evidence_links)` | `propose` | `POST /api/propose` |
| `validate(finding_id, validated_by, note)` | `validate` | `POST /api/validate` |
| `check_conflict(statement or finding_id)` | `check_conflict` | `POST /api/check_conflict` |
| `confirm_conflict(finding_id, conflicting_id, confirmed_by, note)` | `check_conflict` with `confirm_with` | `POST /api/confirm_conflict` |
| `checkout(finding_id, who)` | `checkout` | `POST /api/checkout` |
| `release(finding_id, who)` | `release` | `POST /api/release` |
| `activity()`, `get(id)`, `history(id)` | (via query) | `GET /api/activity`, `/api/findings/{id}`, `/api/findings/{id}/history` |

## Rules in this slice

- New findings always start as `proposed`.
- The first validation moves a finding from `proposed` to `validated`. Later validations are added to the list.
- A person cannot validate the same finding twice, and the owner cannot validate their own finding. (Names are free text for now, so this is a guardrail, not security.)
- Validating a `contested` finding records the validation but does not change the status. Resolving conflicts is a later slice.
- `propose` runs a conflict check automatically and returns possible conflicts. It never blocks.
- A hypothesis or insight proposed with no evidence links gets a warning.
- Checkout is advisory. Checking out something someone else holds, or acting on it, works but returns a warning.

## How the conflict check works

It is a simple text heuristic, so there are no model or API dependencies:

1. Compare topic words (stop words and direction words removed, light stemming) against every validated or contested finding. A candidate needs an overlap score of at least 0.5 and at least two shared words.
2. For each candidate, look for signals that the two disagree: one is negated and the other is not, they point in opposite directions (increase vs decrease), or they cite different numbers.

The check only suggests. Nothing changes until a person confirms, at which point both findings become `contested` and show side by side. The heuristic is isolated in `core.py` so it can be swapped for embeddings or an LLM judge later.

## Not in this slice

Auth and permissions, assignment and intake, AI provenance tracking, promoting a hypothesis to an insight, conflict resolution.
