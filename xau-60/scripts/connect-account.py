#!/usr/bin/env python3
"""Diagnose MT5 connection for the active account (run from xau-60 folder)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.mt5_backend import get_backend_mode, backend_label, is_wine_enabled
from utils.mt5_paths import find_wine_mt5_terminal, resolve_mt5_terminal_path
from core.account_manager import get_account_manager


def main() -> int:
    print(f"Backend: {backend_label()} ({get_backend_mode()})\n")

    if get_backend_mode() == "wine":
        from utils.mt5_wine_client import wine_reachable
        print(f"Wine bridge reachable: {wine_reachable()}")
        term = find_wine_mt5_terminal()
        print(f"Wine MT5 terminal: {term or 'NOT FOUND'}")
        resolved = resolve_mt5_terminal_path()
        print(f"Resolved path:     {resolved or 'NOT FOUND'}")
        print()

    manager = get_account_manager()
    active = manager.get_active_account()
    if not active:
        print("No active account. Set BlackBull Heinz ACTIVE in Accounts.")
        return 1

    print(f"Connecting: {active.name}")
    print(f"  Login:  {active.login}")
    print(f"  Server: {active.server}")
    print()

    ok = manager.connect(active.id)
    err = manager.get_connection_error(active.id)
    status = manager.get_connection_status(active.id)

    print(f"Result:  {'OK' if ok else 'FAILED'}")
    print(f"Status:  {status.value}")
    if err:
        print(f"Error:   {err}")

    info = manager.get_account_info(active.id, refresh=True)
    if info:
        print(f"\nBalance: {info.balance:,.2f} {info.currency}")
        print(f"Equity:  {info.equity:,.2f}")
        return 0

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
