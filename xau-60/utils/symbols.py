"""Broker symbol name resolution (BlackBull / MT5 variants)."""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.mt5_connector import MT5Connector


def symbol_candidates(preferred: str) -> List[str]:
    """Return likely MT5 symbol names for a base symbol (e.g. ETHUSD → ETHUSD.r)."""
    base = preferred.upper().strip()
    extras: List[str] = []
    if base == "ETHUSD":
        extras = ["ETHEREUM", "ETHUSD.i", "ETHUSD.a"]
    elif base == "XAUUSD":
        extras = ["GOLD", "XAUUSD.i", "XAUUSD.a"]
    elif base == "BTCUSD":
        extras = ["BITCOIN", "BTCUSD.i"]

    return [
        base,
        f"{base}.r",
        f"{base}m",
        f"{base}.a",
        f"{base}.i",
        *extras,
    ]


def resolve_broker_symbol(connector: "MT5Connector", preferred: str) -> Optional[str]:
    """First symbol name that exists on the connected broker."""
    seen: set[str] = set()
    for sym in symbol_candidates(preferred):
        if sym in seen:
            continue
        seen.add(sym)
        if connector.get_symbol_info(sym):
            return sym
    return None


def default_trading_symbol() -> str:
    from utils.config import get_env

    return get_env("DEFAULT_TRADING_SYMBOL", "ETHUSD") or "ETHUSD"
