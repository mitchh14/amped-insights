"""Core layer: the data store and the actions on findings.

Everything that reads or writes findings goes through the Store class. The MCP
server and the web app are thin wrappers around it, so there is only one write
path and one version of the truth.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config as config_mod

TIERS = ("data_point", "hypothesis", "insight")
STATUSES = ("proposed", "validated", "contested")
# requested: someone asked for research and nobody has picked it up yet.
# closed: ended without running, for example answered by existing findings.
STUDY_STATUSES = ("requested", "planned", "running", "done", "closed")
STUDY_TEXT_FIELDS = ("title", "objective", "decision", "method", "sample")

DEFAULT_DB_PATH = os.environ.get("ANCHOR_DB", "anchor.db")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    statement       TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN {TIERS}),
    status          TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN {STATUSES}),
    owner           TEXT NOT NULL,
    evidence_links  TEXT NOT NULL DEFAULT '[]',  -- JSON list of finding ids
    created_at      TEXT NOT NULL,
    checked_out_by  TEXT,
    checked_out_at  TEXT
);

-- One row per validation action. Never collapsed into a single flag.
CREATE TABLE IF NOT EXISTS validations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    INTEGER NOT NULL REFERENCES findings(id),
    validated_by  TEXT NOT NULL,
    validated_at  TEXT NOT NULL,
    note          TEXT,
    UNIQUE (finding_id, validated_by)
);

-- A confirmed contradiction between two findings. Both stay visible.
CREATE TABLE IF NOT EXISTS conflicts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id      INTEGER NOT NULL REFERENCES findings(id),
    conflicting_id  INTEGER NOT NULL REFERENCES findings(id),
    flagged_by      TEXT NOT NULL,
    flagged_at      TEXT NOT NULL,
    note            TEXT
);

-- Why we looked, what decision it serves, and how it was studied. Findings
-- captured inside a study carry this context with them.
CREATE TABLE IF NOT EXISTS studies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT NOT NULL,
    objective         TEXT,
    decision          TEXT,  -- the business decision this study serves
    method            TEXT,
    sample            TEXT,
    status            TEXT NOT NULL CHECK (status IN {STUDY_STATUSES}),
    owner             TEXT,  -- empty while a request waits to be picked up
    fields            TEXT NOT NULL DEFAULT '{{}}',  -- team template fields, JSON
    requested_by      TEXT,
    from_decision_id  INTEGER,
    from_query        TEXT,
    created_at        TEXT NOT NULL
);

-- Everyone who has taken an action, with the role they hold on this team.
-- Names are matched without regard to case, so "sam" and "Sam" are one person.
CREATE TABLE IF NOT EXISTS people (
    name        TEXT PRIMARY KEY COLLATE NOCASE,
    role        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Append-only history. Drives the activity feed and keeps prior state
-- (for example the status a finding had before it was contested).
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id  INTEGER REFERENCES findings(id),
    kind        TEXT NOT NULL,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '{{}}'
);
"""

# Columns added after the first release. Applied to new and older databases
# alike, so there is one path to the current shape.
MIGRATIONS = (
    ("findings", "study_id", "INTEGER REFERENCES studies(id)"),
    ("events", "study_id", "INTEGER"),
)


class CoreError(ValueError):
    """Raised when an action is not allowed or the input is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(value: Any) -> str | None:
    """Trim free text; empty becomes None."""
    if value is None:
        return None
    return str(value).strip() or None


def _clean_fields(fields: dict[str, Any] | None) -> dict[str, Any]:
    if fields is None:
        return {}
    if not isinstance(fields, dict):
        raise CoreError("fields must be an object of template field values")
    return {str(k): v.strip() if isinstance(v, str) else v for k, v in fields.items()}


# ---------------------------------------------------------------------------
# Text matching. Deliberately simple and dependency free for the prototype.
# The conflict check only *suggests* candidates; a human always confirms.
# ---------------------------------------------------------------------------

STOPWORDS = set(
    """a an the is are was were be been being of to in on for with and or but at by
    from as that this these those it its their they them we our us you your i me my
    he she his her than then so if because about into over under after before per
    has have had do does did can could should would will may might must very really
    also just only some any all most many much such what which who whom when where why how""".split()
)
NEGATIONS = {
    "not", "no", "never", "none", "nobody", "nothing", "neither", "nor", "without",
    "isn't", "aren't", "wasn't", "weren't", "don't", "doesn't", "didn't", "won't",
    "can't", "cannot", "shouldn't", "hardly", "rarely",
}
UP_WORDS = {
    "increase", "increases", "increased", "increasing", "higher", "more", "up", "rise",
    "rises", "rose", "grew", "grow", "grows", "growth", "improve", "improves",
    "improved", "better", "faster", "prefer", "prefers", "preferred", "like", "likes",
    "positive", "gain", "gains", "boost", "boosts", "helps", "help",
}
DOWN_WORDS = {
    "decrease", "decreases", "decreased", "decreasing", "lower", "less", "fewer", "down",
    "drop", "drops", "dropped", "fall", "falls", "fell", "decline", "declines",
    "declined", "worse", "slower", "avoid", "avoids", "dislike", "dislikes",
    "negative", "loss", "hurt", "hurts", "reduce", "reduces", "reduced",
}
_WORD_RE = re.compile(r"[a-z0-9']+(?:\.[0-9]+)?")
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
_SUFFIXES = ("ments", "ment", "ings", "ing", "ness", "ers", "ed", "es", "ly", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def topic_tokens(text: str) -> set[str]:
    """Content words that describe what a statement is about (not its direction)."""
    skip = STOPWORDS | NEGATIONS | UP_WORDS | DOWN_WORDS
    return {
        _stem(w.strip("'"))
        for w in _words(text)
        if w not in skip and not _NUM_RE.match(w) and len(w) > 2
    }


def _numbers(text: str) -> set[str]:
    return {w for w in _words(text) if _NUM_RE.match(w)}


def _direction(text: str) -> int:
    words = set(_words(text))
    return (1 if words & UP_WORDS else 0) - (1 if words & DOWN_WORDS else 0)


def _negated(text: str) -> bool:
    return bool(set(_words(text)) & NEGATIONS) or "n't" in text.lower()


def similarity(a: str, b: str) -> tuple[float, set[str]]:
    """Overlap coefficient on topic words. Returns (score, shared words)."""
    ta, tb = topic_tokens(a), topic_tokens(b)
    if not ta or not tb:
        return 0.0, set()
    shared = ta & tb
    return len(shared) / min(len(ta), len(tb)), shared


def contradiction_signals(a: str, b: str) -> list[str]:
    """Cheap hints that two statements on the same topic disagree."""
    signals = []
    if _negated(a) != _negated(b):
        signals.append("one statement is negated and the other is not")
    da, db = _direction(a), _direction(b)
    if da and db and da != db:
        signals.append("statements point in opposite directions")
    na, nb = _numbers(a), _numbers(b)
    if na and nb and not (na & nb):
        signals.append(f"different numbers ({', '.join(sorted(na))} vs {', '.join(sorted(nb))})")
    return signals


SIMILARITY_THRESHOLD = 0.5
MIN_SHARED_WORDS = 2


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class Store:
    def __init__(self, path: str = DEFAULT_DB_PATH, config: dict | None = None):
        """Open (or create) the database at path.

        config is a full team config from config.load() or config.from_dict().
        When left out, it is loaded from ANCHOR_CONFIG or ./anchor.toml, and
        falls back to the open defaults.
        """
        self.path = path
        self.config = config if config is not None else config_mod.load()
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            for table, column, decl in MIGRATIONS:
                have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            self._sync_people(conn)

    def _sync_people(self, conn) -> None:
        """Make sure every name on record is a person with a role.

        Names already in older databases join with the default role. The config
        file is the source of truth for the people it lists.
        """
        conn.execute(
            "INSERT OR IGNORE INTO people (name, role, created_at) "
            "SELECT name, ?, ? FROM (SELECT owner AS name FROM findings "
            "UNION SELECT validated_by FROM validations UNION SELECT flagged_by FROM conflicts)",
            (self.config["default_role"], _now()),
        )
        for name, role in self.config["people"].items():
            conn.execute(
                "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT (name) DO UPDATE SET role = excluded.role",
                (name, role, _now()),
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # A fresh connection per call keeps the store safe to share between the
        # threaded web server and a separately running MCP server process.
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _log(conn, finding_id, kind, actor, _study=None, **detail) -> None:
        conn.execute(
            "INSERT INTO events (finding_id, study_id, kind, actor, at, detail) VALUES (?, ?, ?, ?, ?, ?)",
            (finding_id, _study, kind, actor, _now(), json.dumps(detail)),
        )

    @staticmethod
    def _study_row(conn, study_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM studies WHERE id = ?", (study_id,)).fetchone()
        if row is None:
            raise CoreError(f"study {study_id} does not exist")
        return row

    @staticmethod
    def _study_summary(row: sqlite3.Row) -> dict[str, Any]:
        return {k: row[k] for k in ("id", "title", "objective", "decision", "status", "owner")}

    def _study_warnings(self, study: dict[str, Any]) -> list[str]:
        """Gentle nudges toward a complete chain. Never blocks."""
        warnings = []
        if study["status"] != "requested":
            for key in ("objective", "decision"):
                if not study.get(key):
                    warnings.append(f"study has no {key} yet; findings are easier to trust with it")
        for field in self.config["study"]["fields"]:
            if field["required"] and not study["fields"].get(field["key"]):
                warnings.append(f"study template field '{field['label']}' is empty")
        return warnings

    @staticmethod
    def _row(conn, finding_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        if row is None:
            raise CoreError(f"finding {finding_id} does not exist")
        return row

    @staticmethod
    def _require_name(value: str | None, field: str) -> str:
        value = (value or "").strip()
        if not value:
            raise CoreError(f"{field} is required")
        return value

    def _person(self, conn, name: str | None, field: str) -> str:
        """Resolve a name to the person on record, adding them on first use.

        Returns the name as first recorded, so small differences in case do not
        split one person into two. New people get the team's default role.
        """
        name = self._require_name(name, field)
        row = conn.execute("SELECT name FROM people WHERE name = ?", (name,)).fetchone()
        if row:
            return row["name"]
        conn.execute(
            "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?)",
            (name, self.config["default_role"], _now()),
        )
        self._log(conn, None, "joined", name, role=self.config["default_role"])
        return name

    def _role_of(self, conn, name: str | None) -> str | None:
        if not name:
            return None
        row = conn.execute("SELECT role FROM people WHERE name = ?", (name,)).fetchone()
        return row["role"] if row else None

    def _person_dict(self, name: str, role: str) -> dict[str, Any]:
        info = self.config["roles"].get(role, {"label": role, "trusted": False})
        return {"name": name, "role": role, "role_label": info["label"], "trusted": info["trusted"]}

    @staticmethod
    def _summary(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "statement": row["statement"],
            "tier": row["tier"],
            "status": row["status"],
            "owner": row["owner"],
        }

    def _checkout_warning(self, row: sqlite3.Row, actor: str) -> list[str]:
        holder = row["checked_out_by"]
        if holder and holder != actor:
            return [
                f"finding {row['id']} is checked out by {holder} since "
                f"{row['checked_out_at']} (advisory, action still applied)"
            ]
        return []

    def _full(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        """A finding with everything needed to judge how much to trust it."""
        fid = row["id"]
        evidence_ids = json.loads(row["evidence_links"])
        evidence = []
        for eid in evidence_ids:
            erow = conn.execute("SELECT * FROM findings WHERE id = ?", (eid,)).fetchone()
            if erow is not None:
                evidence.append(self._summary(erow))
        cited_by = [
            self._summary(r)
            for r in conn.execute(
                "SELECT f.* FROM findings f, json_each(f.evidence_links) j "
                "WHERE j.value = ? ORDER BY f.id",
                (fid,),
            )
        ]
        validations = [
            dict(r)
            for r in conn.execute(
                "SELECT v.validated_by, p.role, v.validated_at, v.note FROM validations v "
                "LEFT JOIN people p ON p.name = v.validated_by "
                "WHERE v.finding_id = ? ORDER BY v.validated_at, v.id",
                (fid,),
            )
        ]
        conflicts = []
        for c in conn.execute(
            "SELECT * FROM conflicts WHERE finding_id = ? OR conflicting_id = ? ORDER BY id",
            (fid, fid),
        ):
            other_id = c["conflicting_id"] if c["finding_id"] == fid else c["finding_id"]
            conflicts.append(
                {
                    "with": self._summary(self._row(conn, other_id)),
                    "flagged_by": c["flagged_by"],
                    "flagged_at": c["flagged_at"],
                    "note": c["note"],
                }
            )
        srow = conn.execute("SELECT * FROM studies WHERE id = ?", (row["study_id"],)).fetchone()
        return {
            "id": fid,
            "statement": row["statement"],
            "tier": row["tier"],
            "status": row["status"],
            "owner": row["owner"],
            "owner_role": self._role_of(conn, row["owner"]),
            "created_at": row["created_at"],
            "study": self._study_summary(srow) if srow else None,
            "evidence_links": evidence_ids,
            "evidence": evidence,
            "cited_by": cited_by,
            "validations": validations,
            "conflicts": conflicts,
            "checked_out_by": row["checked_out_by"],
            "checked_out_at": row["checked_out_at"],
        }

    # -- read --------------------------------------------------------------

    def team_config(self) -> dict[str, Any]:
        """Display labels and team choices: roles, tiers, study template, modes."""
        return config_mod.public(self.config)

    def people(self) -> list[dict[str, Any]]:
        """Everyone on record with their role, grouped by role order in the config."""
        order = {r: i for i, r in enumerate(self.config["roles"])}
        with self._conn() as conn:
            rows = conn.execute("SELECT name, role FROM people ORDER BY name COLLATE NOCASE").fetchall()
        people = [self._person_dict(r["name"], r["role"]) for r in rows]
        return sorted(people, key=lambda p: order.get(p["role"], len(order)))

    def whoami(self, name: str) -> dict[str, Any]:
        """Look up a person, adding them with the default role if they are new."""
        with self._conn() as conn:
            name = self._person(conn, name, "name")
            return self._person_dict(name, self._role_of(conn, name))

    def _study_full(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        study = dict(row)
        study["fields"] = json.loads(row["fields"])
        findings = [
            self._full(conn, r)
            for r in conn.execute("SELECT * FROM findings WHERE study_id = ? ORDER BY id", (row["id"],))
        ]
        study["findings_by_tier"] = {t: [f for f in findings if f["tier"] == t] for t in TIERS}
        study["finding_count"] = len(findings)
        study["history"] = [
            {"kind": e["kind"], "actor": e["actor"], "at": e["at"], "detail": json.loads(e["detail"])}
            for e in conn.execute(
                "SELECT * FROM events WHERE study_id = ? AND finding_id IS NULL ORDER BY id", (row["id"],)
            )
        ]
        return study

    def get_study(self, study_id: int) -> dict[str, Any]:
        """A study with its objective, the decision it serves, and its findings by tier."""
        with self._conn() as conn:
            return self._study_full(conn, self._study_row(conn, study_id))

    def list_studies(self, status: str | None = None, owner: str | None = None) -> list[dict[str, Any]]:
        if status and status not in STUDY_STATUSES:
            raise CoreError(f"status must be one of {STUDY_STATUSES}")
        sql, args = "SELECT * FROM studies WHERE 1=1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if owner:
            sql += " AND owner = ? COLLATE NOCASE"
            args.append(owner.strip())
        with self._conn() as conn:
            rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
            out = []
            for r in rows:
                study = dict(r)
                study["fields"] = json.loads(r["fields"])
                study["finding_count"] = conn.execute(
                    "SELECT COUNT(*) FROM findings WHERE study_id = ?", (r["id"],)
                ).fetchone()[0]
                out.append(study)
        return out

    def get(self, finding_id: int) -> dict[str, Any]:
        with self._conn() as conn:
            return self._full(conn, self._row(conn, finding_id))

    def list_findings(
        self, tier: str | None = None, status: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        if tier and tier not in TIERS:
            raise CoreError(f"tier must be one of {TIERS}")
        if status and status not in STATUSES:
            raise CoreError(f"status must be one of {STATUSES}")
        sql, args = "SELECT * FROM findings WHERE 1=1", []
        if tier:
            sql += " AND tier = ?"
            args.append(tier)
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            return [self._full(conn, r) for r in conn.execute(sql, args).fetchall()]

    def query(
        self,
        topic: str = "",
        tier: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Findings that match a topic or question, best match first.

        An empty topic returns the most recent findings.
        """
        candidates = self.list_findings(tier=tier, status=status, limit=10_000)
        wanted = topic_tokens(topic or "")
        if not wanted:
            return candidates[:limit]
        scored = []
        for f in candidates:
            shared = wanted & topic_tokens(f["statement"])
            if shared:
                f["match_score"] = round(len(shared) / len(wanted), 2)
                scored.append(f)
        scored.sort(key=lambda f: (-f["match_score"], -f["id"]))
        return scored[:limit]

    def activity(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT e.*, f.statement, s.title AS study_title FROM events e "
                "LEFT JOIN findings f ON f.id = e.finding_id LEFT JOIN studies s ON s.id = e.study_id "
                "ORDER BY e.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "finding_id": r["finding_id"],
                "statement": r["statement"],
                "study_id": r["study_id"],
                "study_title": r["study_title"],
                "kind": r["kind"],
                "actor": r["actor"],
                "at": r["at"],
                "detail": json.loads(r["detail"]),
            }
            for r in rows
        ]

    def history(self, finding_id: int) -> list[dict[str, Any]]:
        with self._conn() as conn:
            self._row(conn, finding_id)
            rows = conn.execute(
                "SELECT * FROM events WHERE finding_id = ? ORDER BY id", (finding_id,)
            ).fetchall()
        return [
            {"kind": r["kind"], "actor": r["actor"], "at": r["at"], "detail": json.loads(r["detail"])}
            for r in rows
        ]

    # -- write -------------------------------------------------------------

    def set_role(self, name: str, role: str, by: str) -> dict[str, Any]:
        """Change someone's role. Logged, so role changes are visible to everyone."""
        if role not in self.config["roles"]:
            raise CoreError(f"role must be one of {tuple(self.config['roles'])}")
        warnings = []
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            name = self._person(conn, name, "name")
            previous = self._role_of(conn, name)
            conn.execute("UPDATE people SET role = ? WHERE name = ?", (role, name))
            self._log(conn, None, "role_set", by, person=name, role=role, previous_role=previous)
        if any(n.lower() == name.lower() for n in self.config["people"]):
            warnings.append(f"{name} is listed in the team config, which resets their role on restart")
        return {"person": self._person_dict(name, role), "warnings": warnings}

    def start_study(
        self,
        title: str,
        owner: str,
        objective: str | None = None,
        decision: str | None = None,
        method: str | None = None,
        sample: str | None = None,
        status: str = "planned",
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Open a study: why we are looking, the decision it serves, and how.

        Only a title is needed to start. Missing objective, decision, or
        required template fields come back as warnings, never errors, so a
        team can start now and fill in details as they learn them.
        """
        title = self._require_name(title, "title")
        if status not in STUDY_STATUSES:
            raise CoreError(f"status must be one of {STUDY_STATUSES}")
        with self._conn() as conn:
            owner = self._person(conn, owner, "owner")
            cur = conn.execute(
                "INSERT INTO studies (title, objective, decision, method, sample, status, owner, fields, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, _clean(objective), _clean(decision), _clean(method), _clean(sample),
                 status, owner, json.dumps(_clean_fields(fields)), _now()),
            )
            sid = cur.lastrowid
            self._log(conn, None, "study_started", owner, sid, status=status)
        study = self.get_study(sid)
        return {"study": study, "warnings": self._study_warnings(study)}

    def update_study(self, study_id: int, by: str, **changes: Any) -> dict[str, Any]:
        """Change a study's details, status, or owner. Template fields are merged.

        The previous values are kept in the study's history.
        """
        allowed = set(STUDY_TEXT_FIELDS) | {"status", "owner", "fields"}
        unknown = set(changes) - allowed
        if unknown:
            raise CoreError(f"cannot update {sorted(unknown)}; choose from {sorted(allowed)}")
        if "status" in changes and changes["status"] not in STUDY_STATUSES:
            raise CoreError(f"status must be one of {STUDY_STATUSES}")
        if "title" in changes:
            changes["title"] = self._require_name(changes["title"], "title")
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            row = self._study_row(conn, study_id)
            if changes.get("owner"):
                changes["owner"] = self._person(conn, changes["owner"], "owner")
            updates, previous = {}, {}
            for key, value in changes.items():
                if key == "fields":
                    value = json.dumps({**json.loads(row["fields"]), **_clean_fields(value)})
                elif key != "status":
                    value = _clean(value)
                if value != row[key]:
                    updates[key] = value
                    previous[key] = row[key]
            if updates:
                conn.execute(
                    f"UPDATE studies SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                    (*updates.values(), study_id),
                )
                self._log(conn, None, "study_updated", by, study_id,
                          changed=sorted(updates), previous=previous)
        study = self.get_study(study_id)
        return {"study": study, "warnings": self._study_warnings(study)}

    def propose(
        self,
        statement: str,
        tier: str,
        owner: str,
        evidence_links: list[int] | None = None,
        study_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a finding with status 'proposed', optionally inside a study.

        Also runs a conflict check so contradictions surface at the moment a
        finding enters the system. The check never blocks the proposal.
        """
        statement = self._require_name(statement, "statement")
        if tier not in TIERS:
            raise CoreError(f"tier must be one of {TIERS}")
        links = sorted({int(x) for x in (evidence_links or [])})
        warnings = []
        with self._conn() as conn:
            owner = self._person(conn, owner, "owner")
            for eid in links:
                self._row(conn, eid)
            if study_id is not None:
                study_id = self._study_row(conn, int(study_id))["id"]
            cur = conn.execute(
                "INSERT INTO findings (statement, tier, status, owner, evidence_links, study_id, created_at) "
                "VALUES (?, ?, 'proposed', ?, ?, ?, ?)",
                (statement, tier, owner, json.dumps(links), study_id, _now()),
            )
            fid = cur.lastrowid
            self._log(conn, fid, "proposed", owner, study_id, tier=tier, evidence_links=links)
        if tier != "data_point" and not links:
            warnings.append(f"this {tier} has no evidence links yet")
        conflicts = self.check_conflict(finding_id=fid)["candidates"]
        return {"finding": self.get(fid), "possible_conflicts": conflicts, "warnings": warnings}

    def validate(self, finding_id: int, validated_by: str, note: str | None = None) -> dict[str, Any]:
        """Add one validation record. The first one moves 'proposed' to 'validated'.

        A contested finding keeps its 'contested' status: more validations are
        recorded and visible, but they do not silently resolve the conflict.
        """
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            validated_by = self._person(conn, validated_by, "validated_by")
            if row["owner"] == validated_by:
                raise CoreError("a finding cannot be validated by its own owner")
            warnings = self._checkout_warning(row, validated_by)
            try:
                conn.execute(
                    "INSERT INTO validations (finding_id, validated_by, validated_at, note) "
                    "VALUES (?, ?, ?, ?)",
                    (finding_id, validated_by, _now(), (note or "").strip() or None),
                )
            except sqlite3.IntegrityError:
                raise CoreError(f"{validated_by} has already validated finding {finding_id}") from None
            self._log(conn, finding_id, "validated", validated_by, note=note)
            if row["status"] == "proposed":
                conn.execute("UPDATE findings SET status = 'validated' WHERE id = ?", (finding_id,))
                self._log(
                    conn, finding_id, "status_changed", validated_by,
                    **{"from": "proposed", "to": "validated"},
                )
            elif row["status"] == "contested":
                warnings.append("finding is contested; validation recorded but status stays contested")
        return {"finding": self.get(finding_id), "warnings": warnings}

    def check_conflict(
        self, statement: str | None = None, finding_id: int | None = None
    ) -> dict[str, Any]:
        """Find validated (or already contested) findings on a similar topic that
        may contradict this one. Contested findings are included so a third
        contradicting finding still surfaces.

        Pass either a statement (to check before proposing) or the id of an
        existing finding. Returns candidates for a human to review; nothing is
        changed. Use confirm_conflict to flag a real conflict.
        """
        if finding_id is not None:
            base = self.get(finding_id)
            statement = base["statement"]
        statement = self._require_name(statement, "statement")
        candidates = []
        existing = self.list_findings(status="validated", limit=10_000)
        existing += self.list_findings(status="contested", limit=10_000)
        for f in existing:
            if f["id"] == finding_id:
                continue
            score, shared = similarity(statement, f["statement"])
            if score < SIMILARITY_THRESHOLD or len(shared) < MIN_SHARED_WORDS:
                continue
            signals = contradiction_signals(statement, f["statement"])
            candidates.append(
                {
                    "finding": f,
                    "similarity": round(score, 2),
                    "shared_words": sorted(shared),
                    "signals": signals,
                    "likely_conflict": bool(signals),
                }
            )
        candidates.sort(key=lambda c: (not c["likely_conflict"], -c["similarity"]))
        return {"statement": statement, "finding_id": finding_id, "candidates": candidates}

    def confirm_conflict(
        self, finding_id: int, conflicting_id: int, confirmed_by: str, note: str | None = None
    ) -> dict[str, Any]:
        """A person confirms two findings contradict. Both become 'contested'.

        Their previous statuses and validations are kept in the record.
        """
        if finding_id == conflicting_id:
            raise CoreError("a finding cannot conflict with itself")
        with self._conn() as conn:
            confirmed_by = self._person(conn, confirmed_by, "confirmed_by")
            rows = [self._row(conn, finding_id), self._row(conn, conflicting_id)]
            exists = conn.execute(
                "SELECT 1 FROM conflicts WHERE (finding_id = ? AND conflicting_id = ?) "
                "OR (finding_id = ? AND conflicting_id = ?)",
                (finding_id, conflicting_id, conflicting_id, finding_id),
            ).fetchone()
            if exists:
                raise CoreError(f"findings {finding_id} and {conflicting_id} are already flagged")
            conn.execute(
                "INSERT INTO conflicts (finding_id, conflicting_id, flagged_by, flagged_at, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (finding_id, conflicting_id, confirmed_by, _now(), (note or "").strip() or None),
            )
            for row, other in ((rows[0], conflicting_id), (rows[1], finding_id)):
                self._log(
                    conn, row["id"], "contested", confirmed_by,
                    conflicts_with=other, previous_status=row["status"], note=note,
                )
                if row["status"] != "contested":
                    conn.execute("UPDATE findings SET status = 'contested' WHERE id = ?", (row["id"],))
        return {"findings": [self.get(finding_id), self.get(conflicting_id)]}

    def checkout(self, finding_id: int, who: str) -> dict[str, Any]:
        """Mark a finding as being worked on. Advisory: never refuses."""
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            who = self._person(conn, who, "who")
            warnings = self._checkout_warning(row, who)
            conn.execute(
                "UPDATE findings SET checked_out_by = ?, checked_out_at = ? WHERE id = ?",
                (who, _now(), finding_id),
            )
            self._log(conn, finding_id, "checked_out", who, previous_holder=row["checked_out_by"])
        return {"finding": self.get(finding_id), "warnings": warnings}

    def release(self, finding_id: int, who: str) -> dict[str, Any]:
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            who = self._person(conn, who, "who")
            warnings = []
            if not row["checked_out_by"]:
                warnings.append(f"finding {finding_id} was not checked out")
            else:
                warnings = self._checkout_warning(row, who)
            conn.execute(
                "UPDATE findings SET checked_out_by = NULL, checked_out_at = NULL WHERE id = ?",
                (finding_id,),
            )
            self._log(conn, finding_id, "released", who, previous_holder=row["checked_out_by"])
        return {"finding": self.get(finding_id), "warnings": warnings}
