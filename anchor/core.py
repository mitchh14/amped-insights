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
# How one finding relates to another. "supports" is stored as an evidence
# link and "contradicts" as a confirmed conflict, so each fact lives in one place.
LINK_TYPES = ("supports", "extends", "duplicates", "contradicts")
# A review's outcome. Only approve counts toward a finding being validated.
OUTCOMES = ("approve", "changes_requested", "disagree")
OUTCOME_EVENT = {"approve": "validated", "changes_requested": "changes_requested", "disagree": "disagreed"}
REQUEST_STATUSES = ("open", "done", "withdrawn")

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

-- One row per review. Never collapsed into a single flag. A person can
-- review again (for example approve after asking for changes); their latest
-- review is the one that counts, and earlier ones stay visible.
CREATE TABLE IF NOT EXISTS validations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    INTEGER NOT NULL REFERENCES findings(id),
    validated_by  TEXT NOT NULL,
    validated_at  TEXT NOT NULL,
    note          TEXT,
    outcome       TEXT NOT NULL DEFAULT 'approve' CHECK (outcome IN {OUTCOMES}),
    basis         TEXT,  -- how the reviewer checked (a key from the team's checks)
    role          TEXT   -- the reviewer's role when they reviewed
);

-- A request for someone, or anyone in a role, to review a finding.
-- Closed by any review from that person or role. Nobody needs to be asked.
CREATE TABLE IF NOT EXISTS validation_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    INTEGER NOT NULL REFERENCES findings(id),
    requested_by  TEXT NOT NULL,
    person        TEXT,  -- one of person or role is set
    role          TEXT,
    note          TEXT,
    at            TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN {REQUEST_STATUSES}),
    closed_by     TEXT,
    closed_at     TEXT,
    outcome       TEXT
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

-- Other ways two findings relate. A extends B: A builds on B.
-- Duplicates reads the same from both sides.
CREATE TABLE IF NOT EXISTS links (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id  INTEGER NOT NULL REFERENCES findings(id),
    to_id    INTEGER NOT NULL REFERENCES findings(id),
    type     TEXT NOT NULL CHECK (type IN ('extends', 'duplicates')),
    by       TEXT NOT NULL,
    at       TEXT NOT NULL,
    note     TEXT,
    UNIQUE (from_id, to_id, type)
);

-- A decision someone made, and the findings they used to make it.
-- This is how research shows its value, and how a decision owner learns when
-- something they relied on is later contested.
CREATE TABLE IF NOT EXISTS decisions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    title     TEXT NOT NULL,
    made_by   TEXT NOT NULL,
    at        TEXT NOT NULL,
    note      TEXT,
    outcome   TEXT  -- what happened, added whenever it is known
);

CREATE TABLE IF NOT EXISTS decision_uses (
    decision_id    INTEGER NOT NULL REFERENCES decisions(id),
    finding_id     INTEGER NOT NULL REFERENCES findings(id),
    status_at_use  TEXT NOT NULL,
    PRIMARY KEY (decision_id, finding_id)
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
    ("findings", "promoted_from", "INTEGER REFERENCES findings(id)"),
    ("events", "decision_id", "INTEGER"),
    ("findings", "revises", "INTEGER REFERENCES findings(id)"),
)

# Promotion moves up one tier and creates a new finding at that tier.
NEXT_TIER = {"data_point": "hypothesis", "hypothesis": "insight"}


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
            self._rebuild_old_validations(conn)
            conn.executescript(SCHEMA)
            for table, column, decl in MIGRATIONS:
                have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            self._sync_people(conn)

    @staticmethod
    def _rebuild_old_validations(conn) -> None:
        """The first release allowed one validation per person. Lift that in place."""
        have = {r["name"] for r in conn.execute("PRAGMA table_info(validations)")}
        if not have or "outcome" in have:
            return
        conn.execute("ALTER TABLE validations RENAME TO validations_v1")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO validations (id, finding_id, validated_by, validated_at, note) "
            "SELECT id, finding_id, validated_by, validated_at, note FROM validations_v1"
        )
        conn.execute("DROP TABLE validations_v1")

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
    def _log(conn, finding_id, kind, actor, _study=None, _decision=None, **detail) -> None:
        conn.execute(
            "INSERT INTO events (finding_id, study_id, decision_id, kind, actor, at, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (finding_id, _study, _decision, kind, actor, _now(), json.dumps(detail)),
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
        current = {r["id"] for r in self._current_reviews(conn, fid)}
        validations = []
        for r in conn.execute(
            # Reviews from before roles were recorded show the reviewer's role today.
            "SELECT v.id, v.validated_by, COALESCE(v.role, p.role) AS role, v.outcome, v.basis, "
            "v.validated_at, v.note FROM validations v LEFT JOIN people p ON p.name = v.validated_by "
            "WHERE v.finding_id = ? ORDER BY v.id",
            (fid,),
        ):
            v = dict(r)
            v["role_label"] = self._role_label(v["role"])
            v["trusted"] = self._trusted(v["role"])
            v["current"] = v["id"] in current
            validations.append(v)
        # Current reviews first, trusted roles first within them, then oldest first.
        validations.sort(key=lambda v: (not v["current"], not v["trusted"], v["id"]))
        requests = [
            dict(r)
            for r in conn.execute(
                "SELECT id, requested_by, person, role, note, at FROM validation_requests "
                "WHERE finding_id = ? AND status = 'open' ORDER BY id",
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
        prow = conn.execute("SELECT * FROM findings WHERE id = ?", (row["promoted_from"],)).fetchone()
        promoted_to = [
            self._summary(r)
            for r in conn.execute("SELECT * FROM findings WHERE promoted_from = ? ORDER BY id", (fid,))
        ]
        rrow = conn.execute("SELECT * FROM findings WHERE id = ?", (row["revises"],)).fetchone()
        revised_as = [
            self._summary(r)
            for r in conn.execute("SELECT * FROM findings WHERE revises = ? ORDER BY id", (fid,))
        ]
        links = {"extends": [], "extended_by": [], "duplicates": []}
        for l in conn.execute(
            "SELECT * FROM links WHERE from_id = ? OR to_id = ? ORDER BY id", (fid, fid)
        ):
            outgoing = l["from_id"] == fid
            other = self._row(conn, l["to_id"] if outgoing else l["from_id"])
            group = l["type"] if outgoing or l["type"] == "duplicates" else "extended_by"
            links[group].append(
                {"finding": self._summary(other), "by": l["by"], "at": l["at"], "note": l["note"]}
            )
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
            "links": links,
            "promoted_from": self._summary(prow) if prow else None,
            "promoted_to": promoted_to,
            "revises": self._summary(rrow) if rrow else None,
            "revised_as": revised_as,
            "promotion": self._readiness(conn, row) if row["tier"] in NEXT_TIER else None,
            "trust": self._trust([v for v in validations if v["current"]]),
            "validations": validations,
            "open_requests": requests,
            "used_in": [
                dict(d) for d in conn.execute(
                    "SELECT d.id, d.title, d.made_by, d.at FROM decisions d "
                    "JOIN decision_uses u ON u.decision_id = d.id WHERE u.finding_id = ? ORDER BY d.id",
                    (fid,),
                )
            ],
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
        drow = conn.execute("SELECT * FROM decisions WHERE id = ?", (row["from_decision_id"],)).fetchone()
        study["from_decision"] = {k: drow[k] for k in ("id", "title", "made_by", "at")} if drow else None
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
                "SELECT e.*, f.statement, s.title AS study_title, d.title AS decision_title FROM events e "
                "LEFT JOIN findings f ON f.id = e.finding_id LEFT JOIN studies s ON s.id = e.study_id "
                "LEFT JOIN decisions d ON d.id = e.decision_id ORDER BY e.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "finding_id": r["finding_id"],
                "statement": r["statement"],
                "study_id": r["study_id"],
                "study_title": r["study_title"],
                "decision_id": r["decision_id"],
                "decision_title": r["decision_title"],
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

    def request_research(
        self,
        question: str,
        requested_by: str,
        decision: str | None = None,
        from_decision_id: int | None = None,
        from_query: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask a research question. It lands as a study with status 'requested'
        for the research team to pick up (update_study to planned, with an owner)
        or close.

        Link it to where it came from: a decision whose outcome raised the
        question (from_decision_id), or a search that found nothing trusted
        (from_query). fields holds any intake fields the team added to its study
        template, such as a link to its own tracker.
        """
        question = self._require_name(question, "question")
        with self._conn() as conn:
            requested_by = self._person(conn, requested_by, "requested_by")
            if from_decision_id is not None:
                drow = self._decision_row(conn, int(from_decision_id))
                from_decision_id = drow["id"]
                decision = _clean(decision) or drow["title"]
            cur = conn.execute(
                "INSERT INTO studies (title, decision, status, fields, requested_by, from_decision_id, "
                "from_query, created_at) VALUES (?, ?, 'requested', ?, ?, ?, ?, ?)",
                (question, _clean(decision), json.dumps(_clean_fields(fields)), requested_by,
                 from_decision_id, _clean(from_query), _now()),
            )
            sid = cur.lastrowid
            self._log(conn, None, "research_requested", requested_by, sid, from_decision_id,
                      from_query=_clean(from_query))
        study = self.get_study(sid)
        warnings = [] if study["decision"] else ["say which decision this would inform, so it can be prioritized"]
        return {"study": study, "warnings": warnings}

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
            fid = self._insert_finding(conn, statement, tier, owner, links, study_id)
        if tier != "data_point" and not links:
            warnings.append(f"this {tier} has no evidence links yet")
        return self._created(fid, warnings)

    def _insert_finding(
        self, conn, statement, tier, owner, links, study_id, promoted_from=None, revises=None
    ) -> int:
        for eid in links:
            self._row(conn, eid)
        if study_id is not None:
            study_id = self._study_row(conn, int(study_id))["id"]
        cur = conn.execute(
            "INSERT INTO findings (statement, tier, status, owner, evidence_links, study_id, "
            "promoted_from, revises, created_at) VALUES (?, ?, 'proposed', ?, ?, ?, ?, ?, ?)",
            (statement, tier, owner, json.dumps(links), study_id, promoted_from, revises, _now()),
        )
        fid = cur.lastrowid
        detail = {"tier": tier, "evidence_links": links}
        if promoted_from:
            detail["promoted_from"] = promoted_from
        if revises:
            detail["revises"] = revises
        self._log(conn, fid, "proposed", owner, study_id, **detail)
        return fid

    def _created(self, fid: int, warnings: list[str]) -> dict[str, Any]:
        """A new finding plus a conflict check, so contradictions surface on entry."""
        conflicts = self.check_conflict(finding_id=fid)["candidates"]
        return {"finding": self.get(fid), "possible_conflicts": conflicts, "warnings": warnings}

    def promote(
        self, finding_id: int, by: str, statement: str | None = None, note: str | None = None
    ) -> dict[str, Any]:
        """Promote a data point to a hypothesis, or a hypothesis to an insight.

        Promotion creates a new finding one tier up, linked back to the one it
        came from, which stays exactly as it was with its own validations. The
        new finding starts as proposed, owned by whoever promoted it, and can
        be reworded (statement) to say what the evidence now supports.

        Anyone can promote. The team's promotion rules show whether the source
        is ready; they only stop a promotion if the team set enforce = "required".
        """
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            by = self._person(conn, by, "by")
            if row["tier"] not in NEXT_TIER:
                raise CoreError(f"finding {finding_id} is already an {row['tier']}; it cannot be promoted further")
            to_tier = NEXT_TIER[row["tier"]]
            readiness = self._readiness(conn, row, promoter=by)
            if not readiness["ready"] and self.config["promote"]["enforce"] == "required":
                raise CoreError(f"not ready to promote: {readiness['summary']}")
            warnings = []
            if not readiness["ready"]:
                warnings.append(f"not ready by the team's rule ({readiness['summary']}); promoted anyway")
            if row["status"] == "proposed":
                warnings.append(f"finding {finding_id} has not been validated yet")
            if row["status"] == "contested":
                warnings.append(f"finding {finding_id} is contested; its conflict is not resolved")
            if row["tier"] != "data_point" and not json.loads(row["evidence_links"]):
                warnings.append(f"finding {finding_id} has no evidence links, so this {to_tier} rests on it alone")
            new_statement = (statement or "").strip() or row["statement"]
            fid = self._insert_finding(
                conn, new_statement, to_tier, by, [finding_id], row["study_id"], promoted_from=finding_id
            )
            self._log(conn, finding_id, "promoted", by, row["study_id"],
                      to=fid, from_tier=row["tier"], to_tier=to_tier, note=_clean(note))
        return self._created(fid, warnings)

    def revise(self, finding_id: int, by: str, statement: str, note: str | None = None) -> dict[str, Any]:
        """Respond to review feedback with a new version of a finding.

        The new version keeps the tier, evidence, and study, and links back to
        the one it revises, which stays as it was with its reviews. Everyone
        whose current review asked for changes gets a request to look again.
        """
        statement = self._require_name(statement, "statement")
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            by = self._person(conn, by, "by")
            if statement == row["statement"]:
                raise CoreError("the new version says the same thing; change the statement to revise")
            warnings = []
            if by != row["owner"]:
                warnings.append(f"finding {finding_id} is owned by {row['owner']}; you own the new version")
            fid = self._insert_finding(
                conn, statement, row["tier"], by, json.loads(row["evidence_links"]), row["study_id"],
                promoted_from=row["promoted_from"], revises=finding_id,
            )
            self._log(conn, finding_id, "revised", by, row["study_id"], to=fid, note=_clean(note))
            asked = [
                r["validated_by"] for r in self._current_reviews(conn, finding_id)
                if r["outcome"] == "changes_requested" and r["validated_by"] != by
            ]
            for name in asked:
                cur = conn.execute(
                    "INSERT INTO validation_requests (finding_id, requested_by, person, note, at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (fid, by, name, f"Revised after your review of #{finding_id}", _now()),
                )
                self._log(conn, fid, "review_requested", by, person=name, request_id=cur.lastrowid)
            # Requests still open on the old version move to the new one.
            conn.execute(
                "UPDATE validation_requests SET status = 'withdrawn', closed_by = ?, closed_at = ? "
                "WHERE finding_id = ? AND status = 'open'",
                (by, _now(), finding_id),
            )
        result = self._created(fid, warnings)
        result["review_requested_from"] = asked
        return result

    @staticmethod
    def _current_reviews(conn, finding_id: int) -> list[sqlite3.Row]:
        """Each reviewer's latest review of a finding. Earlier ones are history."""
        return conn.execute(
            "SELECT * FROM validations v WHERE finding_id = ? AND id = "
            "(SELECT MAX(id) FROM validations w WHERE w.finding_id = v.finding_id "
            "AND w.validated_by = v.validated_by) ORDER BY id",
            (finding_id,),
        ).fetchall()

    def _approvals(self, conn, finding_id: int) -> list[sqlite3.Row]:
        """Reviews that currently count as approval."""
        return [r for r in self._current_reviews(conn, finding_id) if r["outcome"] == "approve"]

    def _trusted(self, role: str | None) -> bool:
        return bool(role and self.config["roles"].get(role, {}).get("trusted"))

    def _role_label(self, role: str | None) -> str | None:
        return self.config["roles"].get(role, {}).get("label", role) if role else None

    def _trust(self, current: list[dict[str, Any]]) -> dict[str, Any]:
        """How much to lean on a finding, from who reviewed it, in what role, and how.

        Trusted roles are counted by role. Everyone else counts as a peer.
        The summary is plain text so the app and AI tools say the same thing.
        """
        approvals = [v for v in current if v["outcome"] == "approve"]
        by_role: dict[str, int] = {}
        for v in approvals:
            key = v["role"] if v["trusted"] else "peer"
            by_role[key] = by_role.get(key, 0) + 1
        checked: dict[str, int] = {}
        for v in approvals:
            if v["basis"]:
                checked[v["basis"]] = checked.get(v["basis"], 0) + 1
        changes = sum(v["outcome"] == "changes_requested" for v in current)
        disagree = sum(v["outcome"] == "disagree" for v in current)

        order = [r for r in self.config["roles"] if self._trusted(r)] + ["peer"]
        who = ", ".join(
            f"{by_role[r]} {'peer' if r == 'peer' else self._role_label(r).lower()}"
            for r in order if by_role.get(r)
        )
        parts = [f"Validated by {who}." if who else "Not validated yet."]
        if checked:
            labels = self.config["checks"]
            parts.append("How they checked: " + ", ".join(
                f"{labels.get(k, k).lower()} ({n})" for k, n in checked.items()) + ".")
        if changes:
            parts.append(f"{changes} {'asks' if changes == 1 else 'ask'} for changes.")
        if disagree:
            parts.append(f"{disagree} {'disagrees' if disagree == 1 else 'disagree'}.")
        return {
            "approvals": len(approvals),
            "trusted": sum(n for r, n in by_role.items() if r != "peer"),
            "peer": by_role.get("peer", 0),
            "by_role": by_role,
            "checked": checked,
            "changes_requested": changes,
            "disagree": disagree,
            "summary": " ".join(parts),
        }

    def _readiness(self, conn, row: sqlite3.Row, promoter: str | None = None) -> dict[str, Any]:
        """Whether a finding meets the team's promotion rule. Any one rule is enough."""
        rules = self.config["promote"]
        approvals = self._approvals(conn, row["id"])
        trusted = sum(self._trusted(a["role"]) for a in approvals)
        checks = []
        if rules["min_validations"]:
            checks.append((len(approvals) >= rules["min_validations"],
                           f"{len(approvals)} of {rules['min_validations']} validations"))
        if rules["min_trusted_validations"]:
            checks.append((trusted >= rules["min_trusted_validations"],
                           f"{trusted} of {rules['min_trusted_validations']} trusted validations"))
        if rules["trusted_roles_ready"] and promoter is not None:
            checks.append((self._trusted(self._role_of(conn, promoter)), f"{promoter} has a trusted role"))
        if not checks:
            return {"ready": True, "summary": "no promotion rule set", "enforced": False}
        ready = any(ok for ok, _ in checks)
        return {
            "ready": ready,
            "summary": ", or ".join(text for _, text in checks),
            "enforced": rules["enforce"] == "required",
        }

    def validate(
        self,
        finding_id: int,
        validated_by: str,
        note: str | None = None,
        outcome: str = "approve",
        basis: str | None = None,
    ) -> dict[str, Any]:
        """Review a finding: approve it, request changes, or disagree.

        Each review stays visible individually, with the reviewer's role. A
        person can review again; their latest review is the one that counts.
        A finding is validated while at least one current review approves it.
        Requesting changes or disagreeing never contests a finding on its own;
        a conflict is confirmed separately.

        Any open review request for this person, or for their role, closes.
        """
        if outcome not in OUTCOMES:
            raise CoreError(f"outcome must be one of {OUTCOMES}")
        if basis is not None and basis not in self.config["checks"]:
            raise CoreError(f"basis must be one of {tuple(self.config['checks'])}")
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            validated_by = self._person(conn, validated_by, "validated_by")
            if row["owner"] == validated_by:
                raise CoreError("a finding cannot be validated by its own owner")
            warnings = self._checkout_warning(row, validated_by)
            last = conn.execute(
                "SELECT outcome FROM validations WHERE finding_id = ? AND validated_by = ? "
                "ORDER BY id DESC LIMIT 1",
                (finding_id, validated_by),
            ).fetchone()
            if last and last["outcome"] == outcome:
                said = "validated" if outcome == "approve" else f"given '{outcome}' on"
                raise CoreError(f"{validated_by} has already {said} finding {finding_id}")
            role = self._role_of(conn, validated_by)
            conn.execute(
                "INSERT INTO validations (finding_id, validated_by, validated_at, note, outcome, basis, role) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (finding_id, validated_by, _now(), _clean(note), outcome, basis, role),
            )
            self._log(conn, finding_id, OUTCOME_EVENT[outcome], validated_by,
                      note=_clean(note), outcome=outcome, basis=basis, role=role)
            conn.execute(
                "UPDATE validation_requests SET status = 'done', closed_by = ?, closed_at = ?, outcome = ? "
                "WHERE finding_id = ? AND status = 'open' AND (person = ? OR role = ?)",
                (validated_by, _now(), outcome, finding_id, validated_by, role),
            )
            if row["status"] == "contested":
                warnings.append("finding is contested; review recorded but status stays contested")
            else:
                status = "validated" if self._approvals(conn, finding_id) else "proposed"
                if status != row["status"]:
                    conn.execute("UPDATE findings SET status = ? WHERE id = ?", (status, finding_id))
                    self._log(conn, finding_id, "status_changed", validated_by,
                              **{"from": row["status"], "to": status})
        return {"finding": self.get(finding_id), "warnings": warnings}

    def request_validation(
        self,
        finding_id: int,
        requested_by: str,
        people: list[str] | None = None,
        roles: list[str] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Ask named people, or anyone in a role (for example any researcher), to
        review a finding. It shows up in their queue until they review it.
        Anyone can still review without being asked."""
        people = [p for p in (people or []) if (p or "").strip()]
        roles = list(roles or [])
        if not people and not roles:
            raise CoreError("name at least one person or role to ask")
        for role in roles:
            if role not in self.config["roles"]:
                raise CoreError(f"role must be one of {tuple(self.config['roles'])}")
        warnings, made = [], []
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            requested_by = self._person(conn, requested_by, "requested_by")
            targets = [("person", self._person(conn, p, "people")) for p in people]
            targets += [("role", r) for r in roles]
            for kind, who in targets:
                if kind == "person" and who == row["owner"]:
                    warnings.append(f"{who} owns this finding, so they cannot review it; skipped")
                    continue
                if conn.execute(
                    f"SELECT 1 FROM validation_requests WHERE finding_id = ? AND status = 'open' AND {kind} = ?",
                    (finding_id, who),
                ).fetchone():
                    warnings.append(f"{who} already has an open request for this finding; skipped")
                    continue
                cur = conn.execute(
                    f"INSERT INTO validation_requests (finding_id, requested_by, {kind}, note, at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (finding_id, requested_by, who, _clean(note), _now()),
                )
                made.append(cur.lastrowid)
                self._log(conn, finding_id, "review_requested", requested_by,
                          **{kind: who}, request_id=cur.lastrowid, note=_clean(note))
        return {"finding": self.get(finding_id), "request_ids": made, "warnings": warnings}

    def withdraw_request(self, request_id: int, by: str) -> dict[str, Any]:
        """Withdraw an open review request, for example when it is no longer needed."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            req = conn.execute("SELECT * FROM validation_requests WHERE id = ?", (request_id,)).fetchone()
            if req is None:
                raise CoreError(f"request {request_id} does not exist")
            if req["status"] != "open":
                raise CoreError(f"request {request_id} is already {req['status']}")
            conn.execute(
                "UPDATE validation_requests SET status = 'withdrawn', closed_by = ?, closed_at = ? WHERE id = ?",
                (by, _now(), request_id),
            )
            self._log(conn, req["finding_id"], "request_withdrawn", by, request_id=request_id)
        return {"finding": self.get(req["finding_id"]), "warnings": []}

    def my_queue(self, who: str) -> dict[str, Any]:
        """What is waiting on a person.

        waiting_on_me: findings someone asked this person (or their role) to review.
        feedback_on_mine: their own findings where a current review asks for
        changes or disagrees.
        my_requests: review requests they made that are still open.
        """
        with self._conn() as conn:
            who = self._person(conn, who, "who")
            role = self._role_of(conn, who)
            waiting = []
            for req in conn.execute(
                "SELECT r.*, f.owner FROM validation_requests r JOIN findings f ON f.id = r.finding_id "
                "WHERE r.status = 'open' AND (r.person = ? OR r.role = ?) AND f.owner != ? ORDER BY r.id",
                (who, role, who),
            ):
                mine = [r for r in self._current_reviews(conn, req["finding_id"]) if r["validated_by"] == who]
                if mine and mine[0]["outcome"] == "approve":
                    continue  # already approved before the request came in
                waiting.append({"request": self._request(req), "finding": self._full(conn, self._row(conn, req["finding_id"]))})
            feedback = []
            for row in conn.execute(
                "SELECT * FROM findings f WHERE owner = ? AND NOT EXISTS "
                "(SELECT 1 FROM findings r WHERE r.revises = f.id) ORDER BY id DESC",
                (who,),
            ):
                concerns = [dict(r) for r in self._current_reviews(conn, row["id"]) if r["outcome"] != "approve"]
                if concerns:
                    feedback.append({"finding": self._full(conn, row), "reviews": concerns})
            mine = [
                {"request": self._request(r), "finding": self._summary(self._row(conn, r["finding_id"]))}
                for r in conn.execute(
                    "SELECT * FROM validation_requests WHERE requested_by = ? AND status = 'open' ORDER BY id",
                    (who,),
                )
            ]
            at_risk = [
                d for d in (
                    self._decision_full(conn, r, with_credits=False)
                    for r in conn.execute("SELECT * FROM decisions WHERE made_by = ? ORDER BY id DESC", (who,))
                ) if d["at_risk"]
            ]
        return {"who": who, "role": role, "waiting_on_me": waiting, "feedback_on_mine": feedback,
                "my_requests": mine, "decisions_at_risk": at_risk}

    @staticmethod
    def _request(r: sqlite3.Row) -> dict[str, Any]:
        return {k: r[k] for k in ("id", "finding_id", "requested_by", "person", "role", "note", "at", "status")}

    # -- decisions ---------------------------------------------------------

    def log_decision(
        self,
        title: str,
        made_by: str,
        finding_ids: list[int] | None = None,
        note: str | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        """Record a decision and the findings used to make it, in one step.

        Using a finding that is not validated yet, or is contested, is allowed
        and comes back as a warning, so the record stays honest about what the
        decision rested on.
        """
        title = self._require_name(title, "title")
        ids = list(dict.fromkeys(int(x) for x in (finding_ids or [])))
        with self._conn() as conn:
            made_by = self._person(conn, made_by, "made_by")
            rows = [self._row(conn, fid) for fid in ids]
            cur = conn.execute(
                "INSERT INTO decisions (title, made_by, at, note, outcome) VALUES (?, ?, ?, ?, ?)",
                (title, made_by, _now(), _clean(note), _clean(outcome)),
            )
            did = cur.lastrowid
            self._log(conn, None, "decision_logged", made_by, None, did, finding_ids=ids)
            warnings = self._use(conn, did, rows, made_by)
        if not ids:
            warnings.append("no findings linked; if nothing trusted exists yet, ask for research")
        return {"decision": self.get_decision(did), "warnings": warnings}

    def _use(self, conn, decision_id: int, rows: list[sqlite3.Row], by: str) -> list[str]:
        warnings = []
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO decision_uses (decision_id, finding_id, status_at_use) VALUES (?, ?, ?)",
                (decision_id, row["id"], row["status"]),
            )
            self._log(conn, row["id"], "used_in_decision", by, None, decision_id)
            if row["status"] == "proposed":
                warnings.append(f"finding {row['id']} has not been validated yet")
            elif row["status"] == "contested":
                warnings.append(f"finding {row['id']} is contested")
        return warnings

    def update_decision(
        self,
        decision_id: int,
        by: str,
        outcome: str | None = None,
        note: str | None = None,
        add_finding_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Add what happened (outcome), a note, or more findings that were used."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            row = self._decision_row(conn, decision_id)
            changes = {}
            for key, value in (("outcome", outcome), ("note", note)):
                if value is not None and _clean(value) != row[key]:
                    changes[key] = _clean(value)
            if changes:
                conn.execute(
                    f"UPDATE decisions SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                    (*changes.values(), decision_id),
                )
                self._log(conn, None, "decision_updated", by, None, decision_id,
                          changed=sorted(changes), previous={k: row[k] for k in changes})
            rows = [self._row(conn, int(fid)) for fid in (add_finding_ids or [])]
            warnings = self._use(conn, decision_id, rows, by)
        return {"decision": self.get_decision(decision_id), "warnings": warnings}

    @staticmethod
    def _decision_row(conn, decision_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            raise CoreError(f"decision {decision_id} does not exist")
        return row

    def _decision_full(self, conn, row: sqlite3.Row, with_credits: bool = True) -> dict[str, Any]:
        decision = dict(row)
        used = []
        for u in conn.execute(
            "SELECT * FROM decision_uses WHERE decision_id = ? ORDER BY finding_id", (row["id"],)
        ):
            f = self._full(conn, self._row(conn, u["finding_id"]))
            used.append({
                **{k: f[k] for k in ("id", "statement", "tier", "status", "owner")},
                "status_at_use": u["status_at_use"],
                "trust": f["trust"]["summary"],
            })
        decision["findings"] = used
        # A decision is at risk when something it relied on is now contested.
        decision["at_risk"] = [f["id"] for f in used if f["status"] == "contested"]
        decision["requests"] = [
            self._study_summary(r)
            for r in conn.execute("SELECT * FROM studies WHERE from_decision_id = ? ORDER BY id", (row["id"],))
        ]
        if with_credits:
            decision["credits"] = self._credits(conn, [f["id"] for f in used])
        return decision

    def _credits(self, conn, finding_ids: list[int]) -> list[dict[str, Any]]:
        """Everyone in the chain behind these findings, and what they did.

        Walks each finding's evidence and promotion history back to the start.
        Listed by name, not ranked: this is about seeing the collaboration
        behind a decision, not scoring it.
        """
        seen: set[int] = set()
        credit: dict[str, list[dict[str, Any]]] = {}

        def add(name, what, **ref):
            items = credit.setdefault(name, [])
            item = {"did": what, **ref}
            if item not in items:
                items.append(item)

        stack = list(finding_ids)
        while stack:
            fid = stack.pop()
            if fid in seen:
                continue
            seen.add(fid)
            row = self._row(conn, fid)
            add(row["owner"], "proposed", finding_id=fid)
            for v in self._approvals(conn, fid):
                add(v["validated_by"], "validated", finding_id=fid)
            if row["study_id"]:
                study = self._study_row(conn, row["study_id"])
                if study["owner"]:
                    add(study["owner"], "ran study", study_id=study["id"])
            stack.extend(json.loads(row["evidence_links"]))
            if row["promoted_from"]:
                stack.append(row["promoted_from"])
        out = []
        for name in sorted(credit, key=str.lower):
            role = self._role_of(conn, name)
            out.append({**self._person_dict(name, role), "contributions": credit[name]})
        return out

    def get_decision(self, decision_id: int) -> dict[str, Any]:
        """A decision, the findings it used (with their trust now and when used),
        what is at risk, research asked for from it, and everyone behind it."""
        with self._conn() as conn:
            return self._decision_full(conn, self._decision_row(conn, decision_id))

    def list_decisions(self, made_by: str | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM decisions", []
        if made_by:
            sql += " WHERE made_by = ? COLLATE NOCASE"
            args.append(made_by.strip())
        with self._conn() as conn:
            rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
            return [self._decision_full(conn, r, with_credits=False) for r in rows]

    def person(self, name: str) -> dict[str, Any]:
        """A person's role, the decisions they made, and the decisions their work
        contributed to (through any finding in the chain behind them)."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM people WHERE name = ?", ((name or "").strip(),)).fetchone()
            if row is None:
                raise CoreError(f"{name} has not taken part yet")
            contributed = []
            for d in conn.execute("SELECT * FROM decisions ORDER BY id DESC").fetchall():
                ids = [u["finding_id"] for u in conn.execute(
                    "SELECT finding_id FROM decision_uses WHERE decision_id = ?", (d["id"],))]
                mine = [c for c in self._credits(conn, ids) if c["name"] == row["name"]]
                if mine:
                    contributed.append({"id": d["id"], "title": d["title"], "made_by": d["made_by"],
                                        "at": d["at"], "contributions": mine[0]["contributions"]})
            made = [dict(d) for d in conn.execute(
                "SELECT id, title, at, outcome FROM decisions WHERE made_by = ? ORDER BY id DESC", (row["name"],))]
        return {**self._person_dict(row["name"], row["role"]), "decisions_made": made,
                "contributed_to": contributed}

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
                # Tell anyone who made a decision with it.
                for u in conn.execute(
                    "SELECT decision_id FROM decision_uses WHERE finding_id = ?", (row["id"],)
                ).fetchall():
                    self._log(conn, row["id"], "decision_at_risk", confirmed_by, None, u["decision_id"])
        return {"findings": [self.get(finding_id), self.get(conflicting_id)]}

    def link(
        self, from_id: int, to_id: int, type: str, by: str, note: str | None = None
    ) -> dict[str, Any]:
        """Say how one finding relates to another.

        supports: from_id is evidence for to_id (added to to_id's evidence links).
        extends: from_id builds on to_id.
        duplicates: the two say the same thing.
        contradicts: a confirmed conflict; both become contested (see confirm_conflict).
        """
        if type not in LINK_TYPES:
            raise CoreError(f"type must be one of {LINK_TYPES}")
        from_id, to_id = int(from_id), int(to_id)
        if from_id == to_id:
            raise CoreError("a finding cannot be linked to itself")
        if type == "contradicts":
            return self.confirm_conflict(from_id, to_id, by, note)
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            self._row(conn, from_id)
            target = self._row(conn, to_id)
            if type == "supports":
                evidence = json.loads(target["evidence_links"])
                if from_id in evidence:
                    raise CoreError(f"finding {from_id} already supports {to_id}")
                conn.execute(
                    "UPDATE findings SET evidence_links = ? WHERE id = ?",
                    (json.dumps(sorted(evidence + [from_id])), to_id),
                )
            else:
                exists = conn.execute(
                    "SELECT 1 FROM links WHERE type = ? AND ((from_id = ? AND to_id = ?) "
                    "OR (type = 'duplicates' AND from_id = ? AND to_id = ?))",
                    (type, from_id, to_id, to_id, from_id),
                ).fetchone()
                if exists:
                    raise CoreError(f"findings {from_id} and {to_id} are already linked as {type}")
                conn.execute(
                    "INSERT INTO links (from_id, to_id, type, by, at, note) VALUES (?, ?, ?, ?, ?, ?)",
                    (from_id, to_id, type, by, _now(), _clean(note)),
                )
            for fid in (from_id, to_id):
                self._log(conn, fid, "linked", by, type=type, source=from_id, target=to_id, note=_clean(note))
        return {"findings": [self.get(from_id), self.get(to_id)]}

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
