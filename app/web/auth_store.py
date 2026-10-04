"""Durable commercial-state adapter.

Public filing data remains in the rebuildable local SQLite database. When
AUTH_DATABASE_URL is set, user/trial/billing/digest state lives in Postgres so
host restarts and deploys cannot erase it. With no URL, local development and
tests retain the original SQLite behavior.
"""
import os

AUTH_DATABASE_URL = os.getenv("AUTH_DATABASE_URL", "").strip()

_PG_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        created TEXT,
        last_login TEXT,
        trial_ends TEXT,
        stripe_customer_id TEXT,
        plan TEXT,
        plan_status TEXT,
        digest_teardown BOOLEAN NOT NULL DEFAULT TRUE,
        digest_openings BOOLEAN NOT NULL DEFAULT TRUE,
        areas TEXT
    )""",
    """CREATE UNIQUE INDEX IF NOT EXISTS ix_users_stripe_customer
       ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL""",
    """CREATE TABLE IF NOT EXISTS magic_links (
        token TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        expires TEXT NOT NULL,
        used BOOLEAN NOT NULL DEFAULT FALSE
    )""",
    """CREATE TABLE IF NOT EXISTS sent_digests (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product TEXT NOT NULL,
        sent_date TEXT NOT NULL,
        PRIMARY KEY (user_id, product, sent_date)
    )""",
]


def enabled():
    return bool(AUTH_DATABASE_URL)


def backend_name():
    return "postgres" if enabled() else "sqlite"


def _pg():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(AUTH_DATABASE_URL, row_factory=dict_row)


def init():
    if not enabled():
        return
    with _pg() as con:
        for statement in _PG_SCHEMA:
            con.execute(statement)


def create_magic_link(sqlite_con, token, email, expires):
    if not enabled():
        sqlite_con.execute(
            "INSERT INTO magic_links(token,email,expires) VALUES (?,?,?)",
            (token, email, expires),
        )
        return
    with _pg() as con:
        con.execute(
            "INSERT INTO magic_links(token,email,expires,used) VALUES (%s,%s,%s,FALSE)",
            (token, email, expires),
        )


def consume_magic_link(sqlite_con, token, now_iso, trial_ends):
    if not enabled():
        row = sqlite_con.execute(
            "SELECT * FROM magic_links WHERE token=? AND used=0", (token,)
        ).fetchone()
        if not row or row["expires"] < now_iso:
            return None
        sqlite_con.execute("UPDATE magic_links SET used=1 WHERE token=?", (token,))
        email = row["email"]
        user = sqlite_con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            sqlite_con.execute(
                "INSERT INTO users(email,created,last_login,trial_ends) VALUES (?,?,?,?)",
                (email, now_iso, now_iso, trial_ends),
            )
        else:
            sqlite_con.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso, user["id"]))
        return sqlite_con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    with _pg() as con:
        row = con.execute(
            "SELECT * FROM magic_links WHERE token=%s AND used=FALSE FOR UPDATE", (token,)
        ).fetchone()
        if not row or row["expires"] < now_iso:
            return None
        con.execute("UPDATE magic_links SET used=TRUE WHERE token=%s", (token,))
        user = con.execute("SELECT * FROM users WHERE email=%s", (row["email"],)).fetchone()
        if not user:
            user = con.execute(
                """INSERT INTO users(email,created,last_login,trial_ends)
                   VALUES (%s,%s,%s,%s) RETURNING *""",
                (row["email"], now_iso, now_iso, trial_ends),
            ).fetchone()
        else:
            user = con.execute(
                "UPDATE users SET last_login=%s WHERE id=%s RETURNING *",
                (now_iso, user["id"]),
            ).fetchone()
        return user


def user_by_id(sqlite_con, user_id):
    if not enabled():
        return sqlite_con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    with _pg() as con:
        return con.execute("SELECT * FROM users WHERE id=%s", (user_id,)).fetchone()


def update_preferences(sqlite_con, user_id, digest_teardown, digest_openings, areas):
    if not enabled():
        sqlite_con.execute(
            "UPDATE users SET digest_teardown=?, digest_openings=?, areas=? WHERE id=?",
            (int(bool(digest_teardown)), int(bool(digest_openings)), areas, user_id),
        )
        return
    with _pg() as con:
        con.execute(
            """UPDATE users SET digest_teardown=%s, digest_openings=%s, areas=%s
               WHERE id=%s""",
            (bool(digest_teardown), bool(digest_openings), areas, user_id),
        )


def set_stripe_customer(sqlite_con, user_id, customer_id):
    if not enabled():
        sqlite_con.execute(
            "UPDATE users SET stripe_customer_id=? WHERE id=?", (customer_id, user_id)
        )
        return
    with _pg() as con:
        con.execute(
            "UPDATE users SET stripe_customer_id=%s WHERE id=%s", (customer_id, user_id)
        )


def set_subscription_by_customer(sqlite_con, customer_id, plan, status):
    if not enabled():
        sqlite_con.execute(
            "UPDATE users SET plan=?, plan_status=? WHERE stripe_customer_id=?",
            (plan, status, customer_id),
        )
        return
    with _pg() as con:
        con.execute(
            """UPDATE users SET plan=%s, plan_status=%s
               WHERE stripe_customer_id=%s""",
            (plan, status, customer_id),
        )


def list_users(sqlite_con, limit=None):
    if not enabled():
        sql = "SELECT * FROM users ORDER BY created DESC"
        params = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        return sqlite_con.execute(sql, params).fetchall()
    with _pg() as con:
        if limit is None:
            return con.execute("SELECT * FROM users ORDER BY created DESC").fetchall()
        return con.execute(
            "SELECT * FROM users ORDER BY created DESC LIMIT %s", (limit,)
        ).fetchall()


def count_users(sqlite_con):
    if not enabled():
        return sqlite_con.execute("SELECT count(*) FROM users").fetchone()[0]
    with _pg() as con:
        return con.execute("SELECT count(*) AS n FROM users").fetchone()["n"]


def count_sent_digests(sqlite_con):
    if not enabled():
        return sqlite_con.execute("SELECT count(*) FROM sent_digests").fetchone()[0]
    with _pg() as con:
        return con.execute("SELECT count(*) AS n FROM sent_digests").fetchone()["n"]


def digest_was_sent(sqlite_con, user_id, product, sent_date):
    if not enabled():
        return bool(
            sqlite_con.execute(
                """SELECT 1 FROM sent_digests
                   WHERE user_id=? AND product=? AND sent_date=?""",
                (user_id, product, sent_date),
            ).fetchone()
        )
    with _pg() as con:
        return bool(
            con.execute(
                """SELECT 1 FROM sent_digests
                   WHERE user_id=%s AND product=%s AND sent_date=%s""",
                (user_id, product, sent_date),
            ).fetchone()
        )


def mark_digest_sent(sqlite_con, user_id, product, sent_date):
    if not enabled():
        sqlite_con.execute(
            "INSERT OR IGNORE INTO sent_digests VALUES (?,?,?)",
            (user_id, product, sent_date),
        )
        return
    with _pg() as con:
        con.execute(
            """INSERT INTO sent_digests(user_id,product,sent_date)
               VALUES (%s,%s,%s)
               ON CONFLICT (user_id,product,sent_date) DO NOTHING""",
            (user_id, product, sent_date),
        )
