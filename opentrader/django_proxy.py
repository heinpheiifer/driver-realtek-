"""Proxy market-data API to original OpenTrader Django backend (has MT5)."""
from __future__ import annotations

import os
from typing import Callable

import requests
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Old OpenTrader chart expects these from Django/MT5 backend.
# /api/history and /api/symbols are handled locally (Django fetch + fallbacks).
PROXY_PREFIXES = (
    "/api/candles",
    "/api/bars",
    "/api/mt5",
    "/api/market",
    "/api/data",
)
# Bookmap SSE stays on this engine — do not proxy /api/bookmap/stream


def backend_url() -> str | None:
    raw = os.environ.get("OPENTRADER_BACKEND_URL", "").strip().rstrip("/")
    return raw or None


def should_proxy(path: str) -> bool:
    return any(path == p or path.startswith(f"{p}/") for p in PROXY_PREFIXES)


class DjangoBackendProxy(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        backend = backend_url()
        if not backend or not should_proxy(request.url.path):
            return await call_next(request)

        target = f"{backend}{request.url.path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"

        try:
            body = await request.body()
            headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length")
            }
            resp = requests.request(
                method=request.method,
                url=target,
                headers=headers,
                data=body if body else None,
                timeout=30,
                allow_redirects=False,
            )
            if resp.status_code >= 500:
                return await call_next(request)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding", "connection")
                },
                media_type=resp.headers.get("content-type"),
            )
        except requests.RequestException:
            return await call_next(request)
