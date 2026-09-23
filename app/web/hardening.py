"""Small protections for a public deployment: rate limits on the login
endpoint, security headers, and an Origin check on state-changing forms."""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from ..config import BASE_URL

_buckets = defaultdict(deque)   # key -> deque of timestamps


def allow(key, limit, window_s):
    now = time.time()
    q = _buckets[key]
    while q and q[0] < now - window_s:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def client_ip(request):
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


class Hardening(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        ip = client_ip(request)

        # login: 10 requests / 10 min per IP; also global 200 / 10 min
        if request.method == "POST" and path == "/login":
            if not allow(f"login:{ip}", 10, 600) or not allow("login:all", 200, 600):
                return PlainTextResponse("Too many sign-in attempts. Try again in a few minutes.", status_code=429)
        # cheap global limit per IP for everything else (bots hammering export/api)
        if not allow(f"all:{ip}", 600, 60):
            return PlainTextResponse("Slow down.", status_code=429)

        # Origin check on browser form posts (cookie is SameSite=Lax too)
        if request.method == "POST" and path not in ("/billing/webhook",):
            origin = request.headers.get("origin") or ""
            if origin and not origin.rstrip("/").endswith(BASE_URL.split("://", 1)[-1].rstrip("/")) and not origin.startswith("http://127.0.0.1"):
                return PlainTextResponse("Bad origin", status_code=403)

        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if BASE_URL.startswith("https"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp
