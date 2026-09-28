"""Build a zero-cold-start public snapshot for First Dig.

The public browse experience is intentionally static/CDN-served. Dynamic account,
billing and private detail routes remain on the backend service.
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "public_static"
BUILD_DATA = ROOT / ".public-build-data"
BACKEND = os.getenv("FIRSTDIG_BACKEND", "https://first-dig-night-shift.onrender.com").rstrip("/")

# Isolate build-time data so this script is deterministic.
os.environ["DATA_DIR"] = str(BUILD_DATA)
os.environ["DB_PATH"] = str(BUILD_DATA / "signals.db")
os.environ["DEV_MODE"] = "0"
os.environ["ENABLE_SCHEDULER"] = "0"
os.environ.setdefault("BASE_URL", BACKEND)

from app.pipeline.run import run
from app.db import connect
from app.web import queries
from app.web.main import app
from fastapi.testclient import TestClient


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rewrite_common(html: str, dashboard=False) -> str:
    # Public browse stays on the static origin; account actions use the dynamic backend.
    html = html.replace('href="/app/teardown"', 'href="/teardown"')
    html = html.replace('href="/app/openings"', 'href="/openings"')
    html = html.replace('href="/login?next=/app/teardown"', f'href="{BACKEND}/login?next=/app/teardown"')
    html = html.replace('href="/login?next=/app/openings"', f'href="{BACKEND}/login?next=/app/openings"')
    html = html.replace('href="/login"', f'href="{BACKEND}/login"')
    html = html.replace('href="/account"', f'href="{BACKEND}/account"')
    html = html.replace('action="/logout"', f'action="{BACKEND}/logout"')
    html = html.replace('href="mailto:hello@example.com"', 'href="mailto:jacksonjameslang@gmail.com"')
    if dashboard:
        html = html.replace('/static/app.js?v=2', '/static/public-dashboard.js?v=1')
    return html


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    if BUILD_DATA.exists():
        shutil.rmtree(BUILD_DATA)
    OUT.mkdir(parents=True, exist_ok=True)

    # Build the real Toronto dataset during deploy. Static hosting means visitors
    # never wait for this work and never see an empty database.
    run(force=True)

    with connect() as con:
        projects, project_total, _ = queries.projects(
            con, {"days": "3650"}, full_access=False, limit=20000
        )
        openings, opening_total, _ = queries.openings(
            con, {"days": "3650", "city": "all", "minsig": "1"},
            full_access=False, limit=20000
        )
        last = queries.stats(con).get("last_run")

    data_dir = OUT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "teardown.json").write_text(json.dumps({
        "generated_at": last,
        "total": project_total,
        "records": projects,
    }, separators=(",", ":")), encoding="utf-8")
    (data_dir / "openings.json").write_text(json.dumps({
        "generated_at": last,
        "total": opening_total,
        "records": openings,
    }, separators=(",", ":")), encoding="utf-8")

    # Reuse the existing brand/UI assets.
    shutil.copytree(ROOT / "app" / "web" / "static", OUT / "static", dirs_exist_ok=True)

    client = TestClient(app, base_url="https://firstdig.app", follow_redirects=True)

    # Marketing/static pages.
    for route, dest in [
        ("/", OUT / "index.html"),
        ("/pricing", OUT / "pricing" / "index.html"),
        ("/methodology", OUT / "methodology" / "index.html"),
        ("/terms", OUT / "terms" / "index.html"),
    ]:
        r = client.get(route)
        r.raise_for_status()
        write(dest, rewrite_common(r.text))

    # Public dashboards. Write both historical /app/... paths and clean URLs.
    for product in ("teardown", "openings"):
        r = client.get(f"/app/{product}")
        r.raise_for_status()
        html = rewrite_common(r.text, dashboard=True)
        write(OUT / product / "index.html", html)
        write(OUT / "app" / product / "index.html", html)

    # Render static-site fallback: useful for direct links without extensions.
    write(OUT / "404.html", rewrite_common(client.get("/").text))


if __name__ == "__main__":
    main()
