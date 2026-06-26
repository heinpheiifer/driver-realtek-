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
        print("  - MT5 in Wine + MT5_WINE_ENABLED=true (same laptop), or")
        print("  - MT5 bridge on another Windows PC + MT5_BRIDGE_URL in .env\n")
    if get_backend_mode() == "bridge":
        from utils.mt5_bridge_client import bridge_reachable
        if not bridge_reachable():
            print("\nERROR: MT5 bridge is not reachable. Run scripts/start-bridge.ps1 on Windows.\n")
            return 1
    elif get_backend_mode() == "wine":
        from utils.mt5_wine_client import wine_reachable
        if not wine_reachable():
            print("\nERROR: Wine MT5 bridge not running. Run ./scripts/start-wine-mt5linux.sh\n")
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
        print(f"\nBalance:      {info.balance:,.2f} {info.currency}")
        print(f"Equity:       {info.equity:,.2f}")
        print(f"Used margin:  {info.margin:,.2f}")
        print(f"Free margin:  {info.free_margin:,.2f}")
        print(f"Leverage:     1:{info.leverage}")
        print(f"Profit:       {info.profit:+,.2f}")
        print(f"Server:       {info.server}")
        print(f"Trade allowed:{info.trade_allowed}")

        connector = manager.get_connector(active.id)
        if connector:
            for sym in ("XAUUSD", "XAUUSD.r", "XAUUSDm", "GOLD"):
                sinfo = connector.get_symbol_info(sym)
                if sinfo:
                    print(f"\nSymbol {sinfo.name}: min lot {sinfo.min_lot}, step {sinfo.lot_step}")
                    tick = connector.get_tick(sinfo.name)
                    if tick:
                        try:
                            from utils.mt5_backend import load_mt5_module
                            mt5 = load_mt5_module()
                            if hasattr(mt5, "order_calc_margin"):
                                need = mt5.order_calc_margin(
                                    mt5.ORDER_TYPE_BUY,
                                    sinfo.name,
                                    sinfo.min_lot,
                                    tick.ask,
                                )
                                if need is not None and need >= 0:
                                    print(
                                        f"Margin for {sinfo.min_lot} lot BUY: ~{need:,.2f} "
                                        f"(free margin: {info.free_margin:,.2f})"
                                    )
                                    if need > info.free_margin:
                                        print(
                                            "→ Not enough free margin for minimum gold lot. "
                                            "Deposit more, raise leverage, or test EURUSD first."
                                        )
                        except Exception:
                            pass
                    break
        return 0

    print("\nCould not read balance.")
    if get_backend_mode() == "bridge":
        print("→ Check Windows MT5 is open, bridge is running, and server name matches exactly.")
    elif get_backend_mode() == "wine":
        print("→ Open MT5 in Wine, run ./scripts/start-wine-mt5linux.sh, check server name.")
    elif get_backend_mode() == "mock":
        print("→ Set MT5_WINE_ENABLED=true in .env (Wine) or MT5_BRIDGE_URL (remote Windows).")
    else:
        print("→ Open MT5, log in to the same account, check server name matches exactly.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
