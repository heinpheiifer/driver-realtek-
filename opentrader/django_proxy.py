"""Proxy market-data API to original OpenTrader Django backend (has live MT5).

Enabled when OPENTRADER_DJANGO_PROXY=1 OR OPENTRADER_BACKEND_URL is set.
This is how your OLD app worked: chart on :8010 → Django on :8000 → MT5 bridge.
"""
from __future__ import annotations

import os
from typing import Callable

import requests
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

PROXY_PREFIXES = (
    "/api/history",
    "/api/candles",
    "/api/bars",
    "/api/symbols",
    "/api/mt5",
    "/api/market",
    "/api/data",
)


def django_proxy_enabled() -> bool:
    raw = os.environ.get("OPENTRADER_DJANGO_PROXY", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return bool(os.environ.get("OPENTRADER_BACKEND_URL", "").strip())


def backend_url() -> str | None:
    if not django_proxy_enabled():
        return None
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
                timeout=15,
                allow_redirects=False,
            )
            if resp.status_code >= 400:
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
