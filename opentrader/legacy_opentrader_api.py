"""Django-style API routes expected by ~/OpenTrader frontend."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from trading.blackbull_mt5 import mt5_status
from trading.market_data import BlackbullDataError, load_market_candles

from .mt5_autosync import mt5_autosync

router = APIRouter()

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
    try:
        candles, source_label, path, meta = load_market_candles(
            symbol=symbol,
            source=source,
            timeframe=tf,
            bars=limit,
        )
    except BlackbullDataError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(exc),
                "mt5": (exc.meta or {}).get("mt5"),
                "hint": "Start Django backend or MT5 bridge — see opentrader/BLACKBULL_OLD_APP.md",
            },
        ) from exc
    if not candles:
        raise HTTPException(status_code=404, detail=f"No history for {symbol} ({source})")

    rows = _bar_rows(candles)
    last = candles[-1]
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "timeframe": tf,
        "range": range,
        "source": source_label,
        "requested_source": source.lower(),
        "count": len(rows),
        "last_price": last.close,
        "csv_path": path,
        "used_cache": (meta or {}).get("used_cache") if meta else False,
        "mt5": (meta or {}).get("mt5") if meta else mt5_status() if source.lower() == "blackbull" else None,
        "bars": rows,
        "candles": rows,
        "data": rows,
    }


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
