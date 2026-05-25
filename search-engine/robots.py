"""robots.txt fetching and caching."""

from __future__ import annotations

import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from config import REQUEST_TIMEOUT_SEC, USER_AGENT

_CACHE: dict[str, tuple[RobotFileParser, float]] = {}
_CACHE_TTL_SEC = 3600


def _robots_url(origin: str) -> str:
    return f"{origin.rstrip('/')}/robots.txt"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    return f"{scheme}://{netloc}"


def get_parser(domain_url: str, client: httpx.Client) -> RobotFileParser:
    origin = _origin(domain_url)
    now = time.time()
    cached = _CACHE.get(origin)
    if cached and now - cached[1] < _CACHE_TTL_SEC:
        return cached[0]

    rp = RobotFileParser()
    rp.set_url(_robots_url(origin))
    try:
        resp = client.get(_robots_url(origin), timeout=REQUEST_TIMEOUT_SEC)
        if resp.status_code == 200 and resp.text:
            rp.parse(resp.text.splitlines())
        else:
            # No robots.txt — allow by default
            rp.parse([])
    except (httpx.HTTPError, OSError):
        rp.parse([])

    _CACHE[origin] = (rp, now)
    return rp


def can_fetch(url: str, client: httpx.Client) -> bool:
    rp = get_parser(url, client)
    return rp.can_fetch(USER_AGENT, url)
