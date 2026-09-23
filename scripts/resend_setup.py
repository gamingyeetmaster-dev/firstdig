"""Register the sending domain in Resend and print the DNS records to add.

Usage:  RESEND_API_KEY=re_... python3 scripts/resend_setup.py yourdomain.com
Re-run any time to see verification status.
"""
import os
import sys

import httpx

key = os.environ.get("RESEND_API_KEY", "")
if not key or len(sys.argv) < 2:
    sys.exit("usage: RESEND_API_KEY=re_... python3 scripts/resend_setup.py yourdomain.com")
domain = sys.argv[1]
h = {"Authorization": f"Bearer {key}"}

existing = next((d for d in httpx.get("https://api.resend.com/domains", headers=h, timeout=30).json().get("data", []) if d["name"] == domain), None)
if existing:
    d = httpx.get(f"https://api.resend.com/domains/{existing['id']}", headers=h, timeout=30).json()
else:
    d = httpx.post("https://api.resend.com/domains", headers=h, json={"name": domain, "region": "us-east-1"}, timeout=30).json()
    if "id" not in d:
        sys.exit(f"Resend error: {d}")

print(f"Domain {domain}: status = {d.get('status')}\n")
print("Add these DNS records at your registrar:\n")
print(f"{'TYPE':<6} {'NAME':<40} {'VALUE':<70} {'STATUS'}")
for r in d.get("records", []):
    print(f"{r['type']:<6} {r['name']:<40} {r['value'][:70]:<70} {r.get('status','')}")
if d.get("status") != "verified":
    print("\nThen click Verify in the Resend dashboard (or re-run this script after a few minutes).")
    if not existing:
        httpx.post(f"https://api.resend.com/domains/{d['id']}/verify", headers=h, timeout=30)
