#!/usr/bin/env python3
"""Place a small test market order on the active MT5 account."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.account_manager import AccountType, get_account_manager
from core.mt5_connector import Signal
from utils.mt5_backend import backend_label, get_backend_mode


def resolve_symbol(connector, preferred: str) -> str:
    """Pick the first symbol name that exists on the broker."""
    base = preferred.upper()
    candidates = [
        base,
        f"{base}.r",
        f"{base}m",
        f"{base}.a",
        "GOLD",
        "XAUUSD",
    ]
    seen: set[str] = set()
    for sym in candidates:
        if sym in seen:
            continue
        seen.add(sym)
        if connector.get_symbol_info(sym):
            return sym
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one small test market order")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--lots", type=float, default=0.01, help="Lot size (default: 0.01)")
    parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    parser.add_argument(
        "--close-after",
        action="store_true",
        help="Close the position right after it opens (good for connectivity tests)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show order details only")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required for LIVE accounts — confirms you accept real money risk",
    )
    args = parser.parse_args()

    print(f"Backend: {backend_label()} ({get_backend_mode()})\n")

    if get_backend_mode() == "wine":
        from utils.mt5_wine_client import wine_reachable

        if not wine_reachable():
            print("Wine bridge not running. Run: ./scripts/ensure-wine-bridge.sh")
            return 1

    manager = get_account_manager()
    active = manager.get_active_account()
    if not active:
        print("No active account. Open UI → Accounts → Set Active on 517035.")
        return 1

    if not manager.connect(active.id, force=True):
        print("Connect failed:", manager.get_connection_error(active.id))
        return 1

    connector = manager.get_connector(active.id)
    if not connector or not connector.is_connected():
        print("Not connected to MT5.")
        return 1

    symbol = resolve_symbol(connector, args.symbol)
    tick = connector.get_tick(symbol)
    if not tick:
        print(f"Cannot get price for {symbol}. Check symbol name in MT5 Market Watch.")
        return 1

    side = Signal.BUY if args.side == "buy" else Signal.SELL
    price = tick["ask"] if side == Signal.BUY else tick["bid"]

    info = connector.get_account_info()
    print(f"Account:  {active.login} @ {active.server} [{active.account_type.value.upper()}]")
    if info:
        print(f"Balance:      {info.balance:,.2f} {info.currency}")
        print(f"Free margin:  {info.free_margin:,.2f}")
        print(f"Leverage:     1:{info.leverage}")
    print(f"Symbol:   {symbol}")
    print(f"Order:    {args.side.upper()} {args.lots} lot(s) @ ~{price}")

    if args.dry_run:
        print("\nDRY RUN — no order sent.")
        return 0

    if active.account_type == AccountType.LIVE and not args.yes:
        print(
            "\nLIVE account — this sends a REAL order. "
            "Re-run with --yes (and optionally --close-after)."
        )
        return 1

    result = connector.place_market_order(
        symbol=symbol,
        order_type=side,
        volume=args.lots,
        comment="XAU60 test trade",
    )

    if not result.success:
        print(f"\nOrder FAILED: {result.error_message}")
        if result.retcode == 10019:
            print(
                "Code 10019 = not enough FREE MARGIN (not minimum lot size). "
                "Gold needs more margin than forex — check free margin vs leverage."
            )
            if info:
                print(f"  Balance {info.balance:,.2f} {info.currency}, free margin {info.free_margin:,.2f}")
        else:
            print("Check: Algo Trading ON in MT5, symbol in Market Watch, min lot size.")
        return 1

    print(f"\nOrder OK — ticket {result.ticket} @ {result.price}")

    if args.close_after:
        time.sleep(1.5)
        if connector.close_position(result.ticket):
            print("Test position closed.")
        else:
            print("Could not auto-close — close ticket manually in MT5 or Dashboard.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
