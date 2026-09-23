"""Stripe Checkout + Customer Portal + webhook. Fully optional: with no
STRIPE_SECRET_KEY the site runs on free trials and the upgrade page says so."""
import logging

from ..config import (BASE_URL, STRIPE_PRICE_BUNDLE, STRIPE_PRICE_OPENINGS, STRIPE_PRICE_TEARDOWN,
                      STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)

log = logging.getLogger("billing")

PRICES = {"teardown": STRIPE_PRICE_TEARDOWN, "openings": STRIPE_PRICE_OPENINGS, "bundle": STRIPE_PRICE_BUNDLE}


def enabled():
    return bool(STRIPE_SECRET_KEY)


def _stripe():
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def checkout_url(con, user, plan):
    stripe = _stripe()
    price = PRICES.get(plan)
    if not price:
        raise ValueError("unknown plan")
    customer_id = user["stripe_customer_id"]
    if not customer_id:
        c = stripe.Customer.create(email=user["email"], metadata={"user_id": user["id"]})
        customer_id = c["id"]
        con.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer_id, user["id"]))
    s = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price, "quantity": 1}],
        success_url=f"{BASE_URL}/account?checkout=success",
        cancel_url=f"{BASE_URL}/pricing?checkout=cancelled",
        allow_promotion_codes=True,
        subscription_data={"metadata": {"user_id": user["id"], "plan": plan}},
        metadata={"user_id": user["id"], "plan": plan},
    )
    return s["url"]


def portal_url(user):
    stripe = _stripe()
    s = stripe.billing_portal.Session.create(customer=user["stripe_customer_id"], return_url=f"{BASE_URL}/account")
    return s["url"]


def handle_webhook(con, payload, sig_header):
    stripe = _stripe()
    event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    t = event["type"]
    obj = event["data"]["object"]
    if t in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        customer = obj["customer"]
        status = obj["status"] if t != "customer.subscription.deleted" else "canceled"
        plan = (obj.get("metadata") or {}).get("plan")
        if not plan:
            price = obj["items"]["data"][0]["price"]["id"]
            plan = next((k for k, v in PRICES.items() if v == price), None)
        con.execute("UPDATE users SET plan=?, plan_status=? WHERE stripe_customer_id=?", (plan, status, customer))
        log.info("subscription %s -> %s/%s for %s", t, plan, status, customer)
    elif t == "checkout.session.completed":
        customer = obj.get("customer")
        uid = (obj.get("metadata") or {}).get("user_id")
        if customer and uid:
            con.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer, uid))
    return t
