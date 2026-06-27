#!/usr/bin/env python3
"""Check Wine MT5 / mt5linux RPyC connection (run from xau-60 folder)."""
import os

# Keep initialize probe fast if MT5 terminal is not open in Wine
os.environ["MT5_WINE_TIMEOUT"] = "15"

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.config import get_env
from utils.mt5_backend import get_backend_mode, backend_label, is_wine_enabled


def main() -> int:
    print(f"Backend mode: {get_backend_mode()}")
    print(f"Label: {backend_label()}")

    if not is_wine_enabled():
        print("\nMT5_WINE_ENABLED is not true in .env")
        print("Add: MT5_WINE_ENABLED=true")
        return 1

    host = get_env("MT5_WINE_HOST", "localhost")
    port = get_env("MT5_WINE_PORT", 18812, int)
    print(f"\nChecking RPyC server at {host}:{port} ...")

    try:
        from utils.mt5_wine_client import wine_reachable
    except ImportError as exc:
        print(f"Import error: {exc}")
        print("Run: pip install mt5linux")
        return 1

    if not wine_reachable():
        print("Wine MT5 bridge is NOT running.")
        print("\nSteps:")
        print("  1. Open MT5 in Wine (BlackBull logged in)")
        print("  2. In Wine Python: pip install MetaTrader5 mt5linux")
        print("  3. Run: ./scripts/start-wine-mt5linux.sh")
        return 1

    print("RPyC server is reachable.")

    try:
        from utils.mt5_wine_client import initialize, account_info, shutdown, last_error
        if not initialize():
            code, msg = last_error()
            print(f"MT5 initialize() failed: [{code}] {msg}")
            print("Ensure MetaTrader 5 is open in Wine and logged into BlackBull.")
            print("(RPyC bridge is OK — only the MT5 terminal connection failed.)")
            return 2
        info = account_info()
        shutdown()
        if info:
            print(f"\nAccount: {info.login} @ {info.server}")
            print(f"Balance: {info.balance:,.2f} {info.currency}")
            return 0
        print("Connected but account_info() returned nothing.")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
