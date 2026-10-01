"""Core layer: the data store and the actions on learnings.

Everything that reads or writes goes through the Store class. The MCP server
and the web app are thin wrappers around it, so there is only one write path
and one version of the truth. The words used here are defined in
docs/GLOSSARY.md.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from . import config as config_mod

# How far a learning goes. Promotion moves up one level.
LEVELS = ("observation", "finding", "insight")
NEXT_LEVEL = {"observation": "finding", "finding": "insight"}
# Where a learning is in its life. Made with AI starts as a draft until its
# owner confirms it. Replaced means a newer version took its place.
STAGES = ("draft", "shared", "replaced")
# Who made it. An AI agent always has a named person as owner.
ORIGINS = ("person", "person_with_ai", "ai_agent")
# A review's verdict. Only approve counts toward a learning being checked.
VERDICTS = ("approve", "changes", "disagree")
# How one learning relates to another. "supports" is stored as evidence and
# "conflicts_with" as a conflict, so each fact lives in one place.
LINK_TYPES = ("supports", "builds_on", "same_as", "conflicts_with")
# requested: someone asked for research and nobody has picked it up yet.
# dropped: ended without running, for example answered by what we know.
STUDY_STAGES = ("requested", "planned", "running", "finished", "dropped")
STUDY_TEXT = ("question", "decision", "hypothesis", "method", "sample", "learned", "notes")
# What each study stage asks for. Team template fields add to these.
STUDY_ASKS = {
    "start": (("decision", "Decision it serves"),),
    "running": (("method", "Method"), ("sample", "Who or what we studied")),
    "finished": (("learned", "What we learned"),),
}
STAGE_ASKS = {"requested": (), "planned": ("start",), "running": ("start", "running"),
              "finished": ("start", "running", "finished"), "dropped": ()}
REQUEST_STATUSES = ("open", "done", "withdrawn")
# How sure an AI says it is about a block it made. Never counts as a check.
CONFIDENCE = ("low", "medium", "high")
# What a piece of context in a workspace is. ai_text is pasted AI output, kept
# whole so the blocks taken from it can point back to it.
SOURCE_KINDS = ("note", "quote", "data", "query", "link", "file", "ai_text")
# The plan: how far each sub-question has got, worked out from its blocks.
# Answered means an insight that answers it is checked by someone other than
# its owner. Only findings and insights answer; observations sit under them.
PLAN_LABEL = {"open": "Open", "in_progress": "In progress", "answered": "Answered"}
ANSWER_LEVELS = ("finding", "insight")
PLAN_SIZE = 5  # a nudge, never a limit

# One trust state per learning. When more than one could apply, the first in
# TRUST_ORDER wins.
TRUST_LABEL = {
    "contested": "Contested",
    "needs_changes": "Needs changes",
    "checked_by_sme": "Checked by an SME",
    "checked_by_peers": "Checked by peers",
    "not_reviewed": "Not reviewed",
}
TRUST_ORDER = tuple(TRUST_LABEL)
# The one check state a block shows in the workbench, first match wins. It
# folds stage and trust together: a draft needs its owner's check, and a shared
# block nobody else has reviewed is checked by its owner.
CHECK_LABEL = {
    "disagreement": "Disagreement",
    "needs_changes": "Needs changes",
    "needs_check": "Needs a check",
    "checked_by_sme": "Checked by an SME",
    "checked_by_peers": "Checked by peers",
    "checked_by_owner": "Checked by owner",
}
CHECK_FROM_TRUST = {"contested": "disagreement", "needs_changes": "needs_changes",
                    "checked_by_sme": "checked_by_sme", "checked_by_peers": "checked_by_peers",
                    "not_reviewed": "checked_by_owner"}
# States a block can be built on, but that keep what is built on it flagged.
UNCHECKED = ("disagreement", "needs_changes", "needs_check")
# The three answers to a check, and the review verdict each becomes.
CHECK_VERDICTS = {"looks_right": "approve", "needs_changes": "changes", "disagree": "disagree"}
CHECKED = ("checked_by_sme", "checked_by_peers")
VERDICT_SAID = {"approve": "approved", "changes": "asked for changes on", "disagree": "disagreed with"}
CREDIT_FOR = {"approve": "approved", "changes": "asked for changes", "disagree": "disagreed"}
LINK_SAID = {"supports": "supports", "builds_on": "builds on", "same_as": "is the same as",
             "conflicts_with": "conflicts with"}
# Counts that earn a milestone moment.
MILESTONES = (5, 10, 25, 50, 100, 250, 500, 1000)
# How loudly the app shows a digest item: 1 do now, 2 news, 3 digest only.
DO_NOW, NEWS, DIGEST = 1, 2, 3

DEFAULT_DB_PATH = os.environ.get("ANCHOR_DB", "anchor.db")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS learnings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    statement      TEXT NOT NULL,
    level          TEXT NOT NULL CHECK (level IN {LEVELS}),
    stage          TEXT NOT NULL DEFAULT 'shared' CHECK (stage IN {STAGES}),
    origin         TEXT NOT NULL DEFAULT 'person' CHECK (origin IN {ORIGINS}),
    owner          TEXT NOT NULL,
    evidence       TEXT NOT NULL DEFAULT '[]',  -- JSON list of learning ids that support it
    source_ids     TEXT NOT NULL DEFAULT '[]',  -- JSON list of sources it was taken from
    confidence     TEXT CHECK (confidence IN {CONFIDENCE}),  -- what the AI said, if an AI made it
    why            TEXT,                         -- the AI's one line reason
    assumes        TEXT NOT NULL DEFAULT '[]',  -- JSON list of what it takes as given
    study_id       INTEGER REFERENCES studies(id),
    question_id    INTEGER REFERENCES questions(id),  -- the sub-question a finding or insight answers
    promoted_from  INTEGER REFERENCES learnings(id),
    revises        INTEGER REFERENCES learnings(id),
    created_at     TEXT NOT NULL,
    working_by     TEXT,
    working_at     TEXT
);

-- One row per review. Never collapsed into a single flag. A person can
-- review again; their latest review is the one that counts, and earlier ones
-- stay visible. Role and SME standing are kept as they were at review time.
CREATE TABLE IF NOT EXISTS reviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id  INTEGER NOT NULL REFERENCES learnings(id),
    by           TEXT NOT NULL,
    at           TEXT NOT NULL,
    verdict      TEXT NOT NULL CHECK (verdict IN {VERDICTS}),
    how          TEXT,  -- a key from the team's checks
    note         TEXT,
    role         TEXT,
    sme          INTEGER NOT NULL DEFAULT 0
);

-- A request for someone, anyone in a role, or any SME to review a learning.
-- Closed by any review from that person or group. Nobody needs to be asked.
CREATE TABLE IF NOT EXISTS review_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id  INTEGER NOT NULL REFERENCES learnings(id),
    asked_by     TEXT NOT NULL,
    person       TEXT,  -- one of person or role is set; role 'sme' means any SME
    role         TEXT,
    note         TEXT,
    at           TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN {REQUEST_STATUSES}),
    closed_by    TEXT,
    closed_at    TEXT,
    verdict      TEXT
);

-- A confirmed conflict between two learnings. Both stay visible.
CREATE TABLE IF NOT EXISTS conflicts (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    a     INTEGER NOT NULL REFERENCES learnings(id),
    b     INTEGER NOT NULL REFERENCES learnings(id),
    by    TEXT NOT NULL,
    at    TEXT NOT NULL,
    note  TEXT
);

-- Other ways two learnings relate. A builds_on B: A builds on B.
-- same_as reads the same from both sides.
CREATE TABLE IF NOT EXISTS links (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id  INTEGER NOT NULL REFERENCES learnings(id),
    to_id    INTEGER NOT NULL REFERENCES learnings(id),
    type     TEXT NOT NULL CHECK (type IN ('builds_on', 'same_as')),
    by       TEXT NOT NULL,
    at       TEXT NOT NULL,
    note     TEXT,
    UNIQUE (from_id, to_id, type)
);

-- A decision someone made, and the learnings it relied on. This is how
-- research shows its value, and how a decision owner learns when something
-- they relied on is later contested. The outcome is added later, once known.
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    made_by     TEXT NOT NULL,
    at          TEXT NOT NULL,
    note        TEXT,
    outcome     TEXT,
    outcome_at  TEXT
);

CREATE TABLE IF NOT EXISTS decision_uses (
    decision_id   INTEGER NOT NULL REFERENCES decisions(id),
    learning_id   INTEGER NOT NULL REFERENCES learnings(id),
    trust_at_use  TEXT NOT NULL,
    PRIMARY KEY (decision_id, learning_id)
);

-- A piece of research: the question, the decision it serves, and how it was
-- studied. Learnings added inside a study carry this context with them.
CREATE TABLE IF NOT EXISTS studies (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    question          TEXT NOT NULL,
    decision          TEXT,
    hypothesis        TEXT,  -- what the study expects to find, if anything
    method            TEXT,
    sample            TEXT,
    learned           TEXT,  -- the wrap up, once finished
    notes             TEXT,  -- what a checker should know: dates, gaps, caveats
    package           TEXT NOT NULL DEFAULT '[]',  -- insight ids chosen to share, in order
    status            TEXT NOT NULL CHECK (status IN {STUDY_STAGES}),
    owner             TEXT,  -- empty while a request waits to be picked up
    fields            TEXT NOT NULL DEFAULT '{{}}',  -- team template fields, JSON
    requested_by      TEXT,
    from_decision_id  INTEGER,
    from_query        TEXT,
    created_at        TEXT NOT NULL
);

-- The plan: sub-questions a workspace needs answered to make its decision.
-- Findings and insights say which one they answer.
CREATE TABLE IF NOT EXISTS questions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id  INTEGER NOT NULL REFERENCES studies(id),
    text      TEXT NOT NULL,
    expect    TEXT,  -- what we expect to find, if anything
    position  INTEGER NOT NULL,
    added_by  TEXT NOT NULL,
    at        TEXT NOT NULL
);

-- Context collected in a workspace (a study): notes, quotes, data, queries,
-- links, and pasted AI text. Observations point back to the sources they came from.
CREATE TABLE IF NOT EXISTS sources (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id  INTEGER NOT NULL REFERENCES studies(id),
    kind      TEXT NOT NULL CHECK (kind IN {SOURCE_KINDS}),
    title     TEXT NOT NULL,
    body      TEXT NOT NULL,
    url       TEXT,
    added_by  TEXT NOT NULL,
    at        TEXT NOT NULL
);

-- Everyone who has taken an action. Names are matched without regard to
-- case, so "sam" and "Sam" are one person.
CREATE TABLE IF NOT EXISTS people (
    name        TEXT PRIMARY KEY COLLATE NOCASE,
    role        TEXT NOT NULL,
    sme         INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

-- Learnings a person chose to follow. Owning, reviewing, or using a learning
-- in a decision follows it without a row here.
CREATE TABLE IF NOT EXISTS follows (
    name         TEXT NOT NULL COLLATE NOCASE,
    learning_id  INTEGER NOT NULL REFERENCES learnings(id),
    at           TEXT NOT NULL,
    PRIMARY KEY (name, learning_id)
);

-- What a person has already seen, or set aside with "Not now".
CREATE TABLE IF NOT EXISTS seen (
    name  TEXT NOT NULL COLLATE NOCASE,
    key   TEXT NOT NULL,
    at    TEXT NOT NULL,
    PRIMARY KEY (name, key)
);

-- Append-only record. Drives history, the digest, and moments.
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id  INTEGER REFERENCES learnings(id),
    study_id     INTEGER,
    decision_id  INTEGER,
    kind         TEXT NOT NULL,
    actor        TEXT NOT NULL,
    at           TEXT NOT NULL,
    detail       TEXT NOT NULL DEFAULT '{{}}'
);
"""


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


def _short(text: str | None, n: int = 70) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 3].rstrip() + "..."


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Text matching. Deliberately simple and dependency free for the prototype.
# The conflict check only *suggests* candidates; a person always confirms.
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


# ---------------------------------------------------------------------------
# Taking long AI text apart. Plain rules, no AI, so it runs anywhere and is
# easy to read. It only drafts: a person checks every block it makes.
# ---------------------------------------------------------------------------

_BULLET_RE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_INSIGHT_RE = re.compile(r"\b(should|recommend\w*|we need to|must|prioriti[sz]\w*|opportunit\w+|invest\w*|"
                         r"focus on|next step|biggest win|worth doing)\b", re.I)
_FINDING_RE = re.compile(r"\b(because|suggest\w*|indicat\w*|likely|drive[sn]?|driven|due to|means|therefore|"
                         r"leads? to|mainly|main reason|pattern|explains?|caus\w+|so that)\b", re.I)
_OBSERVED_RE = re.compile(r"\d|\b(percent|said|told us|reported|measured|saw|observed)\b", re.I)
# Words that take something as given. Each maps to the line shown under Assumes.
_ASSUMES = (
    (re.compile(r"\b(most|majority|many|few|often|usually|typically)\b", re.I), 'Says "{w}" without a number',
     lambda t: not re.search(r"\d", t)),
    (re.compile(r"\b(always|never|all|every|everyone|nobody|none)\b", re.I), 'Uses "{w}", which allows no exceptions',
     None),
    (re.compile(r"\b(likely|probably|may|might|could|seems?)\b", re.I), 'Hedges with "{w}" without saying why', None),
    (re.compile(r"\b(clearly|obviously|of course|undoubtedly|certainly)\b", re.I),
     'Says "{w}" as if it needs no support', None),
    (re.compile(r"\b(because|due to|drives?|causes?|leads? to)\b", re.I), 'Claims a cause ("{w}") the text does not show',
     lambda t: not re.search(r"\d", t)),
)


def _split_claims(text: str) -> list[str]:
    """One piece per sentence or bullet. Headings and fragments are dropped."""
    pieces = []
    lines = [ln.strip() for ln in text.splitlines()]
    first = next((i for i, ln in enumerate(lines) if ln), None)
    for i, raw in enumerate(lines):
        line = _BULLET_RE.sub("", raw).strip()
        if not line or line.endswith(":") or line.startswith("#"):
            continue
        # A short first line with no full stop, set apart from the rest, is a title.
        if i == first and line[-1] not in ".!?" and len(line.split()) <= 10 and (i + 1 == len(lines) or not lines[i + 1]):
            continue
        for part in _SENTENCE_RE.split(line):
            part = part.strip().strip("\"'").strip()
            if len(part.split()) >= 4:
                pieces.append(part if part[-1] in ".!?" else part + ".")
    return pieces


def _guess_level(text: str) -> str:
    if _INSIGHT_RE.search(text):
        return "insight"
    if _FINDING_RE.search(text):
        return "finding"
    return "observation"


def _assumptions(text: str) -> list[str]:
    out = []
    for pattern, line, when in _ASSUMES:
        m = pattern.search(text)
        if m and (when is None or when(text)):
            out.append(line.format(w=m.group(0).lower()))
    return out


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
            old = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'findings'").fetchone() or (
                conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'learnings'").fetchone()
                and not any(c[1] == "question_id" for c in conn.execute("PRAGMA table_info(learnings)")))
            if old:
                raise CoreError(f"{path} was made by an older ANCHOR. Move it aside and start a new database.")
            conn.executescript(SCHEMA)
            self._sync_people(conn)

    def _sync_people(self, conn) -> None:
        """The config file is the source of truth for the people and SMEs it lists."""
        for name, role in self.config["people"].items():
            conn.execute(
                "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT (name) DO UPDATE SET role = excluded.role",
                (name, role, _now()),
            )
        for name in self.config["smes"]:
            conn.execute(
                "INSERT INTO people (name, role, sme, created_at) VALUES (?, ?, 1, ?) "
                "ON CONFLICT (name) DO UPDATE SET sme = 1",
                (name, self.config["default_role"], _now()),
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
    def _log(conn, learning_id, kind, actor, _study=None, _decision=None, **detail) -> int:
        cur = conn.execute(
            "INSERT INTO events (learning_id, study_id, decision_id, kind, actor, at, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (learning_id, _study, _decision, kind, actor, _now(), json.dumps(detail)),
        )
        return cur.lastrowid

    @staticmethod
    def _require(value: str | None, field: str) -> str:
        value = (value or "").strip()
        if not value:
            raise CoreError(f"{field} is required")
        return value

    @staticmethod
    def _row(conn, learning_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM learnings WHERE id = ?", (learning_id,)).fetchone()
        if row is None:
            raise CoreError(f"learning {learning_id} does not exist")
        return row

    @staticmethod
    def _study_row(conn, study_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM studies WHERE id = ?", (study_id,)).fetchone()
        if row is None:
            raise CoreError(f"study {study_id} does not exist")
        return row

    @staticmethod
    def _decision_row(conn, decision_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            raise CoreError(f"decision {decision_id} does not exist")
        return row

    def _person(self, conn, name: str | None, field: str) -> str:
        """Resolve a name to the person on record, adding them on first use.

        Returns the name as first recorded, so small differences in case do not
        split one person into two. New people get the team's default role.
        """
        name = self._require(name, field)
        row = conn.execute("SELECT name FROM people WHERE name = ?", (name,)).fetchone()
        if row:
            return row["name"]
        conn.execute(
            "INSERT INTO people (name, role, created_at) VALUES (?, ?, ?)",
            (name, self.config["default_role"], _now()),
        )
        self._log(conn, None, "joined", name, role=self.config["default_role"])
        return name

    @staticmethod
    def _who(conn, name: str | None) -> sqlite3.Row | None:
        if not name:
            return None
        return conn.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()

    def _role_label(self, role: str | None) -> str | None:
        return self.config["roles"].get(role, {}).get("label", role) if role else None

    def _level_label(self, level: str) -> str:
        return self.config["levels"].get(level, level)

    def _person_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {"name": row["name"], "role": row["role"], "role_label": self._role_label(row["role"]),
                "sme": bool(row["sme"])}

    # -- trust -------------------------------------------------------------

    @staticmethod
    def _current_reviews(conn, learning_id: int) -> list[sqlite3.Row]:
        """Each reviewer's latest review of a learning. Earlier ones are history."""
        return conn.execute(
            "SELECT * FROM reviews r WHERE learning_id = ? AND id = "
            "(SELECT MAX(id) FROM reviews w WHERE w.learning_id = r.learning_id AND w.by = r.by) ORDER BY id",
            (learning_id,),
        ).fetchall()

    @staticmethod
    def _conflict_ids(conn, learning_id: int) -> list[int]:
        return [r[0] for r in conn.execute(
            "SELECT CASE WHEN a = ? THEN b ELSE a END FROM conflicts WHERE a = ? OR b = ? ORDER BY id",
            (learning_id, learning_id, learning_id),
        )]

    def _trust(self, conn, learning_id: int) -> dict[str, Any]:
        """How far to lean on a learning: one state, and a plain sentence that
        the app and AI tools both use."""
        current = self._current_reviews(conn, learning_id)
        approvals = [r for r in current if r["verdict"] == "approve"]
        sme = sum(bool(r["sme"]) for r in approvals)
        peer = len(approvals) - sme
        changes = sum(r["verdict"] == "changes" for r in current)
        disagree = sum(r["verdict"] == "disagree" for r in current)
        conflicts = self._conflict_ids(conn, learning_id)
        checked: dict[str, int] = {}
        for r in approvals:
            if r["how"]:
                checked[r["how"]] = checked.get(r["how"], 0) + 1

        if conflicts or disagree:
            state = "contested"
        elif changes:
            state = "needs_changes"
        elif sme:
            state = "checked_by_sme"
        elif peer:
            state = "checked_by_peers"
        else:
            state = "not_reviewed"

        who = " and ".join(p for p in (
            f"{sme} SME{'s' if sme != 1 else ''}" if sme else "",
            f"{peer} peer{'s' if peer != 1 else ''}" if peer else "",
        ) if p)
        parts = [f"Checked by {who}." if who else "Not reviewed yet."]
        if checked:
            labels = self.config["checks"]
            parts.append("How they checked: " + ", ".join(
                f"{labels.get(k, k).lower()} ({n})" for k, n in checked.items()) + ".")
        if changes:
            parts.append(f"{changes} {'asks' if changes == 1 else 'ask'} for changes.")
        if disagree:
            parts.append(f"{disagree} {'disagrees' if disagree == 1 else 'disagree'}.")
        if conflicts:
            parts.append("Conflicts with " + ", ".join(f"#{c}" for c in conflicts) + ".")
        return {
            "state": state, "label": TRUST_LABEL[state], "sme": sme, "peer": peer,
            "changes": changes, "disagree": disagree, "conflicts": conflicts, "checked": checked,
            "summary": " ".join(parts),
        }

    @staticmethod
    def _chip(row: sqlite3.Row, trust: dict[str, Any]) -> dict[str, str]:
        """The one chip a list row shows: the stage when it is unusual, else trust."""
        if row["stage"] == "draft":
            return {"key": "draft", "label": "Draft"}
        if row["stage"] == "replaced":
            return {"key": "replaced", "label": "Replaced"}
        return {"key": trust["state"], "label": trust["label"]}

    def _check(self, conn, row: sqlite3.Row, trust: dict[str, Any] | None = None) -> dict[str, str]:
        """The one check state a block shows: stage and trust folded together."""
        if row["stage"] == "replaced":
            return {"state": "replaced", "label": "Replaced"}
        if row["stage"] == "draft":
            state = "needs_check"
        else:
            state = CHECK_FROM_TRUST[(trust or self._trust(conn, row["id"]))["state"]]
        return {"state": state, "label": CHECK_LABEL[state]}

    @staticmethod
    def _latest(conn, learning_id: int) -> int:
        """Follow revisions to the newest version, so what a block is built on
        always points at the version people see."""
        seen = {learning_id}
        while True:
            r = conn.execute("SELECT id FROM learnings WHERE revises = ? ORDER BY id DESC LIMIT 1",
                             (learning_id,)).fetchone()
            if r is None or r[0] in seen:
                return learning_id
            learning_id = r[0]
            seen.add(learning_id)

    def _parts(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        """What a block rests on, and how much of that is still unchecked.

        unchecked_parts counts the blocks directly under it that need a check,
        need changes, or have a disagreement. deep_unchecked counts the same
        further down. rests_on_nothing is true when an observation cites no
        source, or a finding or insight is built on no blocks.
        """
        built_on = []
        for e in json.loads(row["evidence"]):
            latest = self._latest(conn, e)
            if latest not in built_on:
                built_on.append(latest)
        state = {}

        def state_of(lid):
            if lid not in state:
                state[lid] = self._check(conn, self._row(conn, lid))["state"]
            return state[lid]

        direct = [e for e in built_on if state_of(e) in UNCHECKED]
        deep, stack, seen = set(), list(built_on), set(built_on)
        while stack:
            r = self._row(conn, stack.pop())
            for e in json.loads(r["evidence"]):
                e = self._latest(conn, e)
                if e in seen:
                    continue
                seen.add(e)
                stack.append(e)
                if state_of(e) in UNCHECKED:
                    deep.add(e)
        source_ids = json.loads(row["source_ids"])
        nothing = not source_ids if row["level"] == "observation" else not built_on
        return {"built_on": built_on, "source_ids": source_ids, "unchecked_parts": len(direct),
                "unchecked_ids": direct, "deep_unchecked": len(deep), "rests_on_nothing": nothing}

    def _block(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        """A block as the workbench draws it: what it says, its one check state,
        what it rests on, and what the AI said about it."""
        return {"id": row["id"], "statement": row["statement"], "level": row["level"], "stage": row["stage"],
                "origin": row["origin"], "owner": row["owner"], "study_id": row["study_id"],
                "question_id": row["question_id"], "check": self._check(conn, row),
                **self._ai_said(row), **self._parts(conn, row)}

    @staticmethod
    def _ai_said(row: sqlite3.Row) -> dict[str, Any]:
        return {"confidence": row["confidence"], "why": row["why"], "assumes": json.loads(row["assumes"])}

    def _retrust(self, conn, learning_id: int, before: str, actor: str, cause: str, moment: bool = True) -> str:
        """Log a change in trust, and warn decisions when something they used is now contested."""
        after = self._trust(conn, learning_id)["state"]
        if after == before:
            return after
        row = self._row(conn, learning_id)
        self._log(conn, learning_id, "trust_changed", actor, row["study_id"], **{"from": before, "to": after, "cause": cause})
        if after == "contested":
            for u in conn.execute("SELECT decision_id FROM decision_uses WHERE learning_id = ?", (learning_id,)).fetchall():
                self._log(conn, learning_id, "decision_at_risk", actor, None, u["decision_id"])
        if after in CHECKED and before not in CHECKED:
            if row["level"] == "insight" and moment:
                self._moment(conn, "checked", actor, row["owner"],
                             f"Your insight #{learning_id} is now {TRUST_LABEL[after]}.", learning_id=learning_id)
            self._milestone_mine(conn, row["owner"], actor)
        return after

    # -- moments -----------------------------------------------------------

    def _moment(self, conn, kind: str, actor: str, to: str, text: str, learning_id=None, decision_id=None,
                key: str | None = None) -> None:
        """A small good-news note for one person, or "*" for the whole team.

        Never compares people. A key stops the same moment being made twice.
        """
        if kind not in self.config["moments"] or (to != "*" and to == actor):
            return
        if key and conn.execute(
            "SELECT 1 FROM events WHERE kind = 'moment' AND json_extract(detail, '$.key') = ?", (key,)
        ).fetchone():
            return
        self._log(conn, learning_id, "moment", actor, None, decision_id, to=to, moment=kind, text=text, key=key)

    def _milestone_mine(self, conn, owner: str, actor: str) -> None:
        n = sum(
            self._trust(conn, r["id"])["state"] in CHECKED
            for r in conn.execute("SELECT id FROM learnings WHERE owner = ? AND stage = 'shared'", (owner,))
        )
        if n in MILESTONES:
            self._moment(conn, "milestone", actor, owner, f"That is your {_ordinal(n)} checked learning.",
                         key=f"mine:{owner.lower()}:{n}")

    def _milestone_team(self, conn, actor: str) -> None:
        n = conn.execute("SELECT COUNT(DISTINCT decision_id) FROM decision_uses").fetchone()[0]
        if n in MILESTONES:
            self._moment(conn, "milestone", actor, "*", f"The team's learnings have now informed {n} decisions.",
                         key=f"team:decisions:{n}")

    BUILT_ON = {"evidence": "used your learning #{} as evidence", "promoted": "promoted your learning #{}",
                "builds_on": "built on your learning #{}"}

    def _built_on(self, conn, actor: str, learning_id: int, how: str) -> None:
        owner = self._row(conn, learning_id)["owner"]
        self._moment(conn, "built_on", actor, owner, f"{actor} {self.BUILT_ON[how].format(learning_id)}.",
                     learning_id=learning_id, key=f"built:{learning_id}:{how}:{actor.lower()}")

    # -- shaping records ---------------------------------------------------

    def _brief(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        trust = self._trust(conn, row["id"])
        return {"id": row["id"], "statement": row["statement"], "level": row["level"], "stage": row["stage"],
                "origin": row["origin"], "owner": row["owner"], "chip": self._chip(row, trust)}

    def _full(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        """A learning with everything needed to judge how far to trust it."""
        lid = row["id"]
        evidence_ids = json.loads(row["evidence"])
        evidence = [self._brief(conn, r) for r in (
            conn.execute("SELECT * FROM learnings WHERE id = ?", (e,)).fetchone() for e in evidence_ids) if r]
        supports = [self._brief(conn, r) for r in conn.execute(
            "SELECT l.* FROM learnings l, json_each(l.evidence) j WHERE j.value = ? ORDER BY l.id", (lid,))]
        current = {r["id"] for r in self._current_reviews(conn, lid)}
        reviews = []
        for r in conn.execute("SELECT * FROM reviews WHERE learning_id = ? ORDER BY id", (lid,)):
            v = dict(r)
            v["sme"] = bool(v["sme"])
            v["role_label"] = self._role_label(v["role"])
            v["current"] = v["id"] in current
            reviews.append(v)
        # Current reviews first, SMEs first within them, then oldest first.
        reviews.sort(key=lambda v: (not v["current"], not v["sme"], v["id"]))
        conflicts = []
        for c in conn.execute("SELECT * FROM conflicts WHERE a = ? OR b = ? ORDER BY id", (lid, lid)):
            other = c["b"] if c["a"] == lid else c["a"]
            conflicts.append({"with": self._brief(conn, self._row(conn, other)), "by": c["by"], "at": c["at"],
                              "note": c["note"]})
        links = {"builds_on": [], "built_on_by": [], "same_as": []}
        for link in conn.execute("SELECT * FROM links WHERE from_id = ? OR to_id = ? ORDER BY id", (lid, lid)):
            outgoing = link["from_id"] == lid
            other = self._row(conn, link["to_id"] if outgoing else link["from_id"])
            group = link["type"] if outgoing or link["type"] == "same_as" else "built_on_by"
            links[group].append({"learning": self._brief(conn, other), "by": link["by"], "at": link["at"],
                                 "note": link["note"]})
        srow = conn.execute("SELECT * FROM studies WHERE id = ?", (row["study_id"],)).fetchone()
        qrow = conn.execute("SELECT id, text, expect FROM questions WHERE id = ?", (row["question_id"],)).fetchone()
        prow = conn.execute("SELECT * FROM learnings WHERE id = ?", (row["promoted_from"],)).fetchone()
        rrow = conn.execute("SELECT * FROM learnings WHERE id = ?", (row["revises"],)).fetchone()
        promoted_to = [self._brief(conn, r) for r in conn.execute(
            "SELECT * FROM learnings WHERE promoted_from = ? AND revises IS NULL ORDER BY id", (lid,))]
        replaced_by = [self._brief(conn, r) for r in conn.execute(
            "SELECT * FROM learnings WHERE revises = ? ORDER BY id", (lid,))]
        trust = self._trust(conn, lid)
        confirmed = conn.execute(
            "SELECT actor, at, detail FROM events WHERE learning_id = ? AND kind = 'confirmed' ORDER BY id DESC LIMIT 1",
            (lid,),
        ).fetchone()
        requests = [dict(r) for r in conn.execute(
            "SELECT id, asked_by, person, role, note, at FROM review_requests "
            "WHERE learning_id = ? AND status = 'open' ORDER BY id", (lid,))]
        used_in = [dict(d) for d in conn.execute(
            "SELECT d.id, d.title, d.made_by, d.at FROM decisions d JOIN decision_uses u ON u.decision_id = d.id "
            "WHERE u.learning_id = ? ORDER BY d.id", (lid,))]
        return {
            "id": lid,
            "statement": row["statement"],
            "level": row["level"],
            "stage": row["stage"],
            "origin": row["origin"],
            "owner": row["owner"],
            "owner_role": (self._who(conn, row["owner"]) or {"role": None})["role"],
            "created_at": row["created_at"],
            "confirmed": {"by": confirmed["actor"], "at": confirmed["at"], **json.loads(confirmed["detail"])}
            if confirmed else None,
            "chip": self._chip(row, trust),
            "trust": trust,
            "check": self._check(conn, row, trust),
            **self._ai_said(row),
            **{k: v for k, v in self._parts(conn, row).items() if k != "built_on"},
            "sources": [dict(r) for r in conn.execute(
                "SELECT s.id, s.kind, s.title, s.body, s.url FROM sources s, json_each(?) j WHERE s.id = j.value",
                (row["source_ids"],))],
            "study": {k: srow[k] for k in ("id", "question", "decision", "status")} if srow else None,
            "answers": dict(qrow) if qrow else None,
            "evidence_ids": evidence_ids,
            "evidence": evidence,
            "supports": supports,
            "links": links,
            "promoted_from": self._brief(conn, prow) if prow else None,
            "promoted_to": promoted_to,
            "revises": self._brief(conn, rrow) if rrow else None,
            "replaced_by": replaced_by,
            "connections": len(evidence) + len(supports) + len(conflicts) + sum(map(len, links.values()))
            + len(promoted_to) + (1 if prow else 0),
            "promotion": self._readiness(conn, row) if row["level"] in NEXT_LEVEL else None,
            "reviews": reviews,
            "open_requests": requests,
            "used_in": used_in,
            "conflicts": conflicts,
            "working_by": row["working_by"],
            "working_at": row["working_at"],
        }

    def _readiness(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        """Whether a learning meets the team's promotion rule. Any one rule is enough."""
        rules = self.config["promote"]
        trust = self._trust(conn, row["id"])
        checks = []
        if rules["min_approvals"]:
            n = trust["sme"] + trust["peer"]
            checks.append((n >= rules["min_approvals"], f"{n} of {rules['min_approvals']} approvals"))
        if rules["min_sme_approvals"]:
            checks.append((trust["sme"] >= rules["min_sme_approvals"],
                           f"{trust['sme']} of {rules['min_sme_approvals']} SME approvals"))
        if not checks:
            return {"ready": True, "rule": False, "summary": "", "enforced": False}
        return {"ready": any(ok for ok, _ in checks), "rule": True,
                "summary": ", or ".join(text for _, text in checks), "enforced": rules["enforce"] == "required"}

    # -- read --------------------------------------------------------------

    def team_config(self) -> dict[str, Any]:
        """Display labels and team choices: roles, levels, checks, study template, modes."""
        return config_mod.public(self.config)

    def people(self) -> list[dict[str, Any]]:
        """Everyone on record with their role and whether they are an SME."""
        order = {r: i for i, r in enumerate(self.config["roles"])}
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM people ORDER BY name COLLATE NOCASE").fetchall()
        return sorted((self._person_dict(r) for r in rows), key=lambda p: order.get(p["role"], len(order)))

    def whoami(self, name: str) -> dict[str, Any]:
        """Look up a person, adding them with the default role if they are new."""
        with self._conn() as conn:
            name = self._person(conn, name, "name")
            return self._person_dict(self._who(conn, name))

    def get(self, learning_id: int) -> dict[str, Any]:
        with self._conn() as conn:
            return self._full(conn, self._row(conn, learning_id))

    def query(
        self, topic: str = "", level: str | None = None, trust: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Learnings that match a topic or question, best match first.

        An empty topic returns the most recent. trust filters by chip: one of
        the trust states, or draft or replaced. Replaced learnings are left out
        unless asked for.
        """
        if level and level not in LEVELS:
            raise CoreError(f"level must be one of {LEVELS}")
        chips = TRUST_ORDER + ("draft", "replaced")
        if trust and trust not in chips:
            raise CoreError(f"trust must be one of {chips}")
        sql, args = "SELECT * FROM learnings WHERE 1=1", []
        if level:
            sql += " AND level = ?"
            args.append(level)
        if trust != "replaced":
            sql += " AND stage != 'replaced'"
        wanted = topic_tokens(topic or "")
        with self._conn() as conn:
            out = []
            for row in conn.execute(sql + " ORDER BY id DESC", args).fetchall():
                score = 0.0
                if wanted:
                    shared = wanted & topic_tokens(row["statement"])
                    if not shared:
                        continue
                    score = round(len(shared) / len(wanted), 2)
                f = self._full(conn, row)
                if trust and f["chip"]["key"] != trust:
                    continue
                if wanted:
                    f["match_score"] = score
                out.append(f)
        if wanted:
            out.sort(key=lambda f: (-f["match_score"], -f["id"]))
        return out[:limit]

    def _events(self, conn, where: str, args: tuple, limit: int | None = None) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT e.*, l.statement, s.question AS study_title, d.title AS decision_title FROM events e "
            "LEFT JOIN learnings l ON l.id = e.learning_id LEFT JOIN studies s ON s.id = e.study_id "
            f"LEFT JOIN decisions d ON d.id = e.decision_id WHERE {where} ORDER BY e.id DESC"
            + (" LIMIT ?" if limit else ""),
            args + ((limit,) if limit else ()),
        ).fetchall()
        return [self._event(r) for r in rows]

    def _event(self, r: sqlite3.Row, you: str | None = None) -> dict[str, Any]:
        d = json.loads(r["detail"])
        return {"id": r["id"], "learning_id": r["learning_id"], "statement": r["statement"],
                "study_id": r["study_id"], "study_title": r["study_title"], "decision_id": r["decision_id"],
                "decision_title": r["decision_title"], "kind": r["kind"], "actor": r["actor"], "at": r["at"],
                "detail": d, "text": self._say(r, d, you)}

    def _say(self, e: sqlite3.Row, d: dict[str, Any], you: str | None = None) -> str:
        """One plain sentence per event, so the app and AI tools say the same thing."""
        a, ref, kind = e["actor"], f"#{e['learning_id']}", e["kind"]
        title, study = f"\"{e['decision_title']}\"", f"\"{e['study_title']}\""
        if kind == "added":
            with_ai = {"person_with_ai": " with AI", "ai_agent": " (AI agent)"}.get(d.get("origin"), "")
            if d.get("revises"):
                return f"{a}{with_ai} revised #{d['revises']} as {ref}"
            if d.get("promoted_from"):
                return f"{a}{with_ai} promoted #{d['promoted_from']} to {ref}"
            return f"{a}{with_ai} added {ref}: \"{_short(e['statement'])}\""
        if kind == "confirmed":
            return f"{a} confirmed the AI draft {ref}" + (" and changed its wording" if d.get("edited") else "")
        if kind == "promoted":
            return f"{a} promoted {ref} to {self._level_label(d['to_level']).lower()} #{d['to']}"
        if kind == "revised":
            return f"{a} revised {ref} as #{d['to']}. Was: \"{_short(d['before'])}\". Now: \"{_short(d['after'])}\""
        if kind == "reviewed":
            return f"{a} {VERDICT_SAID[d['verdict']]} {ref}" + (f": \"{_short(d['note'])}\"" if d.get("note") else "")
        if kind == "trust_changed":
            return f"{ref} is now {TRUST_LABEL[d['to']]}"
        if kind == "review_asked":
            if d.get("person"):
                target = "you" if you and d["person"].lower() == you.lower() else d["person"]
            else:
                target = "any SME" if d.get("role") == "sme" else f"any {(self._role_label(d.get('role')) or '').lower()}"
            return f"{a} asked {target} to review {ref}"
        if kind == "request_withdrawn":
            return f"{a} withdrew a review request on {ref}"
        if kind == "linked":
            return f"{a} linked: #{d['source']} {LINK_SAID[d['type']]} #{d['target']}"
        if kind == "conflict_flagged":
            return f"{a} flagged a conflict between {ref} and #{d['with']}"
        if kind == "used_in_decision":
            return f"{a} used {ref} in {title}"
        if kind == "decision_at_risk":
            return f"{ref}, used in {title}, is now Contested"
        if kind == "decision_logged":
            return f"{a} logged the decision {title}"
        if kind == "decision_updated":
            return f"{a} added what happened to {title}" if "outcome" in d.get("changed", []) else f"{a} updated {title}"
        if kind == "study_started":
            return f"{a} started the study {study}"
        if kind == "research_asked":
            return f"{a} asked for research: {study}"
        if kind == "study_updated":
            if "status" in d.get("changed", []):
                return f"{a} moved {study} to {d.get('status', '').capitalize()}"
            return f"{a} updated {study}"
        if kind == "source_added":
            return f"{a} added the source \"{d.get('title')}\" to {study}"
        if kind == "package_set":
            return f"{a} set the package for {study}"
        if kind == "question_added":
            return f"{a} added the sub-question \"{_short(d.get('text'))}\" to {study}"
        if kind == "question_changed":
            return f"{a} changed the sub-question \"{_short(d.get('text'))}\" in {study}"
        if kind == "question_removed":
            return f"{a} removed the sub-question \"{_short(d.get('text'))}\" from {study}"
        if kind == "answers_set":
            if d.get("question"):
                return f"{a} said {ref} answers \"{_short(d['question'])}\""
            return f"{a} said {ref} no longer answers a sub-question"
        if kind == "working_on":
            return f"{a} is working on {ref}" if d.get("on") else f"{a} stopped working on {ref}"
        if kind == "followed":
            return f"{a} followed {ref}"
        if kind == "joined":
            return f"{a} joined as {self._role_label(d.get('role'))}"
        if kind == "person_set":
            bits = []
            if "role" in d:
                bits.append(f"role to {self._role_label(d['role'])}")
            if "sme" in d:
                bits.append("SME" if d["sme"] else "not an SME")
            return f"{a} set {d['person']}: " + ", ".join(bits)
        if kind == "moment":
            return d["text"]
        return f"{a} {kind.replace('_', ' ')}"

    def activity(self, limit: int = 50) -> list[dict[str, Any]]:
        """The full record, newest first. Everything is here; the digest picks what matters."""
        with self._conn() as conn:
            return self._events(conn, "e.kind != 'moment'", (), limit)

    def history(self, learning_id: int) -> list[dict[str, Any]]:
        """Every change to one learning, oldest first. Nothing is erased."""
        with self._conn() as conn:
            self._row(conn, learning_id)
            return list(reversed(self._events(conn, "e.learning_id = ? AND e.kind != 'moment'", (learning_id,))))

    # -- people ------------------------------------------------------------

    def set_person(self, name: str, by: str, role: str | None = None, sme: bool | None = None) -> dict[str, Any]:
        """Change someone's role, or whether they are an SME. Logged, so everyone can see it."""
        if role is not None and role not in self.config["roles"]:
            raise CoreError(f"role must be one of {tuple(self.config['roles'])}")
        if role is None and sme is None:
            raise CoreError("say what to change: role or sme")
        warnings = []
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            name = self._person(conn, name, "name")
            changes = {}
            if role is not None:
                changes["role"] = role
            if sme is not None:
                changes["sme"] = bool(sme)
            conn.execute(f"UPDATE people SET {', '.join(f'{k} = ?' for k in changes)} WHERE name = ?",
                         (*[int(v) if isinstance(v, bool) else v for v in changes.values()], name))
            self._log(conn, None, "person_set", by, person=name, **changes)
            person = self._person_dict(self._who(conn, name))
        listed = [n.lower() for n in list(self.config["people"]) + self.config["smes"]]
        if name.lower() in listed:
            warnings.append(f"{name} is listed in the team config, which resets them on restart")
        return {"person": person, "warnings": warnings}

    def person(self, name: str) -> dict[str, Any]:
        """A person's role, the decisions they made, and the decisions their work
        contributed to (through any learning in the chain behind them)."""
        with self._conn() as conn:
            row = self._who(conn, (name or "").strip())
            if row is None:
                raise CoreError(f"{name} has not taken part yet")
            contributed = []
            for d in conn.execute("SELECT * FROM decisions ORDER BY id DESC").fetchall():
                ids = [u[0] for u in conn.execute("SELECT learning_id FROM decision_uses WHERE decision_id = ?", (d["id"],))]
                mine = [c for c in self._credits(conn, ids) if c["name"] == row["name"]]
                if mine:
                    contributed.append({"id": d["id"], "title": d["title"], "made_by": d["made_by"], "at": d["at"],
                                        "contributions": mine[0]["contributions"]})
            made = [dict(d) for d in conn.execute(
                "SELECT id, title, at, outcome FROM decisions WHERE made_by = ? ORDER BY id DESC", (row["name"],))]
        return {**self._person_dict(row), "decisions_made": made, "contributed_to": contributed}

    # -- learnings ---------------------------------------------------------

    def _said(self, conn, study_id, source_ids=None, confidence=None, why=None, assumes=None) -> dict[str, Any]:
        """Check and tidy what a block cites and what an AI said about it."""
        ids = sorted({int(x) for x in (source_ids or [])})
        for sid in ids:
            src = conn.execute("SELECT study_id FROM sources WHERE id = ?", (sid,)).fetchone()
            if src is None:
                raise CoreError(f"source {sid} does not exist")
            if study_id is not None and src["study_id"] != int(study_id):
                raise CoreError(f"source {sid} belongs to another workspace")
        confidence = _clean(confidence)
        if confidence is not None:
            confidence = confidence.lower()
            if confidence not in CONFIDENCE:
                raise CoreError(f"confidence must be one of {CONFIDENCE}")
        if isinstance(assumes, str):
            assumes = [assumes]
        assumes = [a for a in (_clean(x) for x in (assumes or [])) if a]
        return {"source_ids": ids, "confidence": confidence, "why": _clean(why), "assumes": assumes}

    def _insert(self, conn, statement, level, owner, evidence, study_id, origin, promoted_from=None,
                revises=None, said: dict[str, Any] | None = None, question_id=None, **extra) -> int:
        if origin not in ORIGINS:
            raise CoreError(f"origin must be one of {ORIGINS}")
        for e in evidence:
            self._row(conn, e)
        if study_id is not None:
            study_id = self._study_row(conn, int(study_id))["id"]
        said = said or self._said(conn, study_id)
        question_id = self._answers(conn, level, study_id, question_id)
        stage = "shared" if origin == "person" else "draft"
        cur = conn.execute(
            "INSERT INTO learnings (statement, level, stage, origin, owner, evidence, source_ids, confidence, why, "
            "assumes, study_id, question_id, promoted_from, revises, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (statement, level, stage, origin, owner, json.dumps(evidence), json.dumps(said["source_ids"]),
             said["confidence"], said["why"], json.dumps(said["assumes"]), study_id, question_id, promoted_from,
             revises, _now()),
        )
        lid = cur.lastrowid
        detail = {"level": level, "origin": origin, "evidence": evidence, **extra}
        if question_id:
            detail["answers"] = question_id
        if promoted_from:
            detail["promoted_from"] = promoted_from
        if revises:
            detail["revises"] = revises
        self._log(conn, lid, "added", owner, study_id, **detail)
        for e in evidence:
            if e != promoted_from:
                self._built_on(conn, owner, e, "evidence")
        return lid

    def _created(self, lid: int, warnings: list[str]) -> dict[str, Any]:
        """A new learning plus a conflict check, so contradictions surface on entry."""
        conflicts = self.check_conflict(learning_id=lid)["candidates"]
        learning = self.get(lid)
        if learning["stage"] == "draft":
            warnings.append(f"#{lid} is a draft until {learning['owner']} confirms it")
        return {"learning": learning, "possible_conflicts": conflicts, "warnings": warnings}

    def add(
        self,
        statement: str,
        level: str,
        owner: str,
        evidence: list[int] | None = None,
        study_id: int | None = None,
        origin: str = "person",
        source_ids: list[int] | None = None,
        confidence: str | None = None,
        why: str | None = None,
        assumes: list[str] | None = None,
        question_id: int | None = None,
    ) -> dict[str, Any]:
        """Write down a block (a learning), optionally inside a workspace (a study).

        origin says who made it: person, person_with_ai, or ai_agent. Anything
        made with AI starts as a draft until its owner checks it. source_ids
        are the workspace sources it was taken from; evidence is the blocks it
        is built on. An AI that made it says how confident it is (low, medium,
        high), why, and what it assumes. That never counts as a check. A
        finding or insight can say which of the workspace's sub-questions it
        answers (question_id). A conflict check runs at once, so contradictions
        surface on entry. It never blocks.
        """
        statement = self._require(statement, "statement")
        if level not in LEVELS:
            raise CoreError(f"level must be one of {LEVELS}")
        evidence = sorted({int(x) for x in (evidence or [])})
        warnings = []
        with self._conn() as conn:
            owner = self._person(conn, owner, "owner")
            said = self._said(conn, study_id, source_ids, confidence, why, assumes)
            lid = self._insert(conn, statement, level, owner, evidence, study_id, origin, said=said,
                               question_id=question_id)
        if level == "observation" and not said["source_ids"] and study_id is not None:
            warnings.append("this observation cites no source, so it rests on nothing yet")
        if level != "observation" and not evidence:
            warnings.append(f"this {self._level_label(level).lower()} is built on nothing yet")
        if origin != "person" and not (said["confidence"] and said["why"]):
            warnings.append("say how confident the AI is and why, so a checker can judge it")
        return self._created(lid, warnings)

    def confirm(self, learning_id: int, by: str, statement: str | None = None, note: str | None = None) -> dict[str, Any]:
        """The owner checks an AI draft and stands behind it. Moves it from draft
        to shared, so it can be reviewed. Pass statement to fix the wording; the
        record keeps whether the AI's wording was changed. note says what was
        checked or changed."""
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            if row["stage"] != "draft":
                raise CoreError(f"#{learning_id} is not a draft")
            if by != row["owner"]:
                raise CoreError(f"only {row['owner']} can confirm #{learning_id}")
            new = (statement or "").strip() or row["statement"]
            edited = new != row["statement"]
            conn.execute("UPDATE learnings SET stage = 'shared', statement = ? WHERE id = ?", (new, learning_id))
            self._log(conn, learning_id, "confirmed", by, row["study_id"], edited=edited, note=_clean(note),
                      **({"before": row["statement"]} if edited else {}))
            added = json.loads(conn.execute(
                "SELECT detail FROM events WHERE learning_id = ? AND kind = 'added'", (learning_id,)).fetchone()[0])
            for name in added.get("ask_again", []):
                self._ask(conn, learning_id, by, "person", name, f"Revised after your review of #{row['revises']}")
        return {"learning": self.get(learning_id), "warnings": []}

    def promote(
        self, learning_id: int, by: str, statement: str | None = None, note: str | None = None, origin: str = "person"
    ) -> dict[str, Any]:
        """Take a learning up a level: an observation to a finding, or a finding
        to an insight.

        Promotion adds a new learning one level up, linked back to the one it
        came from, which stays exactly as it was. The new one is owned by
        whoever promoted it, and can be reworded to say what the evidence now
        supports. Anyone can promote. The team's rule shows whether the source
        is ready; it only stops a promotion if the team set enforce = "required".
        """
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            if row["level"] not in NEXT_LEVEL:
                raise CoreError(f"#{learning_id} is already an insight")
            if row["stage"] == "draft":
                raise CoreError(f"#{learning_id} is a draft; its owner confirms it first")
            to = NEXT_LEVEL[row["level"]]
            readiness = self._readiness(conn, row)
            if not readiness["ready"] and readiness["enforced"]:
                raise CoreError(f"not ready to promote: {readiness['summary']}")
            warnings = []
            if not readiness["ready"]:
                warnings.append(f"not ready by the team's rule ({readiness['summary']}); promoted anyway")
            state = self._trust(conn, learning_id)["state"]
            if state == "not_reviewed":
                warnings.append(f"#{learning_id} has not been reviewed yet")
            if state == "contested":
                warnings.append(f"#{learning_id} is contested; its conflict is not resolved")
            if row["level"] != "observation" and not json.loads(row["evidence"]):
                warnings.append(f"#{learning_id} has no evidence, so this rests on it alone")
            new = (statement or "").strip() or row["statement"]
            lid = self._insert(conn, new, to, by, [learning_id], row["study_id"], origin, promoted_from=learning_id,
                               question_id=row["question_id"])
            self._log(conn, learning_id, "promoted", by, row["study_id"], to=lid, to_level=to, note=_clean(note))
            self._built_on(conn, by, learning_id, "promoted")
        return self._created(lid, warnings)

    def revise(
        self, learning_id: int, by: str, statement: str, note: str | None = None, origin: str = "person"
    ) -> dict[str, Any]:
        """Write a new version of a learning, for example after review feedback.

        The new version keeps the level, evidence, and study. The old one
        becomes Replaced and stays in the record with its reviews. Everyone
        whose current review asked for changes is asked to look again.
        """
        statement = self._require(statement, "statement")
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            if row["stage"] == "replaced":
                newer = conn.execute("SELECT id FROM learnings WHERE revises = ?", (learning_id,)).fetchone()
                raise CoreError(f"#{learning_id} is already replaced by #{newer[0]}; revise that one")
            if statement == row["statement"]:
                raise CoreError("the new version says the same thing; change the wording to revise")
            warnings = []
            if by != row["owner"]:
                warnings.append(f"#{learning_id} is owned by {row['owner']}; you own the new version")
            if self._trust(conn, learning_id)["state"] == "contested":
                warnings.append(f"#{learning_id} is contested, and revising does not resolve the conflict")
            asked = [r["by"] for r in self._current_reviews(conn, learning_id)
                     if r["verdict"] == "changes" and r["by"] != by]
            draft = origin != "person"
            lid = self._insert(conn, statement, row["level"], by, json.loads(row["evidence"]), row["study_id"], origin,
                               said=self._said(conn, row["study_id"], json.loads(row["source_ids"])),
                               promoted_from=row["promoted_from"], revises=learning_id, question_id=row["question_id"],
                               **({"ask_again": asked} if draft and asked else {}))
            conn.execute("UPDATE learnings SET stage = 'replaced' WHERE id = ?", (learning_id,))
            self._log(conn, learning_id, "revised", by, row["study_id"], to=lid, before=row["statement"],
                      after=statement, note=_clean(note))
            # Requests still open on the old version are closed; the new one asks again.
            conn.execute(
                "UPDATE review_requests SET status = 'withdrawn', closed_by = ?, closed_at = ? "
                "WHERE learning_id = ? AND status = 'open'", (by, _now(), learning_id))
            if not draft:
                for name in asked:
                    self._ask(conn, lid, by, "person", name, f"Revised after your review of #{learning_id}")
        result = self._created(lid, warnings)
        result["asked_again"] = asked
        return result

    def review(
        self,
        learning_id: int,
        by: str,
        verdict: str = "approve",
        how: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Review a learning: approve, ask for changes, or disagree, plus how you checked.

        Each review stays visible with the reviewer's role and SME standing. A
        person can review again; their latest review is the one that counts.
        Any open request for this person, their role, or any SME closes.
        """
        if verdict not in VERDICTS:
            raise CoreError(f"verdict must be one of {VERDICTS}")
        if how is not None and how not in self.config["checks"]:
            raise CoreError(f"how must be one of {tuple(self.config['checks'])}")
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            if row["owner"] == by:
                raise CoreError("you cannot review your own learning")
            if row["stage"] == "draft":
                raise CoreError(f"#{learning_id} is a draft; its owner confirms it before anyone reviews it")
            if row["stage"] == "replaced":
                newer = conn.execute("SELECT id FROM learnings WHERE revises = ?", (learning_id,)).fetchone()
                raise CoreError(f"#{learning_id} was replaced by #{newer[0]}; review that one")
            warnings = []
            if row["working_by"] and row["working_by"] != by:
                warnings.append(f"{row['working_by']} is working on #{learning_id}; your review still counts")
            last = conn.execute("SELECT verdict FROM reviews WHERE learning_id = ? AND by = ? ORDER BY id DESC LIMIT 1",
                                (learning_id, by)).fetchone()
            if last and last["verdict"] == verdict:
                raise CoreError(f"{by} has already {VERDICT_SAID[verdict]} #{learning_id}")
            before = self._trust(conn, learning_id)["state"]
            person = self._who(conn, by)
            conn.execute(
                "INSERT INTO reviews (learning_id, by, at, verdict, how, note, role, sme) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (learning_id, by, _now(), verdict, how, _clean(note), person["role"], person["sme"]),
            )
            self._log(conn, learning_id, "reviewed", by, row["study_id"], verdict=verdict, how=how, note=_clean(note),
                      role=person["role"], sme=bool(person["sme"]))
            conn.execute(
                "UPDATE review_requests SET status = 'done', closed_by = ?, closed_at = ?, verdict = ? "
                "WHERE learning_id = ? AND status = 'open' AND (person = ? OR role = ? OR (role = 'sme' AND ?))",
                (by, _now(), verdict, learning_id, by, person["role"], person["sme"]),
            )
            sme_approved = verdict == "approve" and bool(person["sme"])
            if sme_approved:
                self._moment(conn, "checked", by, row["owner"], f"{by}, an SME, approved your learning #{learning_id}.",
                             learning_id=learning_id, key=f"sme:{learning_id}:{by.lower()}")
            self._retrust(conn, learning_id, before, by, "review", moment=not sme_approved)
        return {"learning": self.get(learning_id), "warnings": warnings}

    def _ask(self, conn, learning_id: int, by: str, kind: str, who: str, note: str | None) -> int:
        cur = conn.execute(
            f"INSERT INTO review_requests (learning_id, asked_by, {kind}, note, at) VALUES (?, ?, ?, ?, ?)",
            (learning_id, by, who, note, _now()),
        )
        self._log(conn, learning_id, "review_asked", by, **{kind: who}, request_id=cur.lastrowid, note=note)
        return cur.lastrowid

    def ask_for_review(
        self,
        learning_id: int,
        by: str,
        people: list[str] | None = None,
        roles: list[str] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Ask named people, anyone in a role, or any SME (role "sme") to review a
        learning. It shows in their queue until one of them reviews it. Anyone
        can still review without being asked."""
        people = [p for p in (people or []) if (p or "").strip()]
        roles = list(roles or [])
        if not people and not roles:
            raise CoreError("name at least one person or role to ask")
        for role in roles:
            if role != "sme" and role not in self.config["roles"]:
                raise CoreError(f"role must be 'sme' or one of {tuple(self.config['roles'])}")
        warnings, made = [], []
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            if row["stage"] == "draft":
                raise CoreError(f"#{learning_id} is a draft; confirm it before asking for review")
            if row["stage"] == "replaced":
                raise CoreError(f"#{learning_id} was replaced; ask for review of the newer version")
            targets = [("person", self._person(conn, p, "people")) for p in people] + [("role", r) for r in roles]
            for kind, who in targets:
                if kind == "person" and who == row["owner"]:
                    warnings.append(f"{who} owns this learning, so they cannot review it; skipped")
                    continue
                if conn.execute(
                    f"SELECT 1 FROM review_requests WHERE learning_id = ? AND status = 'open' AND {kind} = ?",
                    (learning_id, who),
                ).fetchone():
                    warnings.append(f"{who} already has an open request for this learning; skipped")
                    continue
                made.append(self._ask(conn, learning_id, by, kind, who, _clean(note)))
        return {"learning": self.get(learning_id), "request_ids": made, "warnings": warnings}

    def withdraw_request(self, request_id: int, by: str) -> dict[str, Any]:
        """Withdraw an open review request that is no longer needed."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            req = conn.execute("SELECT * FROM review_requests WHERE id = ?", (request_id,)).fetchone()
            if req is None:
                raise CoreError(f"request {request_id} does not exist")
            if req["status"] != "open":
                raise CoreError(f"request {request_id} is already {req['status']}")
            conn.execute("UPDATE review_requests SET status = 'withdrawn', closed_by = ?, closed_at = ? WHERE id = ?",
                         (by, _now(), request_id))
            self._log(conn, req["learning_id"], "request_withdrawn", by, request_id=request_id)
        return {"learning": self.get(req["learning_id"]), "warnings": []}

    def link(self, from_id: int, to_id: int, type: str, by: str, note: str | None = None) -> dict[str, Any]:
        """Say how one learning relates to another.

        supports: from_id is evidence for to_id.
        builds_on: from_id builds on to_id.
        same_as: the two say the same thing.
        conflicts_with: a person confirms they conflict; both become Contested.
        """
        if type not in LINK_TYPES:
            raise CoreError(f"type must be one of {LINK_TYPES}")
        from_id, to_id = int(from_id), int(to_id)
        if from_id == to_id:
            raise CoreError("a learning cannot be linked to itself")
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            source, target = self._row(conn, from_id), self._row(conn, to_id)
            if type == "conflicts_with":
                if conn.execute("SELECT 1 FROM conflicts WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)",
                                (from_id, to_id, to_id, from_id)).fetchone():
                    raise CoreError(f"#{from_id} and #{to_id} are already flagged as in conflict")
                before = {r["id"]: self._trust(conn, r["id"])["state"] for r in (source, target)}
                conn.execute("INSERT INTO conflicts (a, b, by, at, note) VALUES (?, ?, ?, ?, ?)",
                             (from_id, to_id, by, _now(), _clean(note)))
                for r, other in ((source, to_id), (target, from_id)):
                    self._log(conn, r["id"], "conflict_flagged", by, r["study_id"], **{"with": other}, note=_clean(note))
                    self._retrust(conn, r["id"], before[r["id"]], by, "conflict")
            elif type == "supports":
                evidence = json.loads(target["evidence"])
                if from_id in evidence:
                    raise CoreError(f"#{from_id} already supports #{to_id}")
                conn.execute("UPDATE learnings SET evidence = ? WHERE id = ?",
                             (json.dumps(sorted(evidence + [from_id])), to_id))
                self._built_on(conn, by, from_id, "evidence")
            else:
                if conn.execute(
                    "SELECT 1 FROM links WHERE type = ? AND ((from_id = ? AND to_id = ?) "
                    "OR (type = 'same_as' AND from_id = ? AND to_id = ?))",
                    (type, from_id, to_id, to_id, from_id),
                ).fetchone():
                    raise CoreError(f"#{from_id} and #{to_id} are already linked that way")
                conn.execute("INSERT INTO links (from_id, to_id, type, by, at, note) VALUES (?, ?, ?, ?, ?, ?)",
                             (from_id, to_id, type, by, _now(), _clean(note)))
                if type == "builds_on":
                    self._built_on(conn, by, to_id, "builds_on")
            if type != "conflicts_with":
                for lid in (from_id, to_id):
                    self._log(conn, lid, "linked", by, type=type, source=from_id, target=to_id, note=_clean(note))
        return {"learnings": [self.get(from_id), self.get(to_id)], "warnings": []}

    def check_conflict(self, statement: str | None = None, learning_id: int | None = None) -> dict[str, Any]:
        """Find checked (or already contested) learnings on a similar topic that
        may conflict with this one. Contested ones are included so a third
        conflicting learning still surfaces.

        Pass a statement (to check before adding) or the id of a learning.
        Returns candidates for a person to judge; nothing changes. To flag a
        real conflict, link the two with type conflicts_with.
        """
        with self._conn() as conn:
            if learning_id is not None:
                statement = self._row(conn, learning_id)["statement"]
            statement = self._require(statement, "statement")
            candidates = []
            for row in conn.execute("SELECT * FROM learnings WHERE stage = 'shared' ORDER BY id DESC").fetchall():
                if row["id"] == learning_id:
                    continue
                score, shared = similarity(statement, row["statement"])
                if score < SIMILARITY_THRESHOLD or len(shared) < MIN_SHARED_WORDS:
                    continue
                if self._trust(conn, row["id"])["state"] not in CHECKED + ("contested",):
                    continue
                signals = contradiction_signals(statement, row["statement"])
                candidates.append({"learning": self._brief(conn, row), "similarity": round(score, 2),
                                   "shared_words": sorted(shared), "signals": signals,
                                   "likely_conflict": bool(signals)})
        candidates.sort(key=lambda c: (not c["likely_conflict"], -c["similarity"]))
        return {"statement": statement, "learning_id": learning_id, "candidates": candidates}

    def working_on(self, learning_id: int, who: str, on: bool = True) -> dict[str, Any]:
        """Say you are working on a learning, or that you stopped. A soft hold:
        it never stops anyone else."""
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            who = self._person(conn, who, "who")
            warnings = []
            if row["working_by"] and row["working_by"] != who:
                warnings.append(f"{row['working_by']} was working on #{learning_id}")
            conn.execute("UPDATE learnings SET working_by = ?, working_at = ? WHERE id = ?",
                         (who if on else None, _now() if on else None, learning_id))
            self._log(conn, learning_id, "working_on", who, on=bool(on))
        return {"learning": self.get(learning_id), "warnings": warnings}

    def follow(self, learning_id: int, who: str, on: bool = True) -> dict[str, Any]:
        """Hear about changes to a learning. Owning, reviewing, or using one in
        a decision follows it already."""
        with self._conn() as conn:
            self._row(conn, learning_id)
            who = self._person(conn, who, "who")
            if on:
                if conn.execute("INSERT OR IGNORE INTO follows (name, learning_id, at) VALUES (?, ?, ?)",
                                (who, learning_id, _now())).rowcount:
                    self._log(conn, learning_id, "followed", who)
            else:
                conn.execute("DELETE FROM follows WHERE name = ? AND learning_id = ?", (who, learning_id))
        return {"learning": self.get(learning_id), "following": bool(on), "warnings": []}

    # -- studies -----------------------------------------------------------

    def _study_needs(self, study: dict[str, Any]) -> list[dict[str, str]]:
        """What the study's current stage asks for that is still empty."""
        needs = []
        for stage in STAGE_ASKS[study["status"]]:
            for key, label in STUDY_ASKS[stage]:
                if not study.get(key):
                    needs.append({"key": key, "label": label, "stage": stage})
            for f in self.config["study"]["fields"]:
                if f["ask_at"] == stage and not study["fields"].get(f["key"]):
                    needs.append({"key": f"field:{f['key']}", "label": f["label"], "stage": stage,
                                  "required": f["required"]})
        return needs

    def _study_warnings(self, study: dict[str, Any]) -> list[str]:
        """Gentle nudges for what this stage asks for. Never blocks."""
        return [f"{n['label']} is empty" for n in study["needs"] if n.get("required", True)]

    def _study_full(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        study = dict(row)
        study["fields"] = json.loads(row["fields"])
        learnings = [self._full(conn, r) for r in conn.execute(
            "SELECT * FROM learnings WHERE study_id = ? AND stage != 'replaced' ORDER BY id", (row["id"],))]
        drow = conn.execute("SELECT * FROM decisions WHERE id = ?", (row["from_decision_id"],)).fetchone()
        study["from_decision"] = {k: drow[k] for k in ("id", "title", "made_by", "at")} if drow else None
        study["by_level"] = {lv: [x for x in learnings if x["level"] == lv] for lv in LEVELS}
        study["learning_count"] = len(learnings)
        study["needs"] = self._study_needs(study)
        study["history"] = list(reversed(self._events(conn, "e.study_id = ? AND e.learning_id IS NULL", (row["id"],))))
        return study

    def get_study(self, study_id: int) -> dict[str, Any]:
        """A study: its question, the decision it serves, how it was run, its
        learnings by level, and what its current stage still asks for."""
        with self._conn() as conn:
            return self._study_full(conn, self._study_row(conn, study_id))

    def list_studies(self, status: str | None = None, owner: str | None = None) -> list[dict[str, Any]]:
        if status and status not in STUDY_STAGES:
            raise CoreError(f"status must be one of {STUDY_STAGES}")
        sql, args = "SELECT * FROM studies WHERE 1=1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if owner:
            sql += " AND owner = ? COLLATE NOCASE"
            args.append(owner.strip())
        with self._conn() as conn:
            out = []
            for r in conn.execute(sql + " ORDER BY id DESC", args).fetchall():
                study = dict(r)
                study["fields"] = json.loads(r["fields"])
                study["learning_count"] = conn.execute(
                    "SELECT COUNT(*) FROM learnings WHERE study_id = ? AND stage != 'replaced'", (r["id"],)).fetchone()[0]
                study["needs"] = self._study_needs(study)
                counts = {k: 0 for k in CHECK_LABEL}
                for r2 in conn.execute("SELECT * FROM learnings WHERE study_id = ? AND stage != 'replaced'", (r["id"],)):
                    counts[self._check(conn, r2)["state"]] += 1
                study["counts"] = counts
                study["package"] = json.loads(r["package"])
                study["plan"] = self._plan_progress(self._plan(conn, r["id"], known=False))
                out.append(study)
        return out

    def start_study(
        self,
        question: str,
        owner: str,
        decision: str | None = None,
        hypothesis: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a study with the question and the decision it serves. The rest
        is asked for when the study reaches the stage that needs it."""
        question = self._require(question, "question")
        with self._conn() as conn:
            owner = self._person(conn, owner, "owner")
            cur = conn.execute(
                "INSERT INTO studies (question, decision, hypothesis, status, owner, fields, created_at) "
                "VALUES (?, ?, ?, 'planned', ?, ?, ?)",
                (question, _clean(decision), _clean(hypothesis), owner, json.dumps(_clean_fields(fields)), _now()),
            )
            sid = cur.lastrowid
            self._log(conn, None, "study_started", owner, sid)
        study = self.get_study(sid)
        return {"study": study, "warnings": self._study_warnings(study)}

    def ask_for_research(
        self,
        question: str,
        by: str,
        decision: str | None = None,
        from_decision_id: int | None = None,
        from_query: str | None = None,
    ) -> dict[str, Any]:
        """Ask a research question. It lands as a Requested study for someone to
        pick up. Link where it came from: a decision whose outcome raised it
        (from_decision_id), or a search that found nothing checked (from_query)."""
        question = self._require(question, "question")
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            if from_decision_id is not None:
                drow = self._decision_row(conn, int(from_decision_id))
                from_decision_id = drow["id"]
                decision = _clean(decision) or drow["title"]
            cur = conn.execute(
                "INSERT INTO studies (question, decision, status, requested_by, from_decision_id, from_query, created_at) "
                "VALUES (?, ?, 'requested', ?, ?, ?, ?)",
                (question, _clean(decision), by, from_decision_id, _clean(from_query), _now()),
            )
            sid = cur.lastrowid
            self._log(conn, None, "research_asked", by, sid, from_decision_id, from_query=_clean(from_query))
        study = self.get_study(sid)
        warnings = [] if study["decision"] else ["say which decision this would inform, so it can be prioritized"]
        return {"study": study, "warnings": warnings}

    def update_study(self, study_id: int, by: str, **changes: Any) -> dict[str, Any]:
        """Change a study's details, stage (status), or owner. Template fields
        are merged. Previous values stay in its history. The result lists what
        the new stage asks for."""
        allowed = set(STUDY_TEXT) | {"status", "owner", "fields"}
        unknown = set(changes) - allowed
        if unknown:
            raise CoreError(f"cannot update {sorted(unknown)}; choose from {sorted(allowed)}")
        if "status" in changes and changes["status"] not in STUDY_STAGES:
            raise CoreError(f"status must be one of {STUDY_STAGES}")
        if "question" in changes:
            changes["question"] = self._require(changes["question"], "question")
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
                conn.execute(f"UPDATE studies SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                             (*updates.values(), study_id))
                self._log(conn, None, "study_updated", by, study_id, changed=sorted(updates), previous=previous,
                          status=updates.get("status"))
        study = self.get_study(study_id)
        return {"study": study, "warnings": self._study_warnings(study)}

    # -- the workbench ----------------------------------------------------

    def _base(self, conn, study: sqlite3.Row) -> list[dict[str, Any]]:
        """The four parts every block rests on, and whether each is in place.
        The plan is in place once the question, the decision, and at least one
        sub-question are set."""
        n = conn.execute("SELECT COUNT(*) FROM sources WHERE study_id = ?", (study["id"],)).fetchone()[0]
        q = conn.execute("SELECT COUNT(*) FROM questions WHERE study_id = ?", (study["id"],)).fetchone()[0]
        return [
            {"key": "plan", "label": "The plan", "count": q,
             "ok": bool(study["question"] and study["decision"] and q)},
            {"key": "context", "label": "Context", "ok": n >= 2, "count": n},
            {"key": "method", "label": "Method and approach", "ok": bool(study["method"])},
            {"key": "notes", "label": "Notes", "ok": bool(study["notes"])},
        ]

    def get_workspace(self, study_id: int) -> dict[str, Any]:
        """Everything the workbench draws for one workspace: the question and
        decision, the plan (sub-questions, how far each has got, and what other
        workspaces already know), the base (context, method, notes), the
        sources, every current block with its check state and what it rests
        on, and the package."""
        with self._conn() as conn:
            row = self._study_row(conn, study_id)
            blocks = [self._block(conn, r) for r in conn.execute(
                "SELECT * FROM learnings WHERE study_id = ? AND stage != 'replaced' ORDER BY id", (study_id,))]
            sources = [dict(r) for r in conn.execute("SELECT * FROM sources WHERE study_id = ? ORDER BY id", (study_id,))]
            base = self._base(conn, row)
            plan = self._plan(conn, row["id"])
        counts = {k: 0 for k in CHECK_LABEL}
        for b in blocks:
            counts[b["check"]["state"]] += 1
        live = {b["id"] for b in blocks}
        return {"id": row["id"], "question": row["question"], "decision": row["decision"], "method": row["method"],
                "notes": row["notes"], "owner": row["owner"], "status": row["status"], "base": base,
                "plan": plan, "sources": sources, "blocks": blocks, "counts": counts,
                "package": [i for i in json.loads(row["package"]) if i in live]}

    # -- the plan ---------------------------------------------------------

    def _question_row(self, conn, question_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (int(question_id),)).fetchone()
        if row is None:
            raise CoreError(f"sub-question {question_id} does not exist")
        return row

    def _answers(self, conn, level: str, study_id, question_id) -> int | None:
        """Check that a block can answer this sub-question: it is a finding or
        insight in the same workspace."""
        if question_id in (None, ""):
            return None
        q = self._question_row(conn, question_id)
        if level not in ANSWER_LEVELS:
            raise CoreError("only a finding or an insight answers a sub-question")
        if study_id is None or int(study_id) != q["study_id"]:
            raise CoreError(f"sub-question {q['id']} belongs to another workspace")
        return q["id"]

    def _known(self, conn, text: str, study_id: int, limit: int = 3) -> list[dict[str, Any]]:
        """Blocks from other workspaces that speak to a sub-question, most
        checked first. Drafts stay out until their owner has checked them."""
        rank = {"checked_by_sme": 0, "checked_by_peers": 1, "checked_by_owner": 2}
        found = []
        for row in conn.execute("SELECT * FROM learnings WHERE stage = 'shared' "
                                "AND (study_id IS NULL OR study_id != ?)", (study_id,)).fetchall():
            score, shared = similarity(text, row["statement"])
            if score < SIMILARITY_THRESHOLD or len(shared) < MIN_SHARED_WORDS:
                continue
            check = self._check(conn, row)
            srow = conn.execute("SELECT id, question FROM studies WHERE id = ?", (row["study_id"],)).fetchone()
            found.append({**self._brief(conn, row), "check": check, "similarity": round(score, 2),
                          "workspace": dict(srow) if srow else None})
        found.sort(key=lambda b: (rank.get(b["check"]["state"], 3), -b["similarity"], -b["id"]))
        return found[:limit]

    def _plan(self, conn, study_id: int, known: bool = True) -> list[dict[str, Any]]:
        """Each sub-question, the current blocks that answer it, and its state."""
        out = []
        for q in conn.execute("SELECT * FROM questions WHERE study_id = ? ORDER BY position, id", (study_id,)):
            rows = conn.execute("SELECT * FROM learnings WHERE question_id = ? AND stage != 'replaced' ORDER BY id",
                                (q["id"],)).fetchall()
            checks = {r["id"]: self._check(conn, r)["state"] for r in rows}
            answered_by = [r["id"] for r in rows if r["level"] == "insight" and checks[r["id"]] in CHECKED]
            state = "answered" if answered_by else "in_progress" if rows else "open"
            item = {"id": q["id"], "text": q["text"], "expect": q["expect"], "position": q["position"],
                    "added_by": q["added_by"], "state": state, "label": PLAN_LABEL[state],
                    "block_ids": [r["id"] for r in rows], "answered_by": answered_by}
            if known:
                item["already_known"] = self._known(conn, q["text"], study_id)
            out.append(item)
        return out

    @staticmethod
    def _plan_progress(plan: list[dict[str, Any]]) -> dict[str, Any]:
        done = sum(q["state"] == "answered" for q in plan)
        return {"total": len(plan), "answered": done,
                "label": f"{done} of {len(plan)} answered" if plan else "No sub-questions yet"}

    def _plan_result(self, conn, study_id: int, **extra) -> dict[str, Any]:
        plan = self._plan(conn, study_id)
        warnings = extra.pop("warnings", [])
        if len(plan) > PLAN_SIZE:
            warnings.append(f"the plan has {len(plan)} sub-questions; a few sharp ones are easier to answer")
        return {**extra, "plan": plan, "progress": self._plan_progress(plan), "warnings": warnings}

    def add_question(self, study_id: int, by: str, text: str, expect: str | None = None) -> dict[str, Any]:
        """Add a sub-question to a workspace's plan: something we need to know
        to make the decision. expect says what we think we will find, if
        anything. The result shows the plan, with what other workspaces
        already know about each sub-question."""
        text = self._require(text, "text")
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            self._study_row(conn, study_id)
            pos = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM questions WHERE study_id = ?",
                               (study_id,)).fetchone()[0]
            cur = conn.execute("INSERT INTO questions (study_id, text, expect, position, added_by, at) "
                               "VALUES (?, ?, ?, ?, ?, ?)", (study_id, text, _clean(expect), pos, by, _now()))
            self._log(conn, None, "question_added", by, study_id, question_id=cur.lastrowid, text=text)
            question = dict(self._question_row(conn, cur.lastrowid))
            return self._plan_result(conn, study_id, question=question)

    def update_question(self, question_id: int, by: str, text: str | None = None, expect: str | None = None,
                        position: int | None = None) -> dict[str, Any]:
        """Change a sub-question's wording, what we expect, or its place in the
        plan (position, starting at 1). The earlier wording stays in the history."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            q = self._question_row(conn, question_id)
            changes = {}
            if text is not None:
                changes["text"] = self._require(text, "text")
            if expect is not None:
                changes["expect"] = _clean(expect)
            changes = {k: v for k, v in changes.items() if v != q[k]}
            if changes:
                conn.execute(f"UPDATE questions SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                             (*changes.values(), q["id"]))
            if position is not None:
                ids = [r[0] for r in conn.execute("SELECT id FROM questions WHERE study_id = ? ORDER BY position, id",
                                                  (q["study_id"],))]
                ids.remove(q["id"])
                ids.insert(max(0, min(int(position) - 1, len(ids))), q["id"])
                for i, qid in enumerate(ids, 1):
                    conn.execute("UPDATE questions SET position = ? WHERE id = ?", (i, qid))
                changes["position"] = position
            if changes:
                self._log(conn, None, "question_changed", by, q["study_id"], question_id=q["id"],
                          text=changes.get("text", q["text"]), changed=sorted(changes),
                          previous={k: q[k] for k in changes})
            question = dict(self._question_row(conn, q["id"]))
            return self._plan_result(conn, q["study_id"], question=question)

    def remove_question(self, question_id: int, by: str) -> dict[str, Any]:
        """Take a sub-question out of the plan. Blocks that answered it stay,
        and no longer answer anything. The history keeps what it said."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            q = self._question_row(conn, question_id)
            untagged = [r[0] for r in conn.execute("SELECT id FROM learnings WHERE question_id = ?", (q["id"],))]
            conn.execute("UPDATE learnings SET question_id = NULL WHERE question_id = ?", (q["id"],))
            conn.execute("DELETE FROM questions WHERE id = ?", (q["id"],))
            self._log(conn, None, "question_removed", by, q["study_id"], question_id=q["id"], text=q["text"],
                      expect=q["expect"], untagged=untagged)
            return self._plan_result(conn, q["study_id"], removed=q["id"], untagged=untagged)

    def set_answers(self, learning_id: int, by: str, question_id: int | None = None) -> dict[str, Any]:
        """Say which sub-question a finding or insight answers, or none (leave
        question_id out). Anyone can. It is not a check, so the block's check
        state does not change."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            row = self._row(conn, learning_id)
            if row["stage"] == "replaced":
                raise CoreError(f"#{learning_id} was replaced by a newer version; use that one")
            qid = self._answers(conn, row["level"], row["study_id"], question_id)
            if qid != row["question_id"]:
                conn.execute("UPDATE learnings SET question_id = ? WHERE id = ?", (qid, learning_id))
                text = self._question_row(conn, qid)["text"] if qid else None
                self._log(conn, learning_id, "answers_set", by, row["study_id"], question_id=qid, question=text,
                          previous=row["question_id"])
            return self._plan_result(conn, row["study_id"], learning=self._block(conn, self._row(conn, learning_id)))

    def already_known(self, question_id: int, limit: int = 3) -> dict[str, Any]:
        """Blocks from other workspaces that already speak to a sub-question,
        most checked first, matched on shared words. Read only: it shows what
        the team knows before anyone builds something new."""
        with self._conn() as conn:
            q = self._question_row(conn, question_id)
            return {"question": dict(q), "blocks": self._known(conn, q["text"], q["study_id"], int(limit))}

    def needs_check(self, who: str, study_id: int | None = None) -> dict[str, Any]:
        """Blocks waiting on a person's check, most pressing first: their AI
        drafts, their blocks with changes asked, blocks someone asked them to
        check, then blocks only their owner has checked so far."""
        with self._conn() as conn:
            who = self._person(conn, who, "who")
            me = self._who(conn, who)
            where, args = "stage = 'shared' AND owner != ?", [who]
            if study_id is not None:
                where += " AND study_id = ?"
                args.append(int(study_id))
            items, seen = [], set()

            def put(row, why):
                if row["id"] not in seen:
                    seen.add(row["id"])
                    items.append({**self._block(conn, row), "reason": why})

            mine = "owner = ?" + (" AND study_id = ?" if study_id is not None else "")
            mine_args = [who] + ([int(study_id)] if study_id is not None else [])
            for r in conn.execute(f"SELECT * FROM learnings WHERE {mine} AND stage = 'draft' ORDER BY id", mine_args):
                put(r, "Your AI draft to check")
            for r in conn.execute(f"SELECT * FROM learnings WHERE {mine} AND stage = 'shared' ORDER BY id", mine_args):
                if self._check(conn, r)["state"] == "needs_changes":
                    put(r, "Changes asked on your block")
            for r in conn.execute(
                f"SELECT l.* FROM learnings l JOIN review_requests q ON q.learning_id = l.id WHERE q.status = 'open' "
                f"AND (q.person = ? OR q.role = ? OR (q.role = 'sme' AND ?)) AND l.{where.replace(' AND ', ' AND l.')} "
                "ORDER BY q.id", [who, me["role"], me["sme"], *args],
            ):
                put(r, "Someone asked you to check this")
            for r in conn.execute(f"SELECT * FROM learnings WHERE {where} ORDER BY id", args):
                if self._check(conn, r)["state"] == "checked_by_owner":
                    put(r, "Nobody else has checked this yet")
        return {"who": who, "items": items}

    def add_source(self, study_id: int, by: str, title: str, body: str, kind: str = "note",
                   url: str | None = None) -> dict[str, Any]:
        """Add context to a workspace: a note, quote, data, query, link, file
        text, or pasted AI text (ai_text). Observations cite it."""
        title, body = self._require(title, "title"), self._require(body, "body")
        if kind not in SOURCE_KINDS:
            raise CoreError(f"kind must be one of {SOURCE_KINDS}")
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            self._study_row(conn, study_id)
            cur = conn.execute(
                "INSERT INTO sources (study_id, kind, title, body, url, added_by, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (study_id, kind, title, body, _clean(url), by, _now()))
            self._log(conn, None, "source_added", by, study_id, source_id=cur.lastrowid, title=title, source_kind=kind)
            source = dict(conn.execute("SELECT * FROM sources WHERE id = ?", (cur.lastrowid,)).fetchone())
        return {"source": source, "warnings": []}

    def check(self, learning_id: int, by: str, verdict: str = "looks_right", how: str | None = None,
              note: str | None = None, statement: str | None = None) -> dict[str, Any]:
        """Check a block: looks_right, needs_changes, or disagree.

        The one action people take on a block. The owner of an AI draft checks
        it first (and may fix the wording), which is the same as confirm. When
        changes were asked, the owner answers by changing the wording, which
        writes a new version. Anyone else gives a review, with how they checked.
        """
        if verdict not in CHECK_VERDICTS:
            raise CoreError(f"verdict must be one of {tuple(CHECK_VERDICTS)}")
        with self._conn() as conn:
            row = self._row(conn, learning_id)
            by = self._person(conn, by, "by")
            state = self._check(conn, row)["state"]
        new = (statement or "").strip()
        changed = bool(new) and new != row["statement"]
        if state == "replaced":
            raise CoreError(f"#{learning_id} was replaced by a newer version; check that one")
        if by != row["owner"]:
            if row["stage"] == "draft":
                raise CoreError(f"{row['owner']} checks this AI draft first")
            return self.review(learning_id, by, CHECK_VERDICTS[verdict], how, note)
        if verdict != "looks_right":
            raise CoreError("this is your block: change the wording instead")
        if row["stage"] == "draft":
            return self.confirm(learning_id, by, new or None, note)
        if changed:
            return self.revise(learning_id, by, new, note)
        if state == "needs_changes":
            raise CoreError("changes were asked for: change the wording to answer them")
        raise CoreError("you already stand behind this; someone else can check it next")

    def add_blocks(self, study_id: int, by: str, blocks: list[dict[str, Any]], origin: str = "ai_agent") -> dict[str, Any]:
        """Add many blocks to a workspace at once, the way an AI tool breaks a
        piece of work into parts. Each item has a level and statement, and can
        have: ref (a name later items can build on), sources (source ids),
        built_on (block ids or earlier refs), answers (a sub-question id, for a
        finding or insight), confidence, why, and assumes.
        Everything made with AI arrives as a draft for its owner to check."""
        if not isinstance(blocks, list) or not blocks:
            raise CoreError("give at least one block")
        refs: dict[str, int] = {}
        known: set[str] = set()
        for i, b in enumerate(blocks):  # check every ref before writing anything
            if not isinstance(b, dict):
                raise CoreError(f"block {i + 1} must be an object")
            for x in b.get("built_on") or []:
                if isinstance(x, str) and not x.isdigit() and x not in known:
                    raise CoreError(f"block {i + 1} builds on '{x}', which is not an earlier ref")
            known.add(str(b.get("ref") or i + 1))
        made, warnings = [], []
        for i, b in enumerate(blocks):
            built = [refs[x] if isinstance(x, str) and x in refs else int(x) for x in b.get("built_on") or []]
            out = self.add(b.get("statement"), b.get("level"), by, built, study_id, origin,
                           b.get("sources"), b.get("confidence"), b.get("why"), b.get("assumes"), b.get("answers"))
            refs[str(b.get("ref") or i + 1)] = out["learning"]["id"]
            made.append(out["learning"]["id"])
            warnings += [f"#{out['learning']['id']}: {w}" for w in out["warnings"] if "is a draft until" not in w]
        return {"ids": made, "refs": refs, "warnings": warnings}

    def break_down(self, study_id: int, by: str, text: str, title: str | None = None,
                   preview: bool = False, blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Take a long piece of AI text apart into blocks, so each claim can be
        checked on its own. A simple built-in splitter, with no AI and nothing
        sent anywhere: the text is kept as a source, each sentence becomes a
        draft block, and a level is guessed from its words. Observations cite
        the text. Findings and insights are left built on nothing, which is the
        point: it shows which claims the text never supported. Hedges and
        sweeping words are listed as what the block assumes. Your AI tool can
        do a better job with add_blocks.

        With preview, nothing is written: you get the pieces, so a person can
        fix a level or the wording, or drop a piece, first. Pass the pieces they
        keep back as blocks (each a statement and a level) to add exactly those."""
        text = self._require(text, "text")
        if blocks is None:
            pieces = [{"statement": p, "level": _guess_level(p)} for p in _split_claims(text)]
        else:
            pieces = []
            for i, b in enumerate(blocks):
                if not isinstance(b, dict):
                    raise CoreError(f"block {i + 1} must be an object")
                level = b.get("level")
                if level not in LEVELS:
                    raise CoreError(f"block {i + 1}: level must be one of {LEVELS}")
                pieces.append({"statement": self._require(b.get("statement"), f"block {i + 1} statement"), "level": level})
        if not pieces:
            raise CoreError("found no claims to take apart; paste sentences, not just headings")
        for p in pieces:
            p["assumes"] = _assumptions(p["statement"])
            p["rests_on_nothing"] = p["level"] != "observation"
        nothing = sum(p["rests_on_nothing"] for p in pieces)
        warnings = [f"{nothing} of {len(pieces)} claims rest on nothing in the text"] if nothing else []
        if preview:
            with self._conn() as conn:
                self._person(conn, by, "by")
                self._study_row(conn, study_id)
            return {"pieces": pieces, "warnings": warnings}
        src = self.add_source(study_id, by, title or "Pasted AI text", text, "ai_text")["source"]
        made = []
        for p in pieces:
            out = self.add(p["statement"], p["level"], by, None, study_id, "ai_agent",
                           [src["id"]] if p["level"] == "observation" else None, None,
                           "Split from pasted AI text. The AI did not say how sure it was.", p["assumes"])
            made.append(out["learning"]["id"])
        with self._conn() as conn:
            made_blocks = [self._block(conn, self._row(conn, i)) for i in made]
        return {"source": src, "ids": made, "blocks": made_blocks, "warnings": warnings}

    def set_package(self, study_id: int, by: str, learning_ids: list[int]) -> dict[str, Any]:
        """Choose the insights a workspace shares together, in order. Only
        insights from this workspace can go in."""
        ids = []
        for x in learning_ids or []:
            if int(x) not in ids:
                ids.append(int(x))
        warnings = []
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            self._study_row(conn, study_id)
            for lid in ids:
                row = self._row(conn, lid)
                if row["study_id"] != int(study_id) or row["level"] != "insight" or row["stage"] == "replaced":
                    raise CoreError(f"#{lid} is not a current insight in this workspace")
                state = self._check(conn, row)["state"]
                if state in UNCHECKED:
                    warnings.append(f"#{lid} is {CHECK_LABEL[state]}")
            conn.execute("UPDATE studies SET package = ? WHERE id = ?", (json.dumps(ids), study_id))
            self._log(conn, None, "package_set", by, study_id, package=ids)
        return {"package": ids, "warnings": warnings}

    # -- decisions ---------------------------------------------------------

    def _use(self, conn, decision_id: int, rows: list[sqlite3.Row], by: str) -> list[str]:
        warnings = []
        for row in rows:
            state = self._trust(conn, row["id"])["state"]
            if conn.execute("INSERT OR IGNORE INTO decision_uses (decision_id, learning_id, trust_at_use) "
                            "VALUES (?, ?, ?)", (decision_id, row["id"], state)).rowcount:
                self._log(conn, row["id"], "used_in_decision", by, None, decision_id)
            if row["stage"] == "draft":
                warnings.append(f"#{row['id']} is still a draft")
            elif row["stage"] == "replaced":
                warnings.append(f"#{row['id']} was replaced by a newer version")
            elif state not in CHECKED:
                warnings.append(f"#{row['id']} is {TRUST_LABEL[state]}")
        # Everyone in the chain hears their work was used. Once per decision.
        title = self._decision_row(conn, decision_id)["title"]
        for c in self._credits(conn, [r["id"] for r in rows]):
            self._moment(conn, "used", by, c["name"], f"{by} used your work in \"{title}\".",
                         decision_id=decision_id, key=f"used:{decision_id}:{c['name'].lower()}")
        self._milestone_team(conn, by)
        return warnings

    def log_decision(
        self, title: str, made_by: str, learning_ids: list[int] | None = None, note: str | None = None
    ) -> dict[str, Any]:
        """Record a decision and the learnings it relied on, in one step. What
        happened is asked for later, once it is known (update_decision).

        Using a learning that is not checked yet, or is contested, is allowed
        and comes back as a warning, so the record stays honest."""
        title = self._require(title, "title")
        ids = list(dict.fromkeys(int(x) for x in (learning_ids or [])))
        with self._conn() as conn:
            made_by = self._person(conn, made_by, "made_by")
            rows = [self._row(conn, lid) for lid in ids]
            cur = conn.execute("INSERT INTO decisions (title, made_by, at, note) VALUES (?, ?, ?, ?)",
                               (title, made_by, _now(), _clean(note)))
            did = cur.lastrowid
            self._log(conn, None, "decision_logged", made_by, None, did, learning_ids=ids)
            warnings = self._use(conn, did, rows, made_by)
        if not ids:
            warnings.append("no learnings linked; if nothing checked exists yet, ask for research")
        return {"decision": self.get_decision(did), "warnings": warnings}

    def update_decision(
        self,
        decision_id: int,
        by: str,
        outcome: str | None = None,
        note: str | None = None,
        add_learning_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Add what happened (outcome), a note, or more learnings it relied on."""
        with self._conn() as conn:
            by = self._person(conn, by, "by")
            row = self._decision_row(conn, decision_id)
            changes = {}
            for key, value in (("outcome", outcome), ("note", note)):
                if value is not None and _clean(value) != row[key]:
                    changes[key] = _clean(value)
            if "outcome" in changes:
                changes["outcome_at"] = _now()
            if changes:
                conn.execute(f"UPDATE decisions SET {', '.join(f'{k} = ?' for k in changes)} WHERE id = ?",
                             (*changes.values(), decision_id))
                self._log(conn, None, "decision_updated", by, None, decision_id,
                          changed=sorted(k for k in changes if k != "outcome_at"),
                          previous={k: row[k] for k in changes if k != "outcome_at"})
            rows = [self._row(conn, int(x)) for x in (add_learning_ids or [])]
            warnings = self._use(conn, decision_id, rows, by) if rows else []
        return {"decision": self.get_decision(decision_id), "warnings": warnings}

    def _outcome_due(self, row: sqlite3.Row) -> bool:
        if row["outcome"]:
            return False
        due = datetime.fromisoformat(row["at"]) + timedelta(days=self.config["outcome_after_days"])
        return datetime.now(timezone.utc) >= due

    def _decision_full(self, conn, row: sqlite3.Row, with_credits: bool = True) -> dict[str, Any]:
        decision = dict(row)
        used = []
        for u in conn.execute("SELECT * FROM decision_uses WHERE decision_id = ? ORDER BY learning_id", (row["id"],)):
            lrow = self._row(conn, u["learning_id"])
            trust = self._trust(conn, lrow["id"])
            used.append({**self._brief(conn, lrow), "trust_at_use": u["trust_at_use"],
                         "trust_at_use_label": TRUST_LABEL.get(u["trust_at_use"], u["trust_at_use"]),
                         "trust": trust["summary"], "state": trust["state"]})
        decision["learnings"] = used
        # A decision is at risk when something it relied on is now contested.
        decision["at_risk"] = [x["id"] for x in used if x["state"] == "contested"]
        decision["outcome_due"] = self._outcome_due(row)
        decision["requests"] = [
            {k: r[k] for k in ("id", "question", "status", "owner", "requested_by")}
            for r in conn.execute("SELECT * FROM studies WHERE from_decision_id = ? ORDER BY id", (row["id"],))
        ]
        if with_credits:
            decision["credits"] = self._credits(conn, [x["id"] for x in used])
        return decision

    def _credits(self, conn, learning_ids: list[int]) -> list[dict[str, Any]]:
        """Everyone in the chain behind these learnings, and what they did.

        Walks each learning's evidence, revisions, and promotions back to the
        start. Reviewers who asked for changes or disagreed are credited too:
        catching a problem is part of getting it right. Listed by name, never
        ranked: this shows the collaboration behind a decision.
        """
        seen: set[int] = set()
        credit: dict[str, list[dict[str, Any]]] = {}

        def add(name, what, **ref):
            items = credit.setdefault(name, [])
            item = {"did": what, **ref}
            if item not in items:
                items.append(item)

        stack = list(learning_ids)
        while stack:
            lid = stack.pop()
            if lid in seen:
                continue
            seen.add(lid)
            row = self._row(conn, lid)
            add(row["owner"], "added", learning_id=lid)
            for r in self._current_reviews(conn, lid):
                add(r["by"], CREDIT_FOR[r["verdict"]], learning_id=lid)
            if row["study_id"]:
                study = self._study_row(conn, row["study_id"])
                if study["owner"]:
                    add(study["owner"], "ran the study", study_id=study["id"])
            stack.extend(json.loads(row["evidence"]))
            stack.extend(x for x in (row["promoted_from"], row["revises"]) if x)
        out = []
        for name in sorted(credit, key=str.lower):
            items = sorted(credit[name], key=lambda c: (c.get("study_id") is None, c.get("learning_id") or 0))
            out.append({**self._person_dict(self._who(conn, name)), "contributions": items})
        return out

    def get_decision(self, decision_id: int) -> dict[str, Any]:
        """A decision, the learnings it relied on (trust now and when used),
        what is at risk, whether its outcome is due, research it raised, and
        everyone behind it."""
        with self._conn() as conn:
            return self._decision_full(conn, self._decision_row(conn, decision_id))

    def list_decisions(self, made_by: str | None = None) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM decisions", []
        if made_by:
            sql += " WHERE made_by = ? COLLATE NOCASE"
            args.append(made_by.strip())
        with self._conn() as conn:
            return [self._decision_full(conn, r, with_credits=False)
                    for r in conn.execute(sql + " ORDER BY id DESC", args).fetchall()]

    # -- what is waiting, and what changed ---------------------------------

    def my_queue(self, who: str) -> dict[str, Any]:
        """What is waiting on a person.

        waiting_on_me: learnings someone asked this person, their role, or any
        SME (if they are one) to review.
        drafts: their AI drafts to confirm.
        feedback_on_mine: their shared learnings where a current review asks
        for changes or disagrees.
        my_requests: review requests they made that are still open.
        decisions_at_risk and outcomes_due: their decisions that need a look.
        """
        with self._conn() as conn:
            who = self._person(conn, who, "who")
            me = self._who(conn, who)
            waiting = []
            for req in conn.execute(
                "SELECT r.* FROM review_requests r JOIN learnings l ON l.id = r.learning_id "
                "WHERE r.status = 'open' AND l.owner != ? AND (r.person = ? OR r.role = ? OR (r.role = 'sme' AND ?)) "
                "ORDER BY r.id",
                (who, who, me["role"], me["sme"]),
            ):
                mine = [r for r in self._current_reviews(conn, req["learning_id"]) if r["by"] == who]
                if mine and mine[0]["verdict"] == "approve":
                    continue  # already approved before the request came in
                waiting.append({"request": dict(req), "learning": self._full(conn, self._row(conn, req["learning_id"]))})
            drafts = [self._full(conn, r) for r in conn.execute(
                "SELECT * FROM learnings WHERE owner = ? AND stage = 'draft' ORDER BY id", (who,))]
            feedback = []
            for row in conn.execute("SELECT * FROM learnings WHERE owner = ? AND stage = 'shared' ORDER BY id DESC", (who,)):
                concerns = [dict(r) for r in self._current_reviews(conn, row["id"]) if r["verdict"] != "approve"]
                if concerns:
                    feedback.append({"learning": self._full(conn, row), "reviews": concerns})
            asked = [{"request": dict(r), "learning": self._brief(conn, self._row(conn, r["learning_id"]))}
                     for r in conn.execute("SELECT * FROM review_requests WHERE asked_by = ? AND status = 'open' ORDER BY id",
                                           (who,))]
            decisions = [self._decision_full(conn, r, with_credits=False) for r in conn.execute(
                "SELECT * FROM decisions WHERE made_by = ? ORDER BY id DESC", (who,))]
        return {"who": who, "role": me["role"], "sme": bool(me["sme"]), "waiting_on_me": waiting, "drafts": drafts,
                "feedback_on_mine": feedback, "my_requests": asked,
                "decisions_at_risk": [d for d in decisions if d["at_risk"]],
                "outcomes_due": [d for d in decisions if d["outcome_due"]]}

    @staticmethod
    def _following(conn, who: str) -> dict[int, int]:
        """Learnings a person owns, reviewed, used in a decision, or follows,
        each with the event that started it, so only later changes are news."""
        return {r[0]: r[1] for r in conn.execute(
            "SELECT learning_id, MIN(id) FROM events WHERE learning_id IS NOT NULL AND actor = ? "
            "AND kind IN ('added', 'reviewed', 'used_in_decision', 'followed') GROUP BY learning_id", (who,))}

    def digest(self, who: str, since: str | None = None, limit: int = 30) -> dict[str, Any]:
        """What changed for a person: changes to what they own, reviewed, used
        in a decision, or follow; reviews asked of them; and moments. Ranked by
        importance (1 do now, 2 news, 3 digest only), then newest first.

        Joins, "working on" notes, follows, and other people's plain activity
        are left out. The full record is in activity.
        """
        with self._conn() as conn:
            who = self._person(conn, who, "who")
            me = self._who(conn, who)
            following = self._following(conn, who)
            owned = {r[0] for r in conn.execute("SELECT id FROM learnings WHERE owner = ?", (who,))}
            my_decisions = {r[0] for r in conn.execute("SELECT id FROM decisions WHERE made_by = ?", (who,))}
            my_requests = {r[0] for r in conn.execute("SELECT id FROM studies WHERE requested_by = ?", (who,))}
            seen = {r[0] for r in conn.execute("SELECT key FROM seen WHERE name = ?", (who,))}
            rows = conn.execute(
                "SELECT e.*, l.statement, l.stage, s.question AS study_title, d.title AS decision_title FROM events e "
                "LEFT JOIN learnings l ON l.id = e.learning_id LEFT JOIN studies s ON s.id = e.study_id "
                "LEFT JOIN decisions d ON d.id = e.decision_id WHERE e.actor != ? AND (? IS NULL OR e.at >= ?) "
                "ORDER BY e.id DESC LIMIT 2000",
                (who, since, since),
            ).fetchall()
            # A moment already says it; skip the plain event behind it.
            said = {(r["learning_id"], r["actor"]) for r in rows if r["kind"] == "moment"
                    and json.loads(r["detail"])["to"].lower() == who.lower()}
            items = []
            for r in rows:
                d = json.loads(r["detail"])
                lid, kind = r["learning_id"], r["kind"]
                if kind in ("promoted", "reviewed") and (lid, r["actor"]) in said \
                        and d.get("verdict", "approve") == "approve":
                    continue
                level = None
                if kind == "moment":
                    if d["to"] == "*" or d["to"].lower() == who.lower():
                        level = NEWS
                elif kind == "review_asked":
                    if (d.get("person") or "").lower() == who.lower() or d.get("role") == me["role"] \
                            or (d.get("role") == "sme" and me["sme"]):
                        level = DO_NOW
                elif kind == "decision_at_risk":
                    if r["decision_id"] in my_decisions:
                        level = DO_NOW
                elif kind == "study_updated":
                    if r["study_id"] in my_requests:
                        level = DIGEST
                elif lid in following and r["id"] > following[lid]:
                    if kind == "reviewed" and lid in owned:
                        level = DO_NOW if d["verdict"] != "approve" and r["stage"] == "shared" else NEWS
                    elif kind == "trust_changed" and not (lid in owned and d.get("cause") == "review"):
                        level = NEWS if d["to"] in CHECKED + ("contested",) else DIGEST
                    elif kind in ("revised", "promoted"):
                        level = NEWS
                    elif kind in ("reviewed", "conflict_flagged", "confirmed"):
                        level = DIGEST
                if level is None:
                    continue
                item = self._event(r, who)
                item["importance"] = level
                item["seen"] = f"e{r['id']}" in seen
                items.append(item)
        items.sort(key=lambda x: (x["importance"], -x["id"]))
        return {"who": who, "items": items[:limit]}

    def mark_seen(self, who: str, keys: list[str]) -> dict[str, Any]:
        """Record that a person has seen digest items or moments (keys like
        "e12"), or set a next step aside with "Not now" (its key)."""
        with self._conn() as conn:
            who = self._person(conn, who, "who")
            for key in keys or []:
                conn.execute("INSERT OR IGNORE INTO seen (name, key, at) VALUES (?, ?, ?)", (who, str(key), _now()))
        return {"who": who, "seen": list(keys or []), "warnings": []}

    def next_step(self, who: str) -> dict[str, Any]:
        """The one thing most worth doing now, and the first unseen moment.

        In order: a decision of yours relies on something now contested; a
        review asked of you; your AI drafts to confirm; changes asked on yours;
        a research request waiting (researchers and SMEs); something you use or
        follow changed; your study's next detail; a decision whose outcome is
        due; and when nothing waits, a suggestion for your role. Steps set
        aside with "Not now" are skipped until something new comes up.
        """
        queue = self.my_queue(who)
        who = queue["who"]
        digest = self.digest(who, limit=200)["items"]
        with self._conn() as conn:
            skip = {r[0] for r in conn.execute("SELECT key FROM seen WHERE name = ?", (who,))}
            studies = [self._study_full(conn, r) for r in conn.execute(
                "SELECT * FROM studies WHERE owner = ? AND status IN ('planned', 'running', 'finished') ORDER BY id DESC",
                (who,))]
            requests = conn.execute("SELECT * FROM studies WHERE status = 'requested' ORDER BY id").fetchall() \
                if queue["role"] == "researcher" or queue["sme"] else []

        def step(key, kind, title, text, button, act, **ref):
            return {"key": key, "kind": kind, "title": title, "text": text, "button": button, "act": act, **ref}

        candidates = []
        for d in queue["decisions_at_risk"]:
            for lid in d["at_risk"]:
                x = next(x for x in d["learnings"] if x["id"] == lid)
                candidates.append(step(f"risk:{d['id']}:{lid}", "at_risk", "A decision of yours relies on something now contested",
                                       f"\"{d['title']}\" used #{lid}: \"{_short(x['statement'])}\"", "Take a look",
                                       "open-learning", learning_id=lid, decision_id=d["id"]))
        for w in queue["waiting_on_me"]:
            r, lrn = w["request"], w["learning"]
            candidates.append(step(f"review:{r['id']}", "review", f"{r['asked_by']} asked you to review a learning",
                                   f"\"{_short(lrn['statement'])}\"" + (f" Note: \"{r['note']}\"" if r["note"] else ""),
                                   "Review", "review", learning_id=lrn["id"]))
        for lrn in queue["drafts"]:
            candidates.append(step(f"confirm:{lrn['id']}", "confirm", "Confirm your AI draft",
                                   f"\"{_short(lrn['statement'])}\" Check it before anyone is asked to review it.",
                                   "Confirm", "confirm", learning_id=lrn["id"]))
        for fb in queue["feedback_on_mine"]:
            latest = max(r["id"] for r in fb["reviews"])
            r = next(r for r in fb["reviews"] if r["id"] == latest)
            candidates.append(step(f"revise:{fb['learning']['id']}:{latest}", "revise",
                                   f"{r['by']} {VERDICT_SAID[r['verdict']]} your learning",
                                   f"\"{_short(fb['learning']['statement'])}\"" + (f" They said: \"{r['note']}\"" if r["note"] else ""),
                                   "Revise", "revise", learning_id=fb["learning"]["id"]))
        for s in requests:
            candidates.append(step(f"request:{s['id']}", "request", "A research request is waiting",
                                   f"\"{_short(s['question'])}\" asked by {s['requested_by']}", "Take a look",
                                   "open-study", study_id=s["id"]))
        for e in digest:
            if e["importance"] <= NEWS and not e["seen"] and e["kind"] not in ("moment", "review_asked", "decision_at_risk"):
                candidates.append(step(f"e{e['id']}", "news", "Something you follow changed", e["text"],
                                       "See what changed", "open-learning", learning_id=e["learning_id"]))
        for s in studies:
            if s["needs"]:
                label = ", ".join(n["label"].lower() for n in s["needs"])
                candidates.append(step(f"study:{s['id']}:{s['status']}", "study", "Your study needs its next detail",
                                       f"\"{_short(s['question'])}\" needs: {label}", "Add it", "study-details",
                                       study_id=s["id"]))
        for d in queue["outcomes_due"]:
            candidates.append(step(f"outcome:{d['id']}", "outcome", "What happened?",
                                   f"You decided \"{d['title']}\". Now that some time has passed, how did it go?",
                                   "Add what happened", "outcome", decision_id=d["id"]))
        chosen = next((c for c in candidates if c["key"] not in skip), None)
        if chosen is None:
            chosen = {
                "stakeholder": step("suggest", "suggest", "Nothing is waiting on you",
                                    "Before your next decision, check what the team already knows.", "Search learnings",
                                    "search"),
                "researcher": step("suggest", "suggest", "Nothing is waiting on you",
                                   "Start a study tied to a decision, or look for learnings ready to promote.",
                                   "Start a study", "new-study"),
            }.get(queue["role"], step("suggest", "suggest", "Nothing is waiting on you",
                                      "Write down something you learned. One sentence is enough.", "Add a learning", "add"))
        moment = next((e for e in digest if e["kind"] == "moment" and not e["seen"]), None)
        return {"who": who, "step": chosen, "later": max(0, len([c for c in candidates if c["key"] not in skip]) - 1),
                "moment": {"key": f"e{moment['id']}", "text": moment["text"], "at": moment["at"]} if moment else None}
