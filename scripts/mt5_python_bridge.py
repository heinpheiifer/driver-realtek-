#!/usr/bin/env python3
"""BlackBull MT5 bridge — pulls ALL symbols into Open Trader.

Run on Windows next to your BlackBull MT5 terminal. Pushes every tradeable
symbol to the Open Trader API (old chart app on :8010 or bridge on :8011).

  set MT5_LOGIN=12345678
  set MT5_PASSWORD=your_password
  set MT5_SERVER=BlackBullMarkets-Live
  set MT5_PATH=C:\\Program Files\\BlackBull Markets MT5\\terminal64.exe
  set OPENTRADER_URL=http://127.0.0.1:8011

  .venv\\Scripts\\pip install -r requirements-mt5.txt
  .venv\\Scripts\\python scripts/mt5_python_bridge.py --all-symbols --interval 60

Linux Open Trader (old chart app): set BlackBull API URL to your Windows PC:
  OPENTRADER_URL=http://192.168.x.x:8011
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading.blackbull_mt5 import (
    connect_mt5,
    fetch_mt5_candles,
    list_mt5_symbols,
    mt5_status,
    save_symbols_manifest,
    shutdown_mt5,
)


def push_symbol(url: str, symbol: str, timeframe: str, bars: int) -> bool:
    result = fetch_mt5_candles(symbol=symbol, timeframe=timeframe, bars=bars)
    if result is None:
        return False
    candles, label, path = result
    payload = {
        "symbol": symbol.upper().replace("/", "").split(".")[0],
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
    try:
        r = requests.post(f"{url.rstrip('/')}/api/market/blackbull/import", json=payload, timeout=60)
        if not r.ok:
            print(f"  FAIL {symbol} {timeframe}: {r.status_code}")
            return False
        print(f"  OK {symbol} {timeframe} · {len(candles)} bars · {label}")
        return True
    except Exception as exc:
        print(f"  FAIL {symbol} {timeframe}: {exc}")
        return False


def push_manifest(url: str, symbols: list, timeframes: list[str]) -> None:
    try:
        requests.post(
            f"{url.rstrip('/')}/api/market/mt5/connect",
            timeout=10,
        )
    except Exception:
        pass
    manifest_path = save_symbols_manifest(symbols, timeframes=timeframes)
    print(f"Symbol manifest: {manifest_path} ({len(symbols)} symbols)")


def sync_all(url: str, timeframes: list[str], bars: int, visible_only: bool) -> int:
    symbols = list_mt5_symbols(visible_only=visible_only)
    if not symbols:
        print("No MT5 symbols. Is BlackBull MT5 running?")
        return 1
    push_manifest(url, symbols, timeframes)
    ok = 0
    total = 0
    for row in symbols:
        name = row["name"]
        clean = name.upper().replace("/", "").split(".")[0]
        for tf in timeframes:
            total += 1
            if push_symbol(url, clean, tf, bars):
                ok += 1
    print(f"Synced {ok}/{total} symbol/timeframe pairs → {url}")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="BlackBull MT5 → Open Trader bridge (all symbols)")
    parser.add_argument("--symbol", default=os.environ.get("MT5_SYMBOL", "BTCUSD"))
    parser.add_argument("--timeframe", default=os.environ.get("MT5_TIMEFRAME", "M5"))
    parser.add_argument("--timeframes", default=os.environ.get("MT5_TIMEFRAMES", "M1,M5,H1"))
    parser.add_argument("--bars", type=int, default=800)
    parser.add_argument("--interval", type=int, default=60, help="Seconds between full syncs (0 = once)")
    parser.add_argument("--url", default=os.environ.get("OPENTRADER_URL", "http://127.0.0.1:8011"))
    parser.add_argument("--all-symbols", action="store_true", help="Sync ALL BlackBull MT5 symbols (default)")
    parser.add_argument("--single", action="store_true", help="Sync only --symbol instead of all")
    parser.add_argument("--visible-only", action="store_true", help="Only Market Watch symbols")
    args = parser.parse_args()

    all_symbols = args.all_symbols or not args.single
    tfs = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]

    if not connect_mt5():
        print("Could not connect to MT5:", json.dumps(mt5_status(), indent=2))
        sys.exit(1)
    print("MT5 connected:", json.dumps(mt5_status(), indent=2))
    print(f"Open Trader URL: {args.url}")

    try:
        while True:
            if all_symbols:
                code = sync_all(args.url, tfs, args.bars, args.visible_only)
            else:
                code = 0 if push_symbol(args.url, args.symbol, args.timeframe, args.bars) else 1
            if args.interval <= 0:
                sys.exit(code)
            print(f"Next sync in {args.interval}s…")
            time.sleep(max(10, args.interval))
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
