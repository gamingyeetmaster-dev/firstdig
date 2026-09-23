"""First Dig web app: Teardown Feed + Opening Soon."""
import csv
import datetime as dt
import io
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config
from ..db import connect, get_meta, init_db
from . import auth, billing, digest, emailer, queries, scheduler
from .hardening import Hardening

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("web")

HERE = Path(__file__).parent
app = FastAPI(title="First Dig", docs_url=None, redoc_url=None)
app.add_middleware(Hardening)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals.update(
    PRODUCTS=config.PRODUCTS, BUNDLE_PRICE=config.BUNDLE_PRICE_MONTHLY, BASE_URL=config.BASE_URL,
    TRIAL_DAYS=config.TRIAL_DAYS, FREE_DELAY_DAYS=config.FREE_DELAY_DAYS, DEV_MODE=config.DEV_MODE,
    billing_enabled=billing.enabled, year=dt.date.today().year,
)


def money(v):
    if v is None:
        return ""
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}k"
    return f"${v:.0f}"


def nice_date(v):
    if not v:
        return ""
    try:
        return dt.date.fromisoformat(v[:10]).strftime("%b %-d")
    except ValueError:
        return v


templates.env.filters["money"] = money
templates.env.filters["nice_date"] = nice_date


@app.on_event("startup")
def _startup():
    init_db()
    scheduler.start()


# ---------- request context ----------

class Ctx:
    def __init__(self, request: Request):
        self.request = request
        self.con = connect()
        self.user = auth.user_from_cookie(self.con, request.cookies.get(auth.COOKIE))
        self.access = auth.access_for(self.user)
        self.is_admin = auth.is_admin(self.user)

    def close(self):
        self.con.commit()
        self.con.close()


def ctx(request: Request):
    c = Ctx(request)
    try:
        yield c
    finally:
        c.close()


def render(c: Ctx, name, **kw):
    kw.setdefault("user", c.user)
    kw.setdefault("access", c.access)
    kw.setdefault("is_admin", c.is_admin)
    kw.setdefault("last_run", get_meta(c.con, "last_run"))
    return templates.TemplateResponse(c.request, name, kw)


def require_login(c: Ctx):
    if not c.user:
        raise HTTPException(status_code=303, headers={"Location": f"/login?next={c.request.url.path}"})


@app.exception_handler(HTTPException)
async def _redirects(request, exc):
    if exc.status_code == 303:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)


# ---------- marketing ----------

@app.get("/", response_class=HTMLResponse)
def home(c: Ctx = Depends(ctx)):
    st = queries.stats(c.con)
    sample_t, _, _ = queries.projects(c.con, {"days": 60, "kinds": "teardown,new_house,multiplex"}, False, limit=6)
    sample_o, _, _ = queries.openings(c.con, {"days": 90, "minsig": 2}, False, limit=6)
    return render(c, "index.html", stats=st, sample_t=sample_t, sample_o=sample_o)


@app.get("/teardown", response_class=HTMLResponse)
def product_teardown(c: Ctx = Depends(ctx)):
    st = queries.stats(c.con)
    items, total, _ = queries.projects(c.con, {"days": 60}, False, limit=40)
    by_kind = c.con.execute("SELECT kind, count(*) n FROM projects WHERE first_filed >= date('now','-30 days') GROUP BY 1").fetchall()
    return render(c, "product_teardown.html", stats=st, items=items, total=total, by_kind={r["kind"]: r["n"] for r in by_kind}, kinds=queries.kinds())


@app.get("/openings", response_class=HTMLResponse)
def product_openings(c: Ctx = Depends(ctx)):
    st = queries.stats(c.con)
    items, total, _ = queries.openings(c.con, {"days": 90, "minsig": 2}, False, limit=40)
    by_cat = c.con.execute("SELECT category, count(*) n FROM openings WHERE last_signal >= date('now','-30 days') GROUP BY 1 ORDER BY 2 DESC").fetchall()
    return render(c, "product_openings.html", stats=st, items=items, total=total, by_cat=by_cat, categories=queries.categories())


@app.get("/pricing", response_class=HTMLResponse)
def pricing(c: Ctx = Depends(ctx)):
    return render(c, "pricing.html")


@app.get("/methodology", response_class=HTMLResponse)
def methodology(c: Ctx = Depends(ctx)):
    st = queries.stats(c.con)
    return render(c, "methodology.html", stats=st)


@app.get("/terms", response_class=HTMLResponse)
def terms(c: Ctx = Depends(ctx)):
    return render(c, "terms.html")


# ---------- dashboards ----------

@app.get("/app/teardown", response_class=HTMLResponse)
def dash_teardown(c: Ctx = Depends(ctx)):
    full = c.access["teardown"]
    args = dict(c.request.query_params)
    items, total, active = queries.projects(c.con, args, full)
    return render(c, "dash_teardown.html", items=items, total=total, active=active, full=full,
                  hoods=queries.neighbourhoods(c.con), kinds=queries.kinds(), stages=list(queries.STAGE_LABELS.items()), product=config.PRODUCTS["teardown"])


@app.get("/app/openings", response_class=HTMLResponse)
def dash_openings(c: Ctx = Depends(ctx)):
    full = c.access["openings"]
    args = dict(c.request.query_params)
    items, total, active = queries.openings(c.con, args, full)
    return render(c, "dash_openings.html", items=items, total=total, active=active, full=full,
                  hoods=queries.neighbourhoods(c.con), categories=queries.categories(), product=config.PRODUCTS["openings"])


@app.get("/p/{project_id}", response_class=HTMLResponse)
def project_detail(project_id: str, c: Ctx = Depends(ctx)):
    p, permits = queries.project(c.con, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    full = c.access["teardown"]
    p = queries.redact_project(p, full)
    locked = not full and queries.is_recent(p["first_filed"])
    if not full:
        permits = []
    if locked:
        p.update({"description": "Filed within the last %d days. Subscribers see this record today." % config.FREE_DELAY_DAYS,
                  "headline": p["kind_label"], "est_cost": None, "units_created": None, "signals": "", "last_activity": None, "issued_date": None})
    nearby = c.con.execute(
        "SELECT * FROM projects WHERE neighbourhood=? AND project_id!=? ORDER BY first_filed DESC LIMIT 8", (p["neighbourhood"], project_id)).fetchall()
    return render(c, "detail_project.html", p=p, permits=permits, full=full, locked=locked, nearby=[queries.redact_project(dict(r), full) for r in nearby], product=config.PRODUCTS["teardown"])


@app.get("/o/{opening_id:path}", response_class=HTMLResponse)
def opening_detail(opening_id: str, c: Ctx = Depends(ctx)):
    o = queries.opening(c.con, opening_id)
    if not o:
        raise HTTPException(404, "Record not found")
    full = c.access["openings"]
    o = queries.redact_opening(o, full)
    locked = not full and queries.is_recent(o["last_signal"])
    if locked:
        o.update({"signal_list": [{"date": o["last_signal"], "type": "locked", "detail": "Filed within the last %d days. Subscribers see the paper trail today." % config.FREE_DELAY_DAYS}],
                  "score": None, "est_cost": None, "first_signal": None})
    nearby = c.con.execute("SELECT * FROM openings WHERE neighbourhood=? AND opening_id!=? ORDER BY last_signal DESC LIMIT 8", (o["neighbourhood"], opening_id)).fetchall()
    return render(c, "detail_opening.html", o=o, full=full, locked=locked, nearby=[queries.redact_opening(dict(r), full) for r in nearby], product=config.PRODUCTS["openings"])


# ---------- data endpoints (map + export) ----------

@app.get("/api/teardown.geojson")
def api_teardown(c: Ctx = Depends(ctx)):
    full = c.access["teardown"]
    items, _, _ = queries.projects(c.con, dict(c.request.query_params), full, limit=1500)
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
              "properties": {"id": p["project_id"], "address": p["address"], "headline": p["headline"], "kind": p["kind"],
                             "stage": p["stage_label"], "filed": p["first_filed"], "hood": p["neighbourhood"]}}
             for p in items if p["lat"]]
    return JSONResponse({"type": "FeatureCollection", "features": feats})


@app.get("/api/openings.geojson")
def api_openings(c: Ctx = Depends(ctx)):
    full = c.access["openings"]
    items, _, _ = queries.openings(c.con, dict(c.request.query_params), full, limit=1500)
    feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [o["lon"], o["lat"]]},
              "properties": {"id": o["opening_id"], "name": o["name"] or o["category_label"], "address": o["address"], "cat": o["category"],
                             "signals": o["signal_count"], "last": o["last_signal"], "hood": o["neighbourhood"]}}
             for o in items if o["lat"]]
    return JSONResponse({"type": "FeatureCollection", "features": feats})


@app.get("/export/{product}.csv")
def export_csv(product: str, c: Ctx = Depends(ctx)):
    require_login(c)
    if not c.access.get(product):
        raise HTTPException(303, headers={"Location": "/pricing"})
    buf = io.StringIO()
    w = csv.writer(buf)
    if product == "teardown":
        items, _, _ = queries.projects(c.con, dict(c.request.query_params), True, limit=5000)
        w.writerow(["address", "neighbourhood", "postal", "kind", "stage", "headline", "est_cost", "units_created", "builder", "first_filed", "issued", "last_activity", "permits", "description", "lat", "lon", "url"])
        for p in items:
            w.writerow([p["address"], p["neighbourhood"], p["postal"], p["kind_label"], p["stage_label"], p["headline"], p["est_cost"], p["units_created"], p["builder_name"],
                        p["first_filed"], p["issued_date"], p["last_activity"], p["permit_nums"], p["description"], p["lat"], p["lon"], f"{config.BASE_URL}/p/{quote(p['project_id'])}"])
    elif product == "openings":
        items, _, _ = queries.openings(c.con, dict(c.request.query_params), True, limit=5000)
        w.writerow(["name", "category", "address", "city", "postal", "neighbourhood", "phone", "owner_or_applicant", "first_signal", "last_signal", "signals", "signal_types", "est_cost", "lat", "lon", "url"])
        for o in items:
            w.writerow([o["name"], o["category_label"], o["address"], o["city"], o["postal"], o["neighbourhood"], o["phone"], o["owner"], o["first_signal"], o["last_signal"],
                        o["signal_count"], " ".join(o["signal_types"]), o["est_cost"], o["lat"], o["lon"], f"{config.BASE_URL}/o/{quote(o['opening_id'], safe='')}"])
    else:
        raise HTTPException(404)
    fname = f"{product}-{dt.date.today().isoformat()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fname}"})


# ---------- auth ----------

@app.get("/login", response_class=HTMLResponse)
def login_page(c: Ctx = Depends(ctx), next: str = "/app/teardown"):
    return render(c, "login.html", next=next)


@app.post("/login", response_class=HTMLResponse)
def login_post(c: Ctx = Depends(ctx), email: str = Form(...), next: str = Form("/app/teardown")):
    email = email.strip().lower()
    if "@" not in email or len(email) > 200:
        return render(c, "login.html", next=next, error="That doesn't look like an email address.")
    token = auth.create_magic_link(c.con, email)
    link = f"{config.BASE_URL}/auth/{token}?next={next}"
    html = templates.get_template("email_login.html").render(link=link, base_url=config.BASE_URL)
    r = emailer.send(email, "Your sign-in link for First Dig", html, f"Sign in: {link}")
    dev_link = link if (config.DEV_MODE and not r["delivered"]) else None
    return render(c, "login.html", next=next, sent=email, dev_link=dev_link)


@app.get("/auth/{token}")
def auth_token(token: str, c: Ctx = Depends(ctx), next: str = "/app/teardown"):
    user = auth.consume_magic_link(c.con, token)
    if not user:
        return render(c, "login.html", next=next, error="That link has expired or was already used. Request a new one.")
    resp = RedirectResponse(next if next.startswith("/") else "/app/teardown", status_code=303)
    resp.set_cookie(auth.COOKIE, auth.session_cookie_value(user["id"]), max_age=60 * 60 * 24 * 90, httponly=True, samesite="lax",
                    secure=config.BASE_URL.startswith("https"))
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(auth.COOKIE)
    return resp


# ---------- account & billing ----------

@app.get("/account", response_class=HTMLResponse)
def account(c: Ctx = Depends(ctx)):
    require_login(c)
    return render(c, "account.html", hoods=queries.neighbourhoods(c.con), areas=[a for a in (c.user["areas"] or "").split(",") if a],
                  checkout=c.request.query_params.get("checkout"))


@app.post("/account")
async def account_post(c: Ctx = Depends(ctx)):
    require_login(c)
    form = await c.request.form()
    areas = ",".join(form.getlist("areas"))
    c.con.execute("UPDATE users SET digest_teardown=?, digest_openings=?, areas=? WHERE id=?",
                  (1 if form.get("digest_teardown") else 0, 1 if form.get("digest_openings") else 0, areas, c.user["id"]))
    return RedirectResponse("/account?saved=1", status_code=303)


@app.post("/billing/checkout/{plan}")
def checkout(plan: str, c: Ctx = Depends(ctx)):
    require_login(c)
    if not billing.enabled():
        return RedirectResponse("/pricing?billing=off", status_code=303)
    try:
        url = billing.checkout_url(c.con, c.user, plan)
    except Exception as e:
        log.exception("checkout failed")
        return RedirectResponse(f"/pricing?error={type(e).__name__}", status_code=303)
    return RedirectResponse(url, status_code=303)


@app.get("/billing/portal")
def portal(c: Ctx = Depends(ctx)):
    require_login(c)
    if not billing.enabled() or not c.user["stripe_customer_id"]:
        return RedirectResponse("/account", status_code=303)
    return RedirectResponse(billing.portal_url(c.user), status_code=303)


@app.post("/billing/webhook")
async def webhook(request: Request):
    payload = await request.body()
    con = connect()
    try:
        t = billing.handle_webhook(con, payload, request.headers.get("stripe-signature", ""))
        con.commit()
    except Exception as e:
        log.exception("webhook rejected")
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        con.close()
    return {"received": t}


# ---------- ops ----------

def _check_key(request: Request):
    if request.query_params.get("key") != config.CRON_SECRET and request.headers.get("x-cron-key") != config.CRON_SECRET:
        raise HTTPException(403, "bad key")


@app.post("/tasks/refresh")
@app.get("/tasks/refresh")
def task_refresh(request: Request):
    _check_key(request)
    from ..pipeline.run import run
    lines = []
    run(force=request.query_params.get("force") == "1", log=lines.append)
    return Response("\n".join(lines), media_type="text/plain")


@app.post("/tasks/digests")
@app.get("/tasks/digests")
def task_digests(request: Request):
    _check_key(request)
    con = connect()
    lines = []
    try:
        n = digest.send_all(con, emailer.send, log=lines.append, dry=request.query_params.get("dry") == "1")
        con.commit()
    finally:
        con.close()
    return Response("\n".join(lines) + f"\nsent={n}", media_type="text/plain")


@app.get("/admin", response_class=HTMLResponse)
def admin(c: Ctx = Depends(ctx)):
    require_login(c)
    if not c.is_admin:
        raise HTTPException(403, "Admins only. Add your email to ADMIN_EMAILS.")
    users = c.con.execute("SELECT * FROM users ORDER BY created DESC LIMIT 200").fetchall()
    runs = c.con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 20").fetchall()
    counts = {t: c.con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("permits", "projects", "licences", "liquor_apps", "openings", "users", "sent_digests")}
    return render(c, "admin.html", users=users, runs=runs, counts=counts, stats=queries.stats(c.con))


@app.get("/health")
def health():
    con = connect()
    try:
        last = get_meta(con, "last_run")
        n = con.execute("SELECT count(*) FROM projects").fetchone()[0]
    finally:
        con.close()
    return {"ok": True, "last_run": last, "projects": n}


@app.get("/robots.txt")
def robots():
    return Response("User-agent: *\nDisallow: /app/\nDisallow: /account\nDisallow: /admin\nAllow: /\n", media_type="text/plain")
