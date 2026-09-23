"""Passwordless login: email a signed one-time link, set a signed cookie."""
import datetime as dt
import secrets

from itsdangerous import BadSignature, URLSafeSerializer

from ..config import ADMIN_EMAILS, SECRET_KEY, TRIAL_DAYS

COOKIE = "fd_session"
_signer = URLSafeSerializer(SECRET_KEY, salt="session")


def now():
    return dt.datetime.utcnow().replace(microsecond=0)


def create_magic_link(con, email):
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    expires = (now() + dt.timedelta(minutes=30)).isoformat()
    con.execute("INSERT INTO magic_links(token,email,expires) VALUES (?,?,?)", (token, email, expires))
    return token


def consume_magic_link(con, token):
    row = con.execute("SELECT * FROM magic_links WHERE token=? AND used=0", (token,)).fetchone()
    if not row or row["expires"] < now().isoformat():
        return None
    con.execute("UPDATE magic_links SET used=1 WHERE token=?", (token,))
    email = row["email"]
    user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    ts = now().isoformat()
    if not user:
        trial_ends = (now() + dt.timedelta(days=TRIAL_DAYS)).date().isoformat()
        con.execute("INSERT INTO users(email,created,last_login,trial_ends) VALUES (?,?,?,?)", (email, ts, ts, trial_ends))
    else:
        con.execute("UPDATE users SET last_login=? WHERE id=?", (ts, user["id"]))
    return con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()


def session_cookie_value(user_id):
    return _signer.dumps({"uid": user_id, "t": now().isoformat()})


def user_from_cookie(con, value):
    if not value:
        return None
    try:
        data = _signer.loads(value)
    except BadSignature:
        return None
    return con.execute("SELECT * FROM users WHERE id=?", (data.get("uid"),)).fetchone()


# ---------- entitlements ----------

def access_for(user):
    """Returns dict(product_slug -> bool) plus trial info."""
    if not user:
        return {"teardown": False, "openings": False, "trial": False, "trial_days_left": 0, "reason": "anonymous"}
    today = dt.date.today().isoformat()
    plan, status = user["plan"], user["plan_status"]
    paid = status in ("active", "trialing", "past_due") and plan
    if paid:
        both = plan == "bundle"
        return {"teardown": both or plan == "teardown", "openings": both or plan == "openings",
                "trial": False, "trial_days_left": 0, "reason": "plan:" + plan}
    if user["email"].lower() in ADMIN_EMAILS:
        return {"teardown": True, "openings": True, "trial": False, "trial_days_left": 0, "reason": "admin"}
    if user["trial_ends"] and user["trial_ends"] >= today:
        left = (dt.date.fromisoformat(user["trial_ends"]) - dt.date.today()).days + 1
        return {"teardown": True, "openings": True, "trial": True, "trial_days_left": left, "reason": "trial"}
    return {"teardown": False, "openings": False, "trial": False, "trial_days_left": 0, "reason": "expired"}


def is_admin(user):
    return bool(user) and user["email"].lower() in ADMIN_EMAILS
