import sqlite3

import pytest

from app.web.auth_migrate import MigrationConflict, inventory, migrate


class SQLitePostgres:
    """Small SQL adapter exercising the migration transaction without a server."""
    def __init__(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        if "SELECT setval(" in sql:
            return self.con.execute("SELECT 1")
        return self.con.execute(sql.replace("%s", "?"), params)

    def commit(self):
        self.con.commit()

    def rollback(self):
        self.con.rollback()


def source_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE users (
          id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, created TEXT,
          last_login TEXT, trial_ends TEXT, stripe_customer_id TEXT, plan TEXT,
          plan_status TEXT, digest_teardown INTEGER, digest_openings INTEGER,
          areas TEXT
        );
        CREATE TABLE magic_links (
          token TEXT PRIMARY KEY, email TEXT, expires TEXT, used INTEGER
        );
        CREATE TABLE sent_digests (
          user_id INTEGER, product TEXT, sent_date TEXT,
          PRIMARY KEY (user_id, product, sent_date)
        );
    """)
    con.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (7, "qa@example.test", "2026-10-01", "2026-10-12",
         "2026-10-22", "cus_qa", "bundle", "active", 1, 0,
         "Leaside,Rosedale"),
    )
    con.execute(
        "INSERT INTO magic_links VALUES (?,?,?,?)",
        ("used-token", "qa@example.test", "2026-10-14T00:00:00", 1),
    )
    con.execute(
        "INSERT INTO sent_digests VALUES (?,?,?)",
        (7, "teardown", "2026-10-12"),
    )
    con.commit()
    return con


def snapshot(pg):
    return {
        "users": [tuple(row) for row in pg.con.execute("SELECT * FROM users ORDER BY id")],
        "magic_links": [tuple(row) for row in pg.con.execute("SELECT * FROM magic_links ORDER BY token")],
        "sent_digests": [tuple(row) for row in pg.con.execute("SELECT * FROM sent_digests ORDER BY user_id")],
    }


def test_migration_preserves_all_commercial_state_and_is_idempotent():
    source = source_db()
    pg = SQLitePostgres()
    assert migrate(source, pg) == {"users": 1, "magic_links": 1, "sent_digests": 1}
    first = snapshot(pg)
    assert first["users"][0][0] == 7
    assert first["users"][0][5:11] == (
        "cus_qa", "bundle", "active", 1, 0, "Leaside,Rosedale"
    )
    assert first["magic_links"][0][3] == 1
    assert first["sent_digests"] == [(7, "teardown", "2026-10-12")]
    assert migrate(source, pg) == {"users": 1, "magic_links": 1, "sent_digests": 1}
    assert snapshot(pg) == first


def test_dry_run_reports_counts_without_touching_destination():
    source = source_db()
    pg = SQLitePostgres()
    assert migrate(source, pg, dry_run=True) == {
        "users": 1, "magic_links": 1, "sent_digests": 1
    }
    assert pg.con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone() is None
    assert inventory(source)["users"] == 1


def test_nonmatching_destination_fails_closed_and_rolls_back():
    source = source_db()
    pg = SQLitePostgres()
    migrate(source, pg)
    pg.con.execute("UPDATE users SET email='other@example.test' WHERE id=7")
    pg.con.commit()
    with pytest.raises(MigrationConflict, match="does not exactly match source"):
        migrate(source, pg)
    assert pg.con.execute("SELECT email FROM users WHERE id=7").fetchone()[0] == "other@example.test"


def test_orphan_digest_is_rejected_before_destination_changes():
    source = source_db()
    source.execute("INSERT INTO sent_digests VALUES (99,'openings','2026-10-12')")
    source.commit()
    pg = SQLitePostgres()
    with pytest.raises(MigrationConflict, match="orphan"):
        migrate(source, pg)
    assert pg.con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone() is None
