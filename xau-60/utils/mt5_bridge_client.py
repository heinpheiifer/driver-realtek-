"""
MetaTrader5 HTTP bridge client for Linux/macOS.

When MT5_BRIDGE_URL is set, this module replaces the mock MT5 API and forwards
calls to a Windows machine running bridge/server.py with MetaTrader 5.
"""
from __future__ import annotations

import time as time_module
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

from utils.config import get_env

# ============================================================================
# MT5 Constants (matching real MT5 API)
# ============================================================================

TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 60
TIMEFRAME_H4 = 240
TIMEFRAME_D1 = 1440
TIMEFRAME_W1 = 10080
TIMEFRAME_MN1 = 43200

ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5
ORDER_TYPE_BUY_STOP_LIMIT = 6
ORDER_TYPE_SELL_STOP_LIMIT = 7

TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_SLTP = 6
TRADE_ACTION_MODIFY = 7
TRADE_ACTION_REMOVE = 8

ORDER_TIME_GTC = 0
ORDER_TIME_SPECIFIED = 2

ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_REQUOTE = 10004

DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1


def _current_time() -> int:
    return int(time_module.time())


@dataclass
class BridgeAccountInfo:
    login: int = 0
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    margin_free: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    currency: str = "USD"
    leverage: int = 100
    server: str = ""
    company: str = ""
    trade_allowed: bool = True
    trade_expert: bool = True


@dataclass
class BridgeSymbolInfo:
    name: str = ""
    description: str = ""
    point: float = 0.01
    digits: int = 2
    spread: int = 0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    trade_tick_size: float = 0.01
    trade_tick_value: float = 1.0
    trade_contract_size: float = 100.0
    trade_mode: int = 4
    trade_stops_level: int = 0
    trade_freeze_level: int = 0


@dataclass
class BridgeTick:
    time: int = field(default_factory=_current_time)
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0


@dataclass
class BridgePosition:
    ticket: int = 0
    time: int = field(default_factory=_current_time)
    type: int = ORDER_TYPE_BUY
    magic: int = 0
    volume: float = 0.0
    price_open: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    price_current: float = 0.0
    profit: float = 0.0
    symbol: str = ""
    comment: str = ""


@dataclass
class BridgeOrder:
    ticket: int = 0
    symbol: str = ""
    type: int = 0
    volume_current: float = 0.0
    price_open: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    time_setup: int = 0
    time_expiration: int = 0
    magic: int = 0
    comment: str = ""


@dataclass
class BridgeDeal:
    ticket: int = 0
    order: int = 0
    time: int = 0
    type: int = DEAL_TYPE_BUY
    volume: float = 0.0
    price: float = 0.0
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    magic: int = 0
    symbol: str = ""
    comment: str = ""


@dataclass
class BridgeOrderResult:
    retcode: int = TRADE_RETCODE_DONE
    deal: int = 0
    order: int = 0
    volume: float = 0.0
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    comment: str = ""
    request_id: int = 0


@dataclass
class BridgeTerminalInfo:
    connected: bool = True
    trade_allowed: bool = True
    company: str = ""
    name: str = "MT5 Bridge"
    path: str = ""


class BridgeHTTPClient:
    """Low-level HTTP client for the MT5 bridge server."""

    def __init__(self, base_url: str, token: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._last_error: Tuple[int, str] = (0, "")
        self.initialized = False
        self.connected = False

    def _set_error(self, code: int, message: str) -> None:
        self._last_error = (code, message)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers,
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                detail = response.text
                try:
                    payload = response.json()
                    detail = payload.get("detail", payload)
                    if isinstance(detail, dict):
                        code = int(detail.get("code", response.status_code))
                        message = str(detail.get("message", detail))
                    else:
                        code = response.status_code
                        message = str(detail)
                except Exception:
                    code = response.status_code
                    message = detail or response.reason
                self._set_error(code, message)
                return None
            if response.content:
                return response.json()
            return {}
        except requests.RequestException as exc:
            self._set_error(1, f"Bridge request failed: {exc}")
            return None

    def health(self) -> bool:
        data = self._request("GET", "/api/health")
        return bool(data and data.get("status") == "ok")


_client = BridgeHTTPClient(
    get_env("MT5_BRIDGE_URL", "").strip().rstrip("/"),
    get_env("MT5_BRIDGE_TOKEN", "").strip(),
    float(get_env("MT5_BRIDGE_TIMEOUT", 30, float)),
)


def _rates_to_numpy(rates: List[Dict[str, Any]]) -> Optional[np.ndarray]:
    if not rates:
        return None
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]
    rows = [
        (
            int(row["time"]),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["tick_volume"]),
            int(row["spread"]),
            int(row["real_volume"]),
        )
        for row in rates
    ]
    return np.array(rows, dtype=dtype)


def initialize(path: str = None, login: int = None, password: str = None,
               server: str = None, timeout: int = 60000, portable: bool = False) -> bool:
    if not _client.base_url:
        _client._set_error(1, "MT5_BRIDGE_URL is not configured")
        return False

    if not _client.health():
        return False

    payload: Dict[str, Any] = {"timeout": timeout}
    if path:
        payload["path"] = path

    data = _client._request("POST", "/api/initialize", json=payload)
    if data is None:
        return False

    _client.initialized = True
    _client.connected = True
    _client._set_error(0, "")
    return True


def shutdown() -> None:
    _client._request("POST", "/api/shutdown")
    _client.initialized = False
    _client.connected = False


def login(login: int, password: str = "", server: str = "", timeout: int = 60000) -> bool:
    if not _client.initialized:
        _client._set_error(1, "MT5 bridge not initialized")
        return False

    data = _client._request(
        "POST",
        "/api/login",
        json={"login": login, "password": password, "server": server, "timeout": timeout},
    )
    if data is None:
        return False

    _client.connected = True
    _client._set_error(0, "")
    return True


def last_error() -> tuple:
    err = _client._request("GET", "/api/last_error")
    if err:
        return int(err.get("code", _client._last_error[0])), str(err.get("message", _client._last_error[1]))
    return _client._last_error


def terminal_info() -> Optional[BridgeTerminalInfo]:
    if not _client.initialized:
        return None
    data = _client._request("GET", "/api/terminal_info")
    if not data:
        return None
    return BridgeTerminalInfo(**data)


def account_info() -> Optional[BridgeAccountInfo]:
    if not _client.connected:
        return None
    data = _client._request("GET", "/api/account_info")
    if not data:
        return None
    return BridgeAccountInfo(**data)


def symbol_info(symbol: str) -> Optional[BridgeSymbolInfo]:
    if not _client.connected:
        return None
    data = _client._request("GET", "/api/symbol_info", params={"symbol": symbol})
    if not data:
        return None
    return BridgeSymbolInfo(**data)


def symbol_info_tick(symbol: str) -> Optional[BridgeTick]:
    if not _client.connected:
        return None
    data = _client._request("GET", "/api/symbol_info_tick", params={"symbol": symbol})
    if not data:
        return None
    return BridgeTick(**data)


def symbol_select(symbol: str, enable: bool = True) -> bool:
    data = _client._request("POST", "/api/symbol_select", json={"symbol": symbol, "enable": enable})
    return bool(data and data.get("ok"))


def copy_rates_from(symbol: str, timeframe: int, date_from: datetime, count: int) -> Optional[np.ndarray]:
    if not _client.connected:
        return None
    data = _client._request(
        "GET",
        "/api/copy_rates_from",
        params={"symbol": symbol, "timeframe": timeframe, "date_from": date_from.isoformat(), "count": count},
    )
    if not data:
        return None
    return _rates_to_numpy(data.get("rates", []))


def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int) -> Optional[np.ndarray]:
    if not _client.connected:
        return None
    data = _client._request(
        "GET",
        "/api/copy_rates_from_pos",
        params={"symbol": symbol, "timeframe": timeframe, "start_pos": start_pos, "count": count},
    )
    if not data:
        return None
    return _rates_to_numpy(data.get("rates", []))


def copy_rates_range(symbol: str, timeframe: int, date_from: datetime, date_to: datetime) -> Optional[np.ndarray]:
    if not _client.connected:
        return None
    data = _client._request(
        "GET",
        "/api/copy_rates_range",
        params={
            "symbol": symbol,
            "timeframe": timeframe,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
    )
    if not data:
        return None
    return _rates_to_numpy(data.get("rates", []))


def order_send(request: dict) -> Optional[BridgeOrderResult]:
    if not _client.connected:
        _client._set_error(1, "Not connected")
        return None

    data = _client._request("POST", "/api/order_send", json={"request": request})
    if not data:
        return None

    return BridgeOrderResult(
        retcode=int(data.get("retcode", TRADE_RETCODE_DONE)),
        deal=int(data.get("deal", 0)),
        order=int(data.get("order", 0)),
        volume=float(data.get("volume", 0.0)),
        price=float(data.get("price", 0.0)),
        bid=float(data.get("bid", 0.0)),
        ask=float(data.get("ask", 0.0)),
        comment=str(data.get("comment", "")),
        request_id=int(data.get("request_id", 0)),
    )


def positions_get(symbol: str = None, ticket: int = None) -> Optional[tuple]:
    if not _client.connected:
        return None

    params: Dict[str, Any] = {}
    if symbol:
        params["symbol"] = symbol
    if ticket is not None:
        params["ticket"] = ticket

    data = _client._request("GET", "/api/positions", params=params or None)
    if data is None:
        return None

    positions = tuple(BridgePosition(**row) for row in data.get("positions", []))
    return positions if positions else None


def orders_get(symbol: str = None) -> Optional[tuple]:
    if not _client.connected:
        return None

    params = {"symbol": symbol} if symbol else None
    data = _client._request("GET", "/api/orders", params=params)
    if data is None:
        return None

    orders = tuple(BridgeOrder(**row) for row in data.get("orders", []))
    return orders if orders else None


def history_deals_get(date_from: datetime, date_to: datetime) -> Optional[tuple]:
    if not _client.connected:
        return None

    data = _client._request(
        "GET",
        "/api/history_deals",
        params={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
    )
    if data is None:
        return None

    deals = tuple(BridgeDeal(**row) for row in data.get("deals", []))
    return deals if deals else None


def bridge_reachable() -> bool:
    """Return True if the configured bridge URL responds to /api/health."""
    if not _client.base_url:
        return False
    return _client.health()


__version__ = "5.0.45.bridge"
__name__ = "MetaTrader5 (Bridge)"
