#!/usr/bin/env python3
"""Check MT5 account connection and print balance (run from xau-60 folder)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.account_manager import get_account_manager, ConnectionStatus
from utils.mt5_backend import get_backend_mode, is_real_mt5_available, backend_label


def main():
    print(f"Backend: {backend_label()} ({get_backend_mode()})")
    if not is_real_mt5_available():
        print("\nNOTE: Real BlackBull balance requires either:")
        print("  - Windows + MT5 terminal (native mode), or")
        print("  - MT5 bridge on Windows + MT5_BRIDGE_URL in .env (Linux/macOS)\n")
    elif get_backend_mode() == "bridge":
        from utils.mt5_bridge_client import bridge_reachable
        if not bridge_reachable():
            print("\nERROR: MT5 bridge is not reachable. Run scripts/start-bridge.ps1 on Windows.\n")
            return 1

    manager = get_account_manager()
    active = manager.get_active_account()

    if not active:
        print("No ACTIVE account. Open the UI → Accounts → Set Active on your live account.")
        accounts = manager.list_accounts()
        if accounts:
            print("\nSaved accounts:")
            for a in accounts:
                print(f"  - {a.name} login={a.login} server={a.server} type={a.account_type.value}")
        return 1

    print(f"Active: {active.name} ({active.login}@{active.server}) [{active.account_type.value}]")

    ok = manager.connect(active.id)
    status = manager.get_connection_status(active.id)
    print(f"Connect: {'OK' if ok else 'FAILED'}  Status: {status.value}")

    info = manager.get_account_info(active.id, refresh=True)
    if info:
        print(f"\nBalance:  {info.balance:,.2f} {info.currency}")
        print(f"Equity:   {info.equity:,.2f}")
        print(f"Profit:   {info.profit:+,.2f}")
        print(f"Server:   {info.server}")
        return 0

    print("\nCould not read balance.")
    if get_backend_mode() == "bridge":
        print("→ Check Windows MT5 is open, bridge is running, and server name matches exactly.")
    elif get_backend_mode() == "mock":
        print("→ Set MT5_BRIDGE_URL in .env or run on Windows with MT5 open.")
    else:
        print("→ Open MT5, log in to the same account, check server name matches exactly.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
