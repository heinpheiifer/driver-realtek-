"""Django-style API routes expected by ~/OpenTrader frontend."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter

from trading.blackbull_mt5 import mt5_status
from trading.market_data import load_candles_with_fallback

from .django_proxy import django_proxy_enabled
from .mt5_autosync import mt5_autosync

logger = logging.getLogger(__name__)

_INTERVAL_TO_TF = {
    "1m": "M1",
    "m1": "M1",
    "3m": "M5",
    "5m": "M5",
    "m5": "M5",
    "15m": "M15",
    "m15": "M15",
    "30m": "M30",
    "1h": "H1",
    "h1": "H1",
    "60m": "H1",
    "4h": "H4",
    "1d": "D1",
    "d1": "D1",
}

_RANGE_TO_BARS = {
    "1d": 1500,
    "5d": 2000,
    "1w": 2000,
    "1mo": 2500,
    "3mo": 3000,
    "6mo": 3500,
    "1y": 4000,
}


def _parse_interval(interval: str) -> str:
    raw = interval.strip().lower()
    if raw in _INTERVAL_TO_TF:
        return _INTERVAL_TO_TF[raw]
    up = interval.strip().upper()
    if up in {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}:
        return up
    return "M1"


def _parse_range_bars(range_: str | None, timeframe: str) -> int:
    if not range_:
        return 800
    key = range_.strip().lower()
    bars = _RANGE_TO_BARS.get(key, 800)
    if timeframe == "M1" and key == "1d":
        return min(bars, 1500)
    return min(bars, 4000)


def _to_unix(ts: str) -> int:
    try:
        cleaned = ts.replace("Z", "+00:00")
        if " " in cleaned and "T" not in cleaned:
            cleaned = cleaned.replace(" ", "T")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def _bar_rows(candles: list) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in candles:
        ts = c.timestamp
        rows.append(
            {
                "timestamp": ts,
                "time": _to_unix(ts),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
        )
    return rows


def _history_response(
    *,
    symbol: str,
    interval: str,
    tf: str,
    range_: str,
    requested_source: str,
    candles: list,
    source_label: str,
    path: str,
    meta: dict | None,
    fallback: bool = False,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    rows = _bar_rows(candles)
    last = candles[-1]
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "timeframe": tf,
        "range": range_,
        "source": source_label,
        "requested_source": requested_source,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "count": len(rows),
        "last_price": last.close,
        "csv_path": path,
        "used_cache": (meta or {}).get("used_cache") if meta else False,
        "mt5": (meta or {}).get("mt5") if meta else mt5_status() if requested_source == "blackbull" else None,
        "bars": rows,
        "candles": rows,
        "data": rows,
    }


def _try_django_history(
    *,
    symbol: str,
    interval: str,
    range_: str,
    source: str,
) -> dict[str, Any] | None:
    if not django_proxy_enabled():
        return None
    backend = os.environ.get("OPENTRADER_BACKEND_URL", "").strip().rstrip("/")
    if not backend:
        return None
    try:
        resp = requests.get(
            f"{backend}/api/history/",
            params={
                "symbol": symbol,
                "interval": interval,
                "range": range_,
                "source": source,
            },
            timeout=5,
        )
        if resp.ok:
            data = resp.json()
            if isinstance(data, dict) and (data.get("bars") or data.get("candles") or data.get("data")):
                return data
    except requests.RequestException as exc:
        logger.warning("Django history fetch failed: %s", exc)
    return None


router = APIRouter()


@router.get("/api/history")
@router.get("/api/history/")
def opentrader_history(
    symbol: str = "XRPUSD",
    interval: str = "1m",
    range: str = "1d",
    source: str = "blackbull",
    timeframe: str | None = None,
    bars: int | None = None,
) -> dict[str, Any]:
    """OpenTrader Django-compatible OHLCV history (chart calls this for XRPUSD)."""
    tf = _parse_interval(timeframe or interval)
    limit = bars or _parse_range_bars(range, tf)

    django_data = _try_django_history(
        symbol=symbol, interval=interval, range_=range, source=source
    )
    if django_data is not None:
        return django_data

    candles, source_label, path, meta, fallback, reason = load_candles_with_fallback(
        symbol=symbol,
        source=source,
        timeframe=tf,
        bars=limit,
    )

    return _history_response(
        symbol=symbol,
        interval=interval,
        tf=tf,
        range_=range,
        requested_source=source.lower(),
        candles=candles,
        source_label=source_label,
        path=path,
        meta=meta,
        fallback=fallback,
        fallback_reason=reason,
    )


@router.get("/api/mt5/status")
@router.get("/api/mt5/status/")
def opentrader_mt5_status() -> dict[str, Any]:
    status = mt5_status()
    return {
        "connected": bool(status.get("connected")),
        "available": bool(status.get("available")),
        "server": status.get("server"),
        "broker": status.get("broker"),
        "account": status.get("account"),
        "last_error": status.get("last_error"),
        "last_sync": status.get("last_sync"),
        "mt5": status,
        "autosync": mt5_autosync.status,
    }
