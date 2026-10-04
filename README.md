# First Dig

Two subscription data feeds built from public filings, refreshed daily:

- **Teardown Feed** — every teardown, new house, multiplex, garden suite and major addition filed with Toronto Building, rolled up per address, classified, geocoded, with the builder's name. For pool, landscape, fence, window, millwork and moving companies.
- **Opening Soon** — restaurants, bars, cafés, clinics, salons and shops 60 to 120 days before they open, joined by address from three independent filings: AGCO liquor licence applications, City of Toronto business licences, and commercial fit-out building permits. For POS/payments, insurance, distributors, signage, cleaning.

One Python process, one SQLite file, no external services required to run. Stripe and Resend plug in through environment variables when you're ready to charge and email.

## Run it locally

```bash
pip3 install -r requirements.txt
cp .env.example .env            # edit ADMIN_EMAILS to your address
python3 -m app.pipeline.run     # downloads ~300 MB of open data, builds the DB (~2 min first time, ~10 s after)
./run_dev.sh                    # http://127.0.0.1:8000
```

Sign in with the email in `ADMIN_EMAILS`. In dev mode the magic link is printed on screen because no email provider is configured.

## Layout

```
app/config.py            env vars, product definitions, source URLs
app/db.py                SQLite schema
app/pipeline/fetch.py    download + cache the five public files
app/pipeline/geo.py      address-point geocoder and neighbourhood lookup
app/pipeline/permits.py  permits -> projects (Teardown Feed)
app/pipeline/openings.py liquor + licences + permits -> openings (Opening Soon)
app/pipeline/run.py      `python -m app.pipeline.run [--force]`
app/web/main.py          FastAPI routes
app/web/auth.py          magic-link login, trials, entitlements
app/web/billing.py       Stripe Checkout, portal, webhook
app/web/emailer.py       Resend (logs when unconfigured)
app/web/digest.py        daily email digests
app/web/scheduler.py     in-process daily refresh (ENABLE_SCHEDULER=1)
app/web/auth_store.py    optional durable Postgres state (AUTH_DATABASE_URL)
app/web/templates/       Jinja pages + email templates
app/web/static/          CSS + map/filter JS
data/                    raw downloads, signals.db, geo index (gitignored)
```

## Data sources

| Source | Publisher | Refresh |
|---|---|---|
| Building Permits – Active Permits | City of Toronto Open Data | daily |
| Municipal Licensing & Standards – Business Licences and Permits | City of Toronto Open Data | daily |
| Status of Current Liquor Sales Licence Applications | AGCO Open Data | daily |
| Address Points (Municipal) | City of Toronto Open Data | weekly |
| Neighbourhoods (158) | City of Toronto Open Data | monthly |

All are under the Open Government Licence – Toronto / Ontario.

## Operations

- `GET /tasks/refresh?key=CRON_SECRET` pulls sources and rebuilds. Add `&force=1` to ignore the download cache.
- `GET /tasks/digests?key=CRON_SECRET` sends the daily emails. Add `&dry=1` to preview.
- With `ENABLE_SCHEDULER=1`, the in-process scheduler runs once during `REFRESH_HOUR` in Toronto time. `.github/workflows/daily.yml` is a zero-secret wake-up for sleeping free hosts: it pings `/health` at the two UTC times that bracket 06:00 Toronto across DST, and only the wake landing inside the configured local hour can trigger the scheduler. Manual `/tasks/*` endpoints remain protected by `CRON_SECRET`.
- Set `AUTH_DATABASE_URL` before treating trials/accounts/billing as durable on an ephemeral host. Public permit/opening data stays local and rebuildable; only commercial state moves to Postgres.
- Current validation datastore note: the existing free Render database `first-dig-auth` expires 2026-10-28. Treat it as a zero-cost validation bridge, not permanent production storage; migrate durable state before that date if validation continues.
- `/admin` (admins only) shows users, runs and table counts. `/health` is for uptime checks.

## Deploy

See [LAUNCH.md](LAUNCH.md) for the step-by-step checklist. Short version: `fly launch`, create a volume, set secrets, `fly deploy`.
