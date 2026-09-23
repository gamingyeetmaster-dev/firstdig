"""Outbound email. Uses Resend when RESEND_API_KEY is set; otherwise logs
the message so everything still works locally."""
import logging

import httpx

from ..config import EMAIL_FROM, RESEND_API_KEY

log = logging.getLogger("email")


def send(to, subject, html, text=None):
    if not RESEND_API_KEY:
        log.warning("EMAIL (not sent, no RESEND_API_KEY) to=%s subject=%s\n%s", to, subject, text or html[:2000])
        return {"id": None, "delivered": False}
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html, "text": text or ""},
        timeout=30,
    )
    if r.status_code >= 300:
        log.error("Resend error %s: %s", r.status_code, r.text)
        return {"id": None, "delivered": False, "error": r.text}
    return {"id": r.json().get("id"), "delivered": True}
