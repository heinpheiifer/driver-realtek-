#!/usr/bin/env python3
"""Print MT5 symbol specs (filling mode, min lot) for debugging order errors."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.account_manager import get_account_manager
from utils.mt5_backend import load_mt5_module
from utils.symbols import resolve_broker_symbol, symbol_candidates


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "ETHUSD"
    manager = get_account_manager()
    active = manager.get_active_account()
    if not active:
        print("No active account")
        return 1
    if not manager.connect(active.id, force=True):
        print(manager.get_connection_error(active.id))
        return 1

    connector = manager.get_connector(active.id)
    mt5 = load_mt5_module()
    resolved = resolve_broker_symbol(connector, symbol) or symbol

    print(f"Looking for: {symbol} -> {resolved}")
    print(f"Candidates tried: {symbol_candidates(symbol)}\n")

    mt5.symbol_select(resolved, True)
    info = mt5.symbol_info(resolved)
    if not info:
        print("Symbol not found. Add to Market Watch in MT5.")
        return 1

    print(f"name:          {info.name}")
    print(f"volume_min:    {info.volume_min}")
    print(f"volume_step:   {info.volume_step}")
    print(f"volume_max:    {info.volume_max}")
    print(f"filling_mode:  {getattr(info, 'filling_mode', '?')}")
    print(f"trade_mode:    {getattr(info, 'trade_mode', '?')}")
    print(f"trade_exemode: {getattr(info, 'trade_exemode', '?')}")

    tick = mt5.symbol_info_tick(resolved)
    if tick:
        print(f"bid/ask:       {tick.bid} / {tick.ask}")

    for name, val in (
        ("ORDER_FILLING_FOK", getattr(mt5, "ORDER_FILLING_FOK", 0)),
        ("ORDER_FILLING_IOC", getattr(mt5, "ORDER_FILLING_IOC", 1)),
        ("ORDER_FILLING_RETURN", getattr(mt5, "ORDER_FILLING_RETURN", 2)),
    ):
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": resolved,
            "volume": info.volume_min,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask if tick else 0,
            "deviation": 20,
            "type_filling": val,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        if hasattr(mt5, "order_check"):
            check = mt5.order_check(req)
            rc = int(getattr(check, "retcode", -1)) if check else -1
            comment = getattr(check, "comment", "") if check else "no check"
            print(f"order_check {name} ({val}): retcode={rc}  {comment}")
        else:
            print(f"order_check not available on backend")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
