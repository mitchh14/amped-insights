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


class CoreError(ValueError):
    """Raised when an action is not allowed or the input is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    def _log(conn, finding_id, kind, actor, **detail) -> None:
        conn.execute(
            "INSERT INTO events (finding_id, kind, actor, at, detail) VALUES (?, ?, ?, ?, ?)",
            (finding_id, kind, actor, _now(), json.dumps(detail)),
        )

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
                "SELECT validated_by, validated_at, note FROM validations "
                "WHERE finding_id = ? ORDER BY validated_at, id",
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
        return {
            "id": fid,
            "statement": row["statement"],
            "tier": row["tier"],
            "status": row["status"],
            "owner": row["owner"],
            "created_at": row["created_at"],
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
                "SELECT e.*, f.statement FROM events e LEFT JOIN findings f ON f.id = e.finding_id "
                "ORDER BY e.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "finding_id": r["finding_id"],
                "statement": r["statement"],
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

    def propose(
        self,
        statement: str,
        tier: str,
        owner: str,
        evidence_links: list[int] | None = None,
    ) -> dict[str, Any]:
        """Create a finding with status 'proposed'.

        Also runs a conflict check so contradictions surface at the moment a
        finding enters the system. The check never blocks the proposal.
        """
        statement = self._require_name(statement, "statement")
        owner = self._require_name(owner, "owner")
        if tier not in TIERS:
            raise CoreError(f"tier must be one of {TIERS}")
        links = sorted({int(x) for x in (evidence_links or [])})
        warnings = []
        with self._conn() as conn:
            for eid in links:
                self._row(conn, eid)
            cur = conn.execute(
                "INSERT INTO findings (statement, tier, status, owner, evidence_links, created_at) "
                "VALUES (?, ?, 'proposed', ?, ?, ?)",
                (statement, tier, owner, json.dumps(links), _now()),
            )
            fid = cur.lastrowid
            self._log(conn, fid, "proposed", owner, tier=tier, evidence_links=links)
        if tier != "data_point" and not links:
            warnings.append(f"this {tier} has no evidence links yet")
        conflicts = self.check_conflict(finding_id=fid)["candidates"]
        return {"finding": self.get(fid), "possible_conflicts": conflicts, "warnings": warnings}

    def validate(self, finding_id: int, validated_by: str, note: str | None = None) -> dict[str, Any]:
        """Add one validation record. The first one moves 'proposed' to 'validated'.

        A contested finding keeps its 'contested' status: more validations are
        recorded and visible, but they do not silently resolve the conflict.
        """
        validated_by = self._require_name(validated_by, "validated_by")
        with self._conn() as conn:
            row = self._row(conn, finding_id)
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
        confirmed_by = self._require_name(confirmed_by, "confirmed_by")
        if finding_id == conflicting_id:
            raise CoreError("a finding cannot conflict with itself")
        with self._conn() as conn:
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
        who = self._require_name(who, "who")
        with self._conn() as conn:
            row = self._row(conn, finding_id)
            warnings = self._checkout_warning(row, who)
            conn.execute(
                "UPDATE findings SET checked_out_by = ?, checked_out_at = ? WHERE id = ?",
                (who, _now(), finding_id),
            )
            self._log(conn, finding_id, "checked_out", who, previous_holder=row["checked_out_by"])
        return {"finding": self.get(finding_id), "warnings": warnings}

    def release(self, finding_id: int, who: str) -> dict[str, Any]:
        who = self._require_name(who, "who")
        with self._conn() as conn:
            row = self._row(conn, finding_id)
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
