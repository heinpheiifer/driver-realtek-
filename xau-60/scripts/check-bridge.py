#!/usr/bin/env python3
"""Test connectivity to the MT5 bridge (run from xau-60 folder)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.mt5_backend import get_backend_mode, get_bridge_url, backend_label
from utils.mt5_bridge_client import bridge_reachable


def main() -> int:
    print(f"Backend mode: {get_backend_mode()}")
    print(f"Label: {backend_label()}")

    url = get_bridge_url()
    if not url:
        print("\nMT5_BRIDGE_URL is not set in .env")
        print("Add: MT5_BRIDGE_URL=http://YOUR_WINDOWS_IP:8021")
        return 1

    print(f"\nPinging bridge at {url} ...")
    if bridge_reachable():
        print("Bridge is reachable.")
        return 0

    print("Bridge is NOT reachable.")
    print("On Windows: open MT5, run .\\scripts\\start-bridge.ps1, allow firewall port 8021.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
