"""A deliberately small FastAPI service.

The point of this repository is the *pipeline*, not the app. The app is just
real enough to lint, test, build, scan, sign, and deploy as a container.
"""

from __future__ import annotations

import hashlib
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
GIT_SHA = os.getenv("GIT_SHA", "dev")

# Conservative defaults for a JSON API: deny framing, no MIME sniffing, no
# referrer leakage, and a locked-down CSP since we never serve HTML/JS.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        # Don't advertise the server implementation.
        response.headers["Server"] = "service"
        return response


app = FastAPI(title="utiso-secure-pipeline", version=APP_VERSION)
app.add_middleware(SecurityHeadersMiddleware)


class HashRequest(BaseModel):
    # Bound the input so a single request can't be used to burn CPU/memory.
    text: str = Field(..., min_length=1, max_length=4096)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": APP_VERSION, "git_sha": GIT_SHA}


@app.post("/api/hash")
def hash_text(payload: HashRequest) -> JSONResponse:
    digest = hashlib.sha256(payload.text.encode("utf-8")).hexdigest()
    return JSONResponse({"algorithm": "sha256", "hex": digest})
