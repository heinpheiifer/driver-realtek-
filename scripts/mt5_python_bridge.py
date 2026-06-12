#!/usr/bin/env python3
"""Push BlackBull MT5 candles into Open Trader.

Run on the same Windows machine as your BlackBull MT5 terminal:

  set MT5_LOGIN=12345678
  set MT5_PASSWORD=your_password
  set MT5_SERVER=BlackBullMarkets-Live
  set MT5_PATH=C:\\Program Files\\BlackBull Markets MT5\\terminal64.exe
  set OPENTRADER_URL=http://127.0.0.1:8010

  python scripts/mt5_python_bridge.py --symbol BTCUSD --timeframe M5 --interval 15

Requires: pip install MetaTrader5 requests
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from trading.blackbull_mt5 import connect_mt5, fetch_mt5_candles, mt5_status, shutdown_mt5


def push_to_opentrader(*, url: str, symbol: str, timeframe: str, bars: int) -> bool:
    result = fetch_mt5_candles(symbol=symbol, timeframe=timeframe, bars=bars)
    if result is None:
        print("MT5 fetch failed:", mt5_status())
        return False

    candles, label, path = result
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ],
    }
    response = requests.post(f"{url.rstrip('/')}/api/market/blackbull/import", json=payload, timeout=30)
    if not response.ok:
        print("Open Trader import failed:", response.status_code, response.text)
        return False
    data = response.json()
    print(f"Synced {data.get('imported', len(candles))} bars · {label} · cached {path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="BlackBull MT5 → Open Trader bridge")
    parser.add_argument("--symbol", default=os.environ.get("MT5_SYMBOL", "BTCUSD"))
    parser.add_argument("--timeframe", default=os.environ.get("MT5_TIMEFRAME", "M5"))
    parser.add_argument("--bars", type=int, default=800)
    parser.add_argument("--interval", type=int, default=15, help="Seconds between syncs (0 = once)")
    parser.add_argument("--url", default=os.environ.get("OPENTRADER_URL", "http://127.0.0.1:8010"))
    args = parser.parse_args()

    if not connect_mt5():
        print("Could not connect to MT5:", json.dumps(mt5_status(), indent=2))
        sys.exit(1)

    print("MT5 connected:", json.dumps(mt5_status(), indent=2))

    try:
        while True:
            ok = push_to_opentrader(url=args.url, symbol=args.symbol, timeframe=args.timeframe, bars=args.bars)
            if args.interval <= 0:
                sys.exit(0 if ok else 1)
            time.sleep(max(5, args.interval))
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
