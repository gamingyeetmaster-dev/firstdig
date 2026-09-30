"""Inbound email forwarding for the First Dig custom mailbox."""
import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
import os
import time
from email.utils import parseaddr

import httpx

from ..config import EMAIL_FROM, RESEND_API_KEY

log = logging.getLogger("inbound-email")

RESEND_API = "https://api.resend.com"
INBOUND_ADDRESS = os.getenv("FIRSTDIG_INBOUND_ADDRESS", "jackson@firstdig.app").strip().lower()
FORWARD_TO = os.getenv("FIRSTDIG_FORWARD_TO", "").strip()
WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "").strip()
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class InboundError(RuntimeError):
    pass


def verify_event(payload: bytes, headers) -> dict:
    """Verify Resend/Svix signature against the raw body, then parse JSON."""
    if not WEBHOOK_SECRET:
        raise InboundError("RESEND_WEBHOOK_SECRET is not configured")

    msg_id = headers.get("svix-id") or headers.get("webhook-id")
    timestamp = headers.get("svix-timestamp") or headers.get("webhook-timestamp")
    signature_header = headers.get("svix-signature") or headers.get("webhook-signature")
    if not msg_id or not timestamp or not signature_header:
        raise InboundError("missing webhook signature headers")

    try:
        ts = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise InboundError("invalid webhook timestamp") from exc

    if abs(int(time.time()) - ts) > 300:
        raise InboundError("webhook timestamp outside tolerance")

    try:
        encoded_secret = WEBHOOK_SECRET.split("_", 1)[1]
        key = base64.b64decode(encoded_secret)
    except Exception as exc:
        raise InboundError("invalid webhook secret") from exc

    signed = f"{msg_id}.{timestamp}.".encode("utf-8") + payload
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")

    candidates = []
    for token in signature_header.split():
        if "," not in token:
            continue
        version, signature = token.split(",", 1)
        if version == "v1":
            candidates.append(signature)

    if not candidates or not any(hmac.compare_digest(sig, expected) for sig in candidates):
        raise InboundError("invalid webhook signature")

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InboundError("invalid webhook JSON") from exc


def _headers() -> dict:
    if not RESEND_API_KEY:
        raise InboundError("RESEND_API_KEY is not configured")
    return {"Authorization": f"Bearer {RESEND_API_KEY}"}


def _get_json(path: str) -> dict:
    r = httpx.get(f"{RESEND_API}{path}", headers=_headers(), timeout=30)
    if r.status_code >= 300:
        raise InboundError(f"Resend GET failed ({r.status_code}): {r.text[:500]}")
    data = r.json()
    return data.get("data", data) if isinstance(data, dict) else data


def _address(value: str) -> str:
    return parseaddr(value or "")[1].strip().lower()


def _download_attachments(email_id: str) -> tuple[list[dict], list[str]]:
    listing = _get_json(f"/emails/receiving/{email_id}/attachments")
    rows = listing.get("data", listing) if isinstance(listing, dict) else listing
    if not isinstance(rows, list):
        rows = []

    attachments = []
    skipped = []
    total = 0

    for att in rows:
        filename = att.get("filename") or "attachment"
        download_url = att.get("download_url")
        if not download_url:
            skipped.append(filename)
            continue

        size = int(att.get("size") or 0)
        if size and total + size > MAX_ATTACHMENT_BYTES:
            skipped.append(filename)
            continue

        r = httpx.get(download_url, timeout=30, follow_redirects=True)
        if r.status_code >= 300:
            skipped.append(filename)
            continue

        blob = r.content
        if total + len(blob) > MAX_ATTACHMENT_BYTES:
            skipped.append(filename)
            continue

        total += len(blob)
        attachments.append({
            "filename": filename,
            "content": base64.b64encode(blob).decode("ascii"),
        })

    return attachments, skipped


def forward_received(event: dict) -> dict:
    """Forward one verified email.received event to the configured Gmail inbox."""
    if event.get("type") != "email.received":
        return {"ok": True, "ignored": "event_type"}
    if not FORWARD_TO:
        raise InboundError("FIRSTDIG_FORWARD_TO is not configured")

    data = event.get("data") or {}
    email_id = data.get("email_id")
    recipients = {_address(v) for v in (data.get("to") or [])}

    # Resend receiving is domain-wide. Only expose the mailbox explicitly chosen
    # for this service rather than turning the whole domain into a catch-all.
    if INBOUND_ADDRESS not in recipients:
        return {"ok": True, "ignored": "recipient"}

    if not email_id:
        raise InboundError("email.received event missing email_id")

    email = _get_json(f"/emails/receiving/{email_id}")
    original_from = email.get("from") or data.get("from") or "Unknown sender"
    subject = email.get("subject") or data.get("subject") or "(no subject)"
    original_html = email.get("html") or ""
    original_text = email.get("text") or ""

    attachments, skipped = _download_attachments(email_id)

    skipped_html = ""
    skipped_text = ""
    if skipped:
        names = ", ".join(skipped)
        skipped_html = f"<p><strong>Attachment note:</strong> {html_lib.escape(names)} could not be forwarded automatically.</p>"
        skipped_text = f"\nAttachment note: {names} could not be forwarded automatically.\n"

    banner_html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;"
        "padding:12px;border:1px solid #ddd;margin-bottom:16px\">"
        "<strong>Forwarded from jackson@firstdig.app</strong><br>"
        f"From: {html_lib.escape(original_from)}<br>"
        f"Subject: {html_lib.escape(subject)}"
        f"{skipped_html}</div>"
    )
    body_html = banner_html + (original_html or f"<pre>{html_lib.escape(original_text)}</pre>")
    body_text = (
        "Forwarded from jackson@firstdig.app\n"
        f"From: {original_from}\n"
        f"Subject: {subject}\n"
        f"{skipped_text}\n"
        f"{original_text}"
    )

    payload = {
        "from": EMAIL_FROM,
        "to": [FORWARD_TO],
        "subject": f"Fwd: {subject}",
        "html": body_html,
        "text": body_text,
        "reply_to": [original_from],
    }
    if attachments:
        payload["attachments"] = attachments

    r = httpx.post(
        f"{RESEND_API}/emails",
        headers={**_headers(), "Idempotency-Key": f"firstdig-forward-{email_id}"},
        json=payload,
        timeout=30,
    )
    if r.status_code >= 300:
        raise InboundError(f"Resend forward failed ({r.status_code}): {r.text[:500]}")

    result = r.json()
    log.info("forwarded inbound email id=%s resend_send_id=%s", email_id, result.get("id"))
    return {"ok": True, "forwarded": True, "email_id": email_id, "send_id": result.get("id")}
