import datetime as dt
import os
import re
import sys
import tempfile
from pathlib import Path

# GitHub Actions/pytest can put tests/ ahead of the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.mkdtemp(prefix="firstdig-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["DB_PATH"] = str(Path(_tmp) / "signals.db")
os.environ["BASE_URL"] = "https://example.test"
os.environ["SECRET_KEY"] = "qa-secret-key"
os.environ["CRON_SECRET"] = "qa-cron-secret"
os.environ["DEV_MODE"] = "1"
os.environ["ENABLE_SCHEDULER"] = "0"
os.environ["ADMIN_EMAILS"] = ""

from fastapi.testclient import TestClient
from app.db import connect, init_db, set_meta
from app.web import auth
from app.web import marketing_brief
from app.web.main import app

client = TestClient(app, base_url="https://example.test", raise_server_exceptions=False, follow_redirects=False)


def setup_module():
    init_db()
    today = dt.date.today()
    old = (today - dt.timedelta(days=30)).isoformat()
    recent = (today - dt.timedelta(days=1)).isoformat()
    with connect() as con:
        set_meta(con, "last_run", dt.datetime.utcnow().isoformat(timespec="seconds"))
        project_sql = """INSERT INTO projects(
            project_id,address,postal,ward,neighbourhood,lat,lon,kind,stage,headline,description,
            est_cost,units_created,builder_name,first_filed,last_activity,issued_date,permit_nums,signals,score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        con.execute(project_sql, ("old-house","10 Old St","M4A1A1","1","Leaside",43.7,-79.3,"new_house","issued",
                                  "New detached house","Test project",1200000,1,"Old Builder",old,old,old,"P1","new house",80))
        con.execute(project_sql, ("fresh-house","11 Fresh St","M4A1A2","1","Leaside",43.71,-79.31,"teardown","applied",
                                  "Fresh teardown","Fresh project",900000,1,"Fresh Builder",recent,recent,None,"P2","demolition",90))
        con.execute("""INSERT INTO permits(
            permit_key,permit_num,revision_num,permit_type,structure_type,work,street_num,street_name,street_type,street_dir,
            address,postal,geo_id,ward,application_date,issued_date,completed_date,status,description,current_use,proposed_use,
            units_created,units_lost,est_cost,builder_name,lat,lon,neighbourhood,first_seen,last_seen
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("P1|00","P1","00","New Building","House","New","10","Old","St","","10 Old St","M4A1A1","g1","1",
             old,old,None,"Issued","Test project","House","House",1,0,1200000,"Old Builder",43.7,-79.3,"Leaside",old,old))
        signals = '[{"type":"licence","date":"%s","detail":"business licence"},{"type":"permit","date":"%s","detail":"fit-out"}]' % (old, old)
        con.execute("""INSERT INTO openings(
            opening_id,name,category,address,city,postal,ward,neighbourhood,lat,lon,phone,owner,
            first_signal,last_signal,signals,signal_count,score,est_cost,description
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("opening-old","Sample Cafe","restaurant","20 Old St","TORONTO","M4B1B1","1","Leaside",43.72,-79.32,
             "4165550100","Sample Inc",old,old,signals,2,80,250000,"Restaurant fit-out"))


def test_public_routes_and_health():
    for path in ["/","/teardown","/openings","/pricing","/methodology","/terms",
                 "/app/teardown","/app/openings","/login","/health","/robots.txt",
                 "/api/teardown.geojson?days=60","/api/openings.geojson?days=90&minsig=2"]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text[:200])
    h = client.get("/health").json()
    assert h["ok"] is True
    assert h["projects"] >= 2


def test_head_root_and_security_headers():
    r = client.head("/")
    assert r.status_code == 200
    g = client.get("/")
    for header in ["x-content-type-options","x-frame-options","referrer-policy","permissions-policy","strict-transport-security"]:
        assert header in g.headers


def test_anonymous_data_is_delayed_and_redacted():
    r = client.get("/app/teardown?days=60")
    assert r.status_code == 200
    assert "Old Builder" not in r.text
    assert "Fresh Builder" not in r.text
    data = client.get("/api/openings.geojson?days=90&minsig=2").json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1
    assert "20 Old St" not in str(data)


def test_magic_link_trial_and_protected_export():
    anon = client.get("/export/teardown.csv")
    assert anon.status_code == 303
    assert anon.headers["location"].startswith("/login")

    r = client.post("/login", data={"email":"qa-user@example.test","next":"/app/teardown"},
                    headers={"origin":"https://example.test"})
    assert r.status_code == 200
    with connect() as con:
        token = con.execute("SELECT token FROM magic_links WHERE email=? ORDER BY rowid DESC LIMIT 1",
                            ("qa-user@example.test",)).fetchone()[0]
    auth_r = client.get(f"/auth/{token}?next=%2Fapp%2Fteardown")
    assert auth_r.status_code == 303
    assert auth_r.headers["location"] == "/app/teardown"
    assert "fd_session" in auth_r.headers.get("set-cookie","")

    full = client.get("/app/teardown?days=60")
    assert full.status_code == 200
    assert "Fresh Builder" in full.text

    export = client.get("/export/teardown.csv")
    assert export.status_code == 200
    assert "Fresh Builder" in export.text


def test_open_redirect_is_blocked():
    with connect() as con:
        token = auth.create_magic_link(con, "redirect-test@example.test")
    r = client.get(f"/auth/{token}?next=%2F%2Fevil.example")
    assert r.status_code == 303
    assert r.headers["location"] == "/app/teardown"


def test_origin_check_requires_exact_host():
    r = client.post("/login", data={"email":"origin-test@example.test","next":"/app/teardown"},
                    headers={"origin":"https://evil-example.test"})
    assert r.status_code == 403


def test_bad_filter_values_do_not_500():
    for path in [
        "/app/teardown?days=oops&mincost=wat",
        "/app/teardown?days=-999999&mincost=-5",
        "/app/openings?days=oops&minsig=oops",
        "/app/openings?days=-999999&minsig=999999999",
    ]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text[:200])


def test_cron_secret_rejected():
    r = client.get("/tasks/refresh?key=wrong")
    assert r.status_code == 403


def test_billing_disabled_fails_closed():
    # Reuse the authenticated client from the trial test when test order is standard;
    # create a fresh session if needed.
    if "fd_session" not in client.cookies:
        with connect() as con:
            token = auth.create_magic_link(con, "billing-test@example.test")
        client.get(f"/auth/{token}")
    r = client.post("/billing/checkout/teardown", headers={"origin":"https://example.test"})
    assert r.status_code == 303
    assert r.headers["location"] == "/pricing?billing=off"



def test_marketing_brief_includes_trade_specific_proof():
    today = dt.date.today().isoformat()
    with connect() as con:
        con.execute(
            """INSERT OR REPLACE INTO projects(
                project_id,address,postal,ward,neighbourhood,lat,lon,kind,stage,headline,description,
                est_cost,units_created,builder_name,first_filed,last_activity,issued_date,permit_nums,signals,score
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("underpinning-proof","88 Basement St","M4C1C1","1","Leaside",43.73,-79.33,
             "underpinning","applied","Underpinning / basement","Test underpinning project",
             180000,0,"",today,today,None,"P-UNDER","underpinning",40),
        )
        subject, html_body, text_body = marketing_brief.render(con, limit=5)
    assert "daily proof brief" in subject.lower()
    assert "TRADE-SPECIFIC PROOF" in text_body
    assert "UNDERPINNING / BASEMENT" in text_body
    assert "88 Basement St" in text_body
    assert "Underpinning / basement" in html_body
    assert "88 Basement St" in html_body
