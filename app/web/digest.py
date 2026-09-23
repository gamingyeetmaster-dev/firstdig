"""Email digests. Teardown Feed is daily; Opening Soon is daily too but
only when there is something new. Each user gets at most one email per
product per day, tracked in sent_digests."""
import datetime as dt
import json

from jinja2 import Environment, FileSystemLoader, select_autoescape

from urllib.parse import quote

from ..config import BASE_URL
from .auth import access_for
from .queries import redact_opening, redact_project

_env = Environment(loader=FileSystemLoader(str(__import__("pathlib").Path(__file__).parent / "templates")),
                   autoescape=select_autoescape(["html"]))


def _areas(user):
    return [a for a in (user["areas"] or "").split(",") if a]


def teardown_items(con, user, since):
    areas = _areas(user)
    sql = "SELECT * FROM projects WHERE first_filed > ? AND kind IN ('teardown','new_house','multiplex','garden_suite','major_addition','pool','new_building')"
    params = [since]
    if areas:
        sql += " AND neighbourhood IN (%s)" % ",".join("?" * len(areas))
        params += areas
    sql += " ORDER BY score DESC, first_filed DESC LIMIT 60"
    return [redact_project(dict(r), True) for r in con.execute(sql, params)]


def opening_items(con, user, since):
    areas = _areas(user)
    sql = "SELECT * FROM openings WHERE last_signal > ? AND (city IS NULL OR upper(city) IN ('TORONTO','NORTH YORK','SCARBOROUGH','ETOBICOKE','EAST YORK','YORK'))"
    params = [since]
    if areas:
        sql += " AND neighbourhood IN (%s)" % ",".join("?" * len(areas))
        params += areas
    sql += " ORDER BY score DESC LIMIT 60"
    return [redact_opening(dict(r), True) for r in con.execute(sql, params)]


def render(product, user, items, since):
    tpl = _env.get_template("email_digest.html")
    html = tpl.render(product=product, user=user, items=items, since=since, base_url=BASE_URL, date=dt.date.today().isoformat())
    lines = [f"{product['name']} - {len(items)} new since {since}", ""]
    for it in items:
        if product["slug"] == "teardown":
            lines.append(f"- {it['address']} ({it['neighbourhood']}): {it['headline']} [{it['stage_label']}] {BASE_URL}/p/{quote(it['project_id'])}")
        else:
            lines.append(f"- {it['name'] or it['category_label']} - {it['address']} ({it['neighbourhood']}), {it['signal_count']} signals {BASE_URL}/o/{quote(it['opening_id'], safe='')}")
    return html, "\n".join(lines)


def send_all(con, send_fn, log=print, dry=False):
    from ..config import PRODUCTS
    today = dt.date.today().isoformat()
    since = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    users = con.execute("SELECT * FROM users").fetchall()
    sent = 0
    for u in users:
        acc = access_for(u)
        for slug, product in PRODUCTS.items():
            if not acc.get(slug) or not u["digest_" + slug]:
                continue
            if con.execute("SELECT 1 FROM sent_digests WHERE user_id=? AND product=? AND sent_date=?", (u["id"], slug, today)).fetchone():
                continue
            items = teardown_items(con, u, since) if slug == "teardown" else opening_items(con, u, since)
            if not items:
                continue
            html, text = render(product, u, items, since)
            subject = f"{product['name']}: {len(items)} new {'projects' if slug == 'teardown' else 'openings'} in Toronto"
            if dry:
                log(f"  would send {subject} -> {u['email']}")
            else:
                send_fn(u["email"], subject, html, text)
                con.execute("INSERT INTO sent_digests VALUES (?,?,?)", (u["id"], slug, today))
            sent += 1
    log(f"  digests: {sent} sent")
    return sent
