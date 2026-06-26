"""
MT5 backend selection helpers.

On Windows the native MetaTrader5 package is used.
On Linux with MT5 in Wine, enable MT5_WINE_ENABLED and run the mt5linux RPyC server.
Alternatively set MT5_BRIDGE_URL for a remote Windows HTTP bridge.
Otherwise the local mock module is used for UI preview.
"""
import os
import platform
from typing import Literal

from utils.config import get_env

BackendMode = Literal["native", "wine", "bridge", "mock"]


def get_bridge_url() -> str:
    """Return configured MT5 bridge base URL, or empty string."""
    return (get_env("MT5_BRIDGE_URL", "") or "").strip().rstrip("/")


def get_bridge_token() -> str:
    """Return optional auth token for the MT5 bridge."""
    return (get_env("MT5_BRIDGE_TOKEN", "") or "").strip()


def is_wine_enabled() -> bool:
    """True when Linux should use mt5linux to reach MT5 in Wine."""
    return get_env("MT5_WINE_ENABLED", False, bool)


def get_backend_mode() -> BackendMode:
    """Return which MT5 backend this process will use."""
    if platform.system() == "Windows":
        return "native"
    if get_bridge_url():
        return "bridge"
    if is_wine_enabled():
        return "wine"
    return "mock"


def is_real_mt5_available() -> bool:
    """True when live MT5 data/trading is available."""
    return get_backend_mode() in ("native", "bridge", "wine")


def backend_label() -> str:
    """Human-readable backend description for UI messages."""
    mode = get_backend_mode()
    if mode == "native":
        return "Windows MT5 (local)"
    if mode == "bridge":
        return f"MT5 bridge ({get_bridge_url()})"
    if mode == "wine":
        host = get_env("MT5_WINE_HOST", "localhost")
        port = get_env("MT5_WINE_PORT", 18812, int)
        return f"MT5 in Wine via mt5linux ({host}:{port})"
    return "Mock MT5 (UI preview only)"


def load_mt5_module():
    """
    Import the MT5 module appropriate for this platform and configuration.

    Returns:
        Module exposing the MetaTrader5-style API.
    """
    mode = get_backend_mode()

    if mode == "native":
        import MetaTrader5 as mt5
        return mt5

    module_map = {
        "bridge": "mt5_bridge_client",
        "wine": "mt5_wine_client",
        "mock": "mt5_mock",
    }
    module_name = module_map[mode]
    module_path = os.path.join(os.path.dirname(__file__), f"{module_name}.py")

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mt5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt5)
    return mt5
