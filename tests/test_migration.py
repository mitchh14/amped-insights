"""An older database, made by the first release, opens and upgrades in place."""

import sqlite3

from anchor import config
from anchor.core import Store

# The first release's tables, trimmed to what the upgrade touches.
OLD_SCHEMA = """
CREATE TABLE findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, statement TEXT NOT NULL, tier TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed', owner TEXT NOT NULL,
    evidence_links TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
    checked_out_by TEXT, checked_out_at TEXT
);
CREATE TABLE validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id INTEGER NOT NULL REFERENCES findings(id),
    validated_by TEXT NOT NULL, validated_at TEXT NOT NULL, note TEXT,
    UNIQUE (finding_id, validated_by)
);
CREATE TABLE conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id INTEGER NOT NULL, conflicting_id INTEGER NOT NULL,
    flagged_by TEXT NOT NULL, flagged_at TEXT NOT NULL, note TEXT
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, finding_id INTEGER REFERENCES findings(id),
    kind TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}'
);
INSERT INTO findings (statement, tier, status, owner, created_at)
    VALUES ('Conversion is 42 percent', 'data_point', 'validated', 'Ana', '2026-01-01T00:00:00+00:00');
INSERT INTO validations (finding_id, validated_by, validated_at, note)
    VALUES (1, 'Sam', '2026-01-02T00:00:00+00:00', 'checked');
INSERT INTO events (finding_id, kind, actor, at) VALUES (1, 'proposed', 'Ana', '2026-01-01T00:00:00+00:00');
"""


def test_old_database_upgrades_in_place(tmp_path):
    path = str(tmp_path / "old.db")
    with sqlite3.connect(path) as conn:
        conn.executescript(OLD_SCHEMA)
    store = Store(path, config.from_dict())
    f = store.get(1)
    assert f["statement"] == "Conversion is 42 percent"
    assert f["validations"][0]["validated_by"] == "Sam"
    assert {p["name"] for p in store.people()} == {"Ana", "Sam"}
    # New features work on the upgraded file.
    sid = store.start_study("Checkout", "Sam")["study"]["id"]
    new = store.propose("Drop off is on the address step", "data_point", "Ana", study_id=sid)
    assert new["finding"]["study"]["id"] == sid
    # Opening it again is a no-op.
    assert Store(path, config.from_dict()).get(1)["status"] == "validated"
