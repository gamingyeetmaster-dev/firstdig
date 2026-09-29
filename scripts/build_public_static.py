"""Build a zero-cold-start public snapshot for First Dig.

The public browse experience is intentionally static/CDN-served. Dynamic account,
billing and private detail routes remain on the backend service.
"""
import json
import html as html_lib
import datetime as dt
import os
import shutil
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "public_static"
BUILD_DATA = ROOT / ".public-build-data"
BACKEND = os.getenv("FIRSTDIG_BACKEND", "https://first-dig-night-shift.onrender.com").rstrip("/")
SITE = "https://firstdig.app"

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


def seoify(document: str, path: str, schema=None) -> str:
    """Add canonical/search/social metadata to each static page."""
    canonical = SITE + (path if path.startswith("/") else "/" + path)
    title_match = re.search(r"<title>(.*?)</title>", document, flags=re.I | re.S)
    desc_match = re.search(r'<meta name="description" content="([^"]*)">', document, flags=re.I)
    title = html_lib.unescape(title_match.group(1).strip()) if title_match else "First Dig"
    desc = html_lib.unescape(desc_match.group(1).strip()) if desc_match else "Toronto permit intelligence from First Dig."

    graph = []
    if path == "/":
        graph.extend([
            {
                "@type": "Organization",
                "@id": SITE + "/#organization",
                "name": "First Dig",
                "alternateName": "FirstDig",
                "url": SITE + "/",
                "description": "Toronto construction and business-opening intelligence built from public filings.",
                "founder": {
                    "@type": "Person",
                    "name": "Jackson Lang",
                    "affiliation": {"@type": "CollegeOrUniversity", "name": "University of Toronto"}
                }
            },
            {
                "@type": "WebSite",
                "@id": SITE + "/#website",
                "url": SITE + "/",
                "name": "First Dig",
                "alternateName": "FirstDig",
                "publisher": {"@id": SITE + "/#organization"}
            }
        ])
    elif path in ("/teardown", "/openings"):
        name = "Toronto Building Permits and Construction Leads" if path == "/teardown" else "Toronto Businesses Opening Soon"
        keywords = (
            ["Toronto building permits", "construction leads Toronto", "Toronto demolition permits", "Toronto new house permits"]
            if path == "/teardown"
            else ["Toronto restaurants opening soon", "new businesses Toronto", "Toronto business licences", "restaurant leads Toronto"]
        )
        graph.append({
            "@type": "Dataset",
            "name": name,
            "description": desc,
            "url": canonical,
            "keywords": keywords,
            "creator": {"@id": SITE + "/#organization"},
            "spatialCoverage": {"@type": "Place", "name": "Toronto, Ontario, Canada"}
        })

    if path != "/":
        label = {
            "/teardown": "Toronto Building Permits",
            "/openings": "Businesses Opening Soon",
            "/pricing": "Pricing",
            "/methodology": "Methodology",
            "/terms": "Terms & Privacy",
            "/about": "About First Dig",
        }.get(path, title)
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "First Dig", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": label, "item": canonical},
            ],
        })

    if schema:
        graph.append(schema)

    tags = [
        f'<link rel="canonical" href="{html_lib.escape(canonical, quote=True)}">',
        f'<meta property="og:title" content="{html_lib.escape(title, quote=True)}">',
        f'<meta property="og:description" content="{html_lib.escape(desc, quote=True)}">',
        f'<meta property="og:url" content="{html_lib.escape(canonical, quote=True)}">',
        '<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{html_lib.escape(title, quote=True)}">',
        f'<meta name="twitter:description" content="{html_lib.escape(desc, quote=True)}">',
    ]
    if graph:
        tags.append('<script type="application/ld+json">' + json.dumps(
            {"@context": "https://schema.org", "@graph": graph},
            separators=(",", ":")
        ) + '</script>')
    return document.replace("</head>", "\n" + "\n".join(tags) + "\n</head>", 1)


def rewrite_common(html: str, dashboard=False) -> str:
    # Public browse stays entirely on the static origin. Authentication is not
    # exposed until persistent account storage is production-ready.
    access = "mailto:jacksonjameslang@gmail.com?subject=First%20Dig%20early%20access"
    html = html.replace('href="/app/teardown"', 'href="/teardown"')
    html = html.replace('href="/app/openings"', 'href="/openings"')
    html = re.sub(r'href="/login(?:\\?[^"]*)?"', f'href="{access}"', html)
    html = html.replace('href="/account"', f'href="{access}"')
    html = html.replace('action="/logout"', f'action="{access}"')
    html = html.replace('>Start free trial<', '>Request early access<')
    html = html.replace('>Sign in<', '>Request access<')
    html = html.replace('>Subscribe to see today\'s filings<', '>Request access to current filings<')
    html = html.replace('href="mailto:hello@example.com"', 'href="mailto:jacksonjameslang@gmail.com?subject=First%20Dig"')
    # Prevent redacted public record links from falling through to the sleeping
    # dynamic backend. The public dashboard itself carries the usable signal.
    html = re.sub(r'href="/p/[^"]+"', 'href="/teardown"', html)
    html = re.sub(r'href="/o/[^"]+"', 'href="/openings"', html)
    if dashboard:
        html = html.replace('/static/app.js?v=2', '/static/public-dashboard.js?v=2')
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
        # Fail closed: an empty default browse experience must never replace a
        # previously good production snapshot.
        default_projects = queries.projects(con, {"days": "90"}, full_access=False, limit=20000)[1]
        default_openings = queries.openings(con, {"days": "90", "city": "toronto", "minsig": "1"}, full_access=False, limit=20000)[1]
        if default_projects <= 0 or default_openings <= 0:
            raise RuntimeError(f"refusing empty public snapshot: projects={default_projects}, openings={default_openings}")
        print(f"public defaults: projects_90d={default_projects}; openings_90d={default_openings}")
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
        ("/about", OUT / "about" / "index.html"),
    ]:
        r = client.get(route)
        r.raise_for_status()
        write(dest, seoify(rewrite_common(r.text), route))

    # Public dashboards. Write both historical /app/... paths and clean URLs.
    for product in ("teardown", "openings"):
        r = client.get(f"/app/{product}?days=90")
        r.raise_for_status()
        html = rewrite_common(r.text, dashboard=True)
        clean = seoify(html, f"/{product}")
        write(OUT / product / "index.html", clean)
        duplicate = clean.replace(
            '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">',
            '<meta name="robots" content="noindex,follow">'
        )
        write(OUT / "app" / product / "index.html", duplicate)

    # Search discovery. Keep only canonical public pages in the sitemap.
    today = dt.date.today().isoformat()
    urls = ["/", "/teardown", "/openings", "/pricing", "/methodology", "/about", "/terms"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for route in urls:
        sitemap.append(
            f'<url><loc>{SITE}{route}</loc><lastmod>{today}</lastmod></url>'
        )
    sitemap.append('</urlset>')
    write(OUT / "sitemap.xml", "\n".join(sitemap) + "\n")
    write(OUT / "robots.txt",
          "User-agent: *\nAllow: /\nDisallow: /app/\nSitemap: https://firstdig.app/sitemap.xml\n")

    # Render static-site fallback: useful for direct links without extensions.
    write(OUT / "404.html", seoify(rewrite_common(client.get("/").text), "/"))


if __name__ == "__main__":
    main()
