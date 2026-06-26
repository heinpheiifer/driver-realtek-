"""
MT5 backend selection helpers.

On Windows the native MetaTrader5 package is used.
On Linux/macOS, set MT5_BRIDGE_URL to a Windows machine running the MT5 bridge
for real account data and trading; otherwise the local mock module is used.
"""
import os
import platform
from typing import Literal

from utils.config import get_env

BackendMode = Literal["native", "bridge", "mock"]


def get_bridge_url() -> str:
    """Return configured MT5 bridge base URL, or empty string."""
    return (get_env("MT5_BRIDGE_URL", "") or "").strip().rstrip("/")


def get_bridge_token() -> str:
    """Return optional auth token for the MT5 bridge."""
    return (get_env("MT5_BRIDGE_TOKEN", "") or "").strip()


def get_backend_mode() -> BackendMode:
    """Return which MT5 backend this process will use."""
    if platform.system() == "Windows":
        return "native"
    if get_bridge_url():
        return "bridge"
    return "mock"


def is_real_mt5_available() -> bool:
    """True when live MT5 data/trading is available (native or bridge)."""
    return get_backend_mode() in ("native", "bridge")


def backend_label() -> str:
    """Human-readable backend description for UI messages."""
    mode = get_backend_mode()
    if mode == "native":
        return "Windows MT5 (local)"
    if mode == "bridge":
        return f"MT5 bridge ({get_bridge_url()})"
    return "Mock MT5 (UI preview only)"


def load_mt5_module():
    """
    Import the MT5 module appropriate for this platform and configuration.

    Returns:
        Module exposing the MetaTrader5-style API (native, bridge client, or mock).
    """
    mode = get_backend_mode()

    if mode == "native":
        import MetaTrader5 as mt5
        return mt5

    import importlib.util

    if mode == "bridge":
        module_name = "mt5_bridge_client"
        module_path = os.path.join(os.path.dirname(__file__), "mt5_bridge_client.py")
    else:
        module_name = "mt5_mock"
        module_path = os.path.join(os.path.dirname(__file__), "mt5_mock.py")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mt5 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt5)
    return mt5
