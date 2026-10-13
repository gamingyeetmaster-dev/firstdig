"""One-shot, side-effect-free migration of commercial state to Postgres.

This module never sends email, invokes Stripe, or changes AUTH_DATABASE_URL.
Run it before switching the web service to Postgres.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

from .auth_store import _PG_SCHEMA


TABLES = ("users", "magic_links", "sent_digests")
USER_COLUMNS = (
    "id", "email", "created", "last_login", "trial_ends",
    "stripe_customer_id", "plan", "plan_status", "digest_teardown",
    "digest_openings", "areas",
)
MAGIC_COLUMNS = ("token", "email", "expires", "used")
DIGEST_COLUMNS = ("user_id", "product", "sent_date")


class MigrationConflict(RuntimeError):
    """Raised when source and destination cannot be reconciled safely."""


def _rows(con, table, columns):
    result = con.execute(
        f"SELECT {','.join(columns)} FROM {table} ORDER BY {columns[0]}"
    ).fetchall()
    return [dict(row) for row in result]


def snapshot_sqlite(sqlite_con):
    return {
        "users": _rows(sqlite_con, "users", USER_COLUMNS),
        "magic_links": _rows(sqlite_con, "magic_links", MAGIC_COLUMNS),
        "sent_digests": _rows(sqlite_con, "sent_digests", DIGEST_COLUMNS),
    }


def _normalise(table, row):
    row = dict(row)
    if table == "users":
        row["digest_teardown"] = bool(row["digest_teardown"])
        row["digest_openings"] = bool(row["digest_openings"])
    elif table == "magic_links":
        row["used"] = bool(row["used"])
    return row


def _canonical(table, rows):
    columns = {
        "users": USER_COLUMNS,
        "magic_links": MAGIC_COLUMNS,
        "sent_digests": DIGEST_COLUMNS,
    }[table]
    return sorted(
        (tuple(_normalise(table, row).get(column) for column in columns) for row in rows),
        key=repr,
    )


def _validate_source(source):
    user_ids = {row["id"] for row in source["users"]}
    orphan_ids = {
        row["user_id"] for row in source["sent_digests"]
        if row["user_id"] not in user_ids
    }
    if orphan_ids:
        raise MigrationConflict(
            f"source sent_digests contains {len(orphan_ids)} orphan user id(s)"
        )
    stripe_ids = [
        row["stripe_customer_id"] for row in source["users"]
        if row["stripe_customer_id"]
    ]
    if len(stripe_ids) != len(set(stripe_ids)):
        raise MigrationConflict("source contains duplicate Stripe customer ids")


def inventory(sqlite_con):
    source = snapshot_sqlite(sqlite_con)
    _validate_source(source)
    return {table: len(source[table]) for table in TABLES}


def migrate(sqlite_con, pg_con, dry_run=False):
    """Migrate and exactly reconcile all commercial rows in one transaction."""
    source = snapshot_sqlite(sqlite_con)
    _validate_source(source)
    counts = {table: len(source[table]) for table in TABLES}
    if dry_run:
        return counts

    try:
        for statement in _PG_SCHEMA:
            pg_con.execute(statement)

        current = {
            "users": _rows(pg_con, "users", USER_COLUMNS),
            "magic_links": _rows(pg_con, "magic_links", MAGIC_COLUMNS),
            "sent_digests": _rows(pg_con, "sent_digests", DIGEST_COLUMNS),
        }
        for table in TABLES:
            if current[table] and _canonical(table, current[table]) != _canonical(table, source[table]):
                raise MigrationConflict(
                    f"destination {table} is non-empty and does not exactly match source"
                )

        user_sql = """INSERT INTO users(
            id,email,created,last_login,trial_ends,stripe_customer_id,plan,plan_status,
            digest_teardown,digest_openings,areas
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            email=EXCLUDED.email, created=EXCLUDED.created,
            last_login=EXCLUDED.last_login, trial_ends=EXCLUDED.trial_ends,
            stripe_customer_id=EXCLUDED.stripe_customer_id, plan=EXCLUDED.plan,
            plan_status=EXCLUDED.plan_status,
            digest_teardown=EXCLUDED.digest_teardown,
            digest_openings=EXCLUDED.digest_openings, areas=EXCLUDED.areas"""
        for row in source["users"]:
            pg_con.execute(user_sql, tuple(row[column] for column in USER_COLUMNS))

        magic_sql = """INSERT INTO magic_links(token,email,expires,used)
            VALUES (%s,%s,%s,%s) ON CONFLICT (token) DO NOTHING"""
        for row in source["magic_links"]:
            pg_con.execute(magic_sql, tuple(row[column] for column in MAGIC_COLUMNS))

        digest_sql = """INSERT INTO sent_digests(user_id,product,sent_date)
            VALUES (%s,%s,%s) ON CONFLICT (user_id,product,sent_date) DO NOTHING"""
        for row in source["sent_digests"]:
            pg_con.execute(digest_sql, tuple(row[column] for column in DIGEST_COLUMNS))

        pg_con.execute(
            """SELECT setval(
                pg_get_serial_sequence('users','id'),
                COALESCE((SELECT MAX(id) FROM users), 1),
                EXISTS(SELECT 1 FROM users)
            )"""
        )

        migrated = {
            "users": _rows(pg_con, "users", USER_COLUMNS),
            "magic_links": _rows(pg_con, "magic_links", MAGIC_COLUMNS),
            "sent_digests": _rows(pg_con, "sent_digests", DIGEST_COLUMNS),
        }
        for table in TABLES:
            if _canonical(table, migrated[table]) != _canonical(table, source[table]):
                raise MigrationConflict(f"post-migration reconciliation failed for {table}")
        pg_con.commit()
        return counts
    except Exception:
        pg_con.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Migrate First Dig commercial state from SQLite to Postgres"
    )
    parser.add_argument(
        "--sqlite",
        default=os.getenv("DB_PATH", "data/signals.db"),
        help="source SQLite database path (default: DB_PATH)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate source and print table counts without connecting to Postgres",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.sqlite)
    if not source_path.is_file():
        parser.error(f"SQLite source does not exist: {source_path}")
    sqlite_con = sqlite3.connect(str(source_path))
    sqlite_con.row_factory = sqlite3.Row
    try:
        if args.dry_run:
            result = inventory(sqlite_con)
        else:
            database_url = os.getenv("AUTH_DATABASE_URL", "").strip()
            if not database_url:
                parser.error("AUTH_DATABASE_URL is required unless --dry-run is used")
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(database_url, row_factory=dict_row) as pg_con:
                result = migrate(sqlite_con, pg_con)
    finally:
        sqlite_con.close()
    print(json.dumps({"ok": True, "counts": result}, sort_keys=True))


if __name__ == "__main__":
    main()
