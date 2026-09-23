"""Central configuration. Everything comes from environment variables with
sane local defaults so the whole product runs with zero accounts."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "signals.db"))

# Public URL of the site (used in emails and Stripe redirects)
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DEV_MODE = os.getenv("DEV_MODE", "1") == "1"
CRON_SECRET = os.getenv("CRON_SECRET", "dev-cron")
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}

# Email (Resend). When unset, emails are printed to the log and, in DEV_MODE,
# magic links are shown on screen.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "First Dig <hello@example.com>")

# Stripe. When unset, every signed-in user gets a free trial and the
# "Upgrade" button explains billing is not live yet.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_TEARDOWN = os.getenv("STRIPE_PRICE_TEARDOWN", "")
STRIPE_PRICE_OPENINGS = os.getenv("STRIPE_PRICE_OPENINGS", "")
STRIPE_PRICE_BUNDLE = os.getenv("STRIPE_PRICE_BUNDLE", "")

TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "14"))
# Free (logged-out) view shows records older than this many days, with
# builder names, costs and contact details removed.
FREE_DELAY_DAYS = int(os.getenv("FREE_DELAY_DAYS", "21"))

PRODUCTS = {
    "teardown": {
        "slug": "teardown",
        "name": "Teardown Feed",
        "tagline": "Every new house, demolition, multiplex and major addition filed in Toronto, the day it lands.",
        "price_monthly": 79,
        "price_env": "STRIPE_PRICE_TEARDOWN",
    },
    "openings": {
        "slug": "openings",
        "name": "Opening Soon",
        "tagline": "Restaurants, bars, clinics and shops 60 to 120 days before they open, from three public filings joined together.",
        "price_monthly": 99,
        "price_env": "STRIPE_PRICE_OPENINGS",
    },
}
BUNDLE_PRICE_MONTHLY = 149

# Source URLs (all public, no auth)
SOURCES = {
    "permits_active": "https://ckan0.cf.opendata.inter.prod-toronto.ca/datastore/dump/6d0229af-bc54-46de-9c2b-26759b01dd05",
    "business_licences": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/57b2285f-4f80-45fb-ae3e-41a02c3a137f/resource/54bddc5e-92d9-4102-89c1-43e82f8f4d2d/download/business-licences-data.csv",
    "agco_liquor": "https://www.agco.ca/sites/default/files/opendata/LiquorApplicationsUndergoingPublicNotice.csv",
    "address_points": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv",
    "neighbourhoods": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/fc443770-ef0a-4025-9c2c-2cb558bfab00/resource/0719053b-28b7-48ea-b863-068823a93aaa/download/neighbourhoods-4326.geojson",
}
