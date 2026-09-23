"""Create the three subscription prices and the webhook endpoint in Stripe.
Idempotent: looks up existing objects by metadata before creating.

Usage:  STRIPE_SECRET_KEY=sk_... BASE_URL=https://yourdomain python3 scripts/stripe_setup.py
Prints STRIPE_PRICE_* and STRIPE_WEBHOOK_SECRET lines ready for .env.
"""
import os
import sys

import stripe

from app.config import BASE_URL, BUNDLE_PRICE_MONTHLY, PRODUCTS

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
if not stripe.api_key.startswith("sk_"):
    sys.exit("set STRIPE_SECRET_KEY")

PLANS = [
    ("teardown", PRODUCTS["teardown"]["name"], PRODUCTS["teardown"]["price_monthly"]),
    ("openings", PRODUCTS["openings"]["name"], PRODUCTS["openings"]["price_monthly"]),
    ("bundle", "Both feeds", BUNDLE_PRICE_MONTHLY),
]


def find_price(plan):
    for p in stripe.Price.list(active=True, limit=100, expand=["data.product"]).auto_paging_iter():
        if (p.get("metadata") or {}).get("plan") == plan and p["recurring"] and p["currency"] == "cad":
            return p
    return None


out = {}
for plan, name, amount in PLANS:
    price = find_price(plan)
    if not price:
        product = stripe.Product.create(name=name, metadata={"plan": plan})
        price = stripe.Price.create(product=product["id"], unit_amount=amount * 100, currency="cad",
                                    recurring={"interval": "month"}, metadata={"plan": plan}, tax_behavior="exclusive")
        print(f"created {name}: {price['id']}", file=sys.stderr)
    out[f"STRIPE_PRICE_{plan.upper()}"] = price["id"]

url = f"{BASE_URL}/billing/webhook"
events = ["checkout.session.completed", "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"]
existing = next((w for w in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter() if w["url"] == url), None)
if existing:
    print(f"webhook exists ({existing['id']}); its signing secret is only shown once at creation. If you lost it, delete the endpoint in the Stripe dashboard and re-run.", file=sys.stderr)
else:
    w = stripe.WebhookEndpoint.create(url=url, enabled_events=events, description="Signals subscriptions")
    out["STRIPE_WEBHOOK_SECRET"] = w["secret"]
    print(f"created webhook {w['id']} -> {url}", file=sys.stderr)

for k, v in out.items():
    print(f"{k}={v}")
