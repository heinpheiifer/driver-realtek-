#!/usr/bin/env python3
"""Forward Bookmap order-flow events to Open Trader.

Run alongside Bookmap (or pipe events from your Bookmap Python addon):

  OPENTRADER_URL=http://127.0.0.1:8010 python scripts/opentrader_bookmap_addon.py

Pipe JSON lines (one event per line):
  {"type":"large_print","price":1.105,"size":5000,"delta":120,"side":"buy"}

Or replay demo signals from loaded BlackBull CSV:
  python scripts/opentrader_bookmap_addon.py --replay trading_data/blackbull_import/xrpusd_h1.csv
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

from trading.data import load_candles_from_csv
from trading.orderflow import compute_orderflow


def post_event(url: str, event: dict) -> bool:
    try:
        r = requests.post(f"{url.rstrip('/')}/api/bookmap/event", json=event, timeout=5)
        return r.ok
    except Exception as exc:
        print("POST failed:", exc)
        return False


def replay_csv(url: str, csv_path: str, tick_ms: int = 200) -> None:
    candles = load_candles_from_csv(csv_path)
    if not candles:
        print("No candles in", csv_path)
        sys.exit(1)
    print(f"Replaying {len(candles)} bars → {url}")
    for idx, candle in enumerate(candles[-500:]):
        flow = compute_orderflow(candles, end_index=idx + 1, window=80)
        delta = flow.get("delta", 0.0)
        side = "buy" if candle.close >= candle.open else "sell"
        events = [
            {
                "type": "large_print" if abs(candle.close - candle.open) > 0 else "imbalance",
                "timestamp": candle.timestamp,
                "price": candle.close,
                "size": candle.volume,
                "delta": delta,
                "side": side,
            }
        ]
        for ev in events:
            post_event(url, ev)
        time.sleep(tick_ms / 1000.0)


def stdin_loop(url: str) -> None:
    print(f"Listening for JSON events → {url}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            ok = post_event(url, event)
            print("ok" if ok else "fail", event.get("type"), event.get("price"))
        except json.JSONDecodeError as exc:
            print("Bad JSON:", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bookmap → Open Trader event bridge")
    parser.add_argument("--url", default=os.environ.get("OPENTRADER_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--replay", help="Replay OHLCV CSV as bookmap events")
    parser.add_argument("--tick-ms", type=int, default=200)
    args = parser.parse_args()

    if args.replay:
        replay_csv(args.url, args.replay, args.tick_ms)
    else:
        stdin_loop(args.url)


if __name__ == "__main__":
    main()
