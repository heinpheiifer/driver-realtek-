"""
MetaTrader5 client for MT5 running in Wine on the same Linux machine.

Uses the mt5linux RPyC bridge: Windows Python (inside Wine) runs MetaTrader5
and exposes it to Linux Python on localhost.

Prerequisites:
  1. MT5 terminal running in Wine (logged into BlackBull)
  2. Windows Python installed inside Wine with: pip install MetaTrader5 mt5linux
  3. RPyC server running: wine python -m mt5linux  (see scripts/start-wine-mt5linux.sh)
  4. Linux venv: pip install mt5linux
  5. .env: MT5_WINE_ENABLED=true
"""
from __future__ import annotations

import socket
from typing import Any, Optional, Tuple

from utils.config import get_env

_client: Any = None
_last_error: Tuple[int, str] = (0, "")
_initialized = False


def _wine_host() -> str:
    return get_env("MT5_WINE_HOST", "localhost") or "localhost"


def _wine_port() -> int:
    return get_env("MT5_WINE_PORT", 18812, int)


def _wine_timeout() -> int:
    return get_env("MT5_WINE_TIMEOUT", 300, int)


def _set_error(code: int, message: str) -> None:
    global _last_error
    _last_error = (code, message)


def _ensure_client():
    """Create mt5linux client (connects RPyC to Wine-side Python)."""
    global _client
    if _client is not None:
        return _client

    try:
        from mt5linux import MetaTrader5
    except ImportError as exc:
        raise RuntimeError(
            "mt5linux is not installed. Run: pip install mt5linux"
        ) from exc

    try:
        _client = MetaTrader5(
            host=_wine_host(),
            port=_wine_port(),
            timeout=_wine_timeout(),
        )
    except Exception as exc:
        _set_error(1, f"Cannot connect to Wine MT5 bridge on {_wine_host()}:{_wine_port()}: {exc}")
        raise

    return _client


def _export_constants() -> None:
    """Copy MT5 constants from mt5linux into this module namespace."""
    try:
        from mt5linux import MetaTrader5 as _MT5Class
        for name in dir(_MT5Class):
            if name.isupper() and not name.startswith("_"):
                globals()[name] = getattr(_MT5Class, name)
    except ImportError:
        from utils import mt5_mock as mock
        for name in dir(mock):
            if name.isupper() and not name.startswith("_"):
                globals()[name] = getattr(mock, name)


_export_constants()


def wine_reachable() -> bool:
    """Return True if the Wine-side mt5linux RPyC server accepts connections."""
    try:
        with socket.create_connection((_wine_host(), _wine_port()), timeout=2):
            return True
    except OSError:
        return False


def initialize(
    path: Optional[str] = None,
    login: Optional[int] = None,
    password: Optional[str] = None,
    server: Optional[str] = None,
    timeout: int = 60000,
    portable: bool = False,
) -> bool:
    global _initialized
    try:
        client = _ensure_client()
    except RuntimeError:
        return False
    except Exception as exc:
        _set_error(1, str(exc))
        return False

    kwargs: dict = {"timeout": timeout, "portable": portable}
    if path:
        kwargs["path"] = path
    elif get_env("MT5_WINE_PATH", ""):
        kwargs["path"] = get_env("MT5_WINE_PATH", "")
    if login is not None:
        kwargs["login"] = int(login)
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    try:
        ok = client.initialize(**kwargs)
        _initialized = bool(ok)
        if not ok:
            err = client.last_error()
            _set_error(int(err[0]), str(err[1]))
        else:
            _set_error(0, "")
        return _initialized
    except Exception as exc:
        _set_error(1, str(exc))
        return False


def shutdown() -> None:
    global _initialized, _client
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass
    _initialized = False


def reset_wine_client() -> None:
    """Drop RPyC session after a failed initialize/login (avoids stale MT5 state)."""
    global _initialized, _client, _last_error
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass
    _client = None
    _initialized = False
    _last_error = (0, "")


def login(login: int, password: str = "", server: str = "", timeout: int = 60000) -> bool:
    try:
        client = _ensure_client()
        ok = client.login(login, password=password, server=server, timeout=timeout)
        if not ok:
            err = client.last_error()
            _set_error(int(err[0]), str(err[1]))
        else:
            _set_error(0, "")
        return bool(ok)
    except Exception as exc:
        _set_error(1, str(exc))
        return False


def last_error() -> tuple:
    if _client is not None:
        try:
            return _client.last_error()
        except Exception:
            pass
    return _last_error


def terminal_info():
    return _ensure_client().terminal_info()


def account_info():
    return _ensure_client().account_info()


def symbol_info(symbol: str):
    return _ensure_client().symbol_info(symbol)


def symbol_info_tick(symbol: str):
    return _ensure_client().symbol_info_tick(symbol)


def symbol_select(symbol: str, enable: bool = True) -> bool:
    return bool(_ensure_client().symbol_select(symbol, enable))


def copy_rates_from(symbol: str, timeframe: int, date_from, count: int):
    return _ensure_client().copy_rates_from(symbol, timeframe, date_from, count)


def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int):
    return _ensure_client().copy_rates_from_pos(symbol, timeframe, start_pos, count)


def copy_rates_range(symbol: str, timeframe: int, date_from, date_to):
    return _ensure_client().copy_rates_range(symbol, timeframe, date_from, date_to)


def order_send(request: dict):
    return _ensure_client().order_send(request)


def order_check(request: dict):
    return _ensure_client().order_check(request)


def positions_get(symbol: str = None, ticket: int = None):
    if ticket is not None:
        return _ensure_client().positions_get(ticket=ticket)
    if symbol:
        return _ensure_client().positions_get(symbol=symbol)
    return _ensure_client().positions_get()


def orders_get(symbol: str = None):
    if symbol:
        return _ensure_client().orders_get(symbol=symbol)
    return _ensure_client().orders_get()


def history_deals_get(date_from, date_to):
    return _ensure_client().history_deals_get(date_from, date_to)


__version__ = "5.0.45.wine"
__name__ = "MetaTrader5 (Wine/mt5linux)"
