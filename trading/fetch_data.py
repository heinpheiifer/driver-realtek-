from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


def _generate_realistic_ohlcv(
    *,
    bars: int,
    start_price: float = 1.0850,
    seed: int = 42,
    bar_minutes: int = 1,
    start_time: datetime | None = None,
) -> list[dict[str, str | float]]:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    if start_time is None:
        start_time = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)

    rows: list[dict[str, str | float]] = []
    price = start_price
    regime = "range"
    regime_bars_left = int(rng.integers(800, 2500))
    drift = 0.0
    vol = 0.00008

    for bar_idx in range(bars):
        if regime_bars_left <= 0:
            regime = rng.choice(["range", "trend_up", "trend_down"], p=[0.55, 0.225, 0.225])
            regime_bars_left = int(rng.integers(600, 3000))
            if regime == "range":
                drift = 0.0
                vol = float(rng.uniform(0.00005, 0.00010))
            elif regime == "trend_up":
                drift = float(rng.uniform(0.000003, 0.000012))
                vol = float(rng.uniform(0.00006, 0.00014))
            else:
                drift = float(rng.uniform(-0.000012, -0.000003))
                vol = float(rng.uniform(0.00006, 0.00014))

        regime_bars_left -= 1
        shock = float(rng.normal(drift, vol))
        if regime == "range":
            shock -= ((price / start_price) - 1.0) * 0.05

        open_price = price
        close_price = max(0.5, open_price * (1.0 + shock))
        wick = abs(float(rng.normal(0.0, vol * 0.8)))
        high_price = max(open_price, close_price) + wick
        low_price = min(open_price, close_price) - wick
        volume = float(max(20.0, rng.lognormal(mean=5.0, sigma=0.35)))

        ts = start_time + timedelta(minutes=bar_idx * bar_minutes)
        rows.append(
            {
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_price, 5),
                "high": round(high_price, 5),
                "low": round(low_price, 5),
                "close": round(close_price, 5),
                "volume": round(volume, 2),
            }
        )
        price = close_price

    return rows


def save_ohlcv_csv(path: str | Path, rows: list[dict[str, str | float]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or fetch OHLCV CSV for backtesting.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--bars", type=int, default=5000, help="Number of candles to generate.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-price", type=float, default=1.0850)
    parser.add_argument("--bar-minutes", type=int, default=1)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows = _generate_realistic_ohlcv(
        bars=args.bars,
        start_price=args.start_price,
        seed=args.seed,
        bar_minutes=args.bar_minutes,
    )
    save_ohlcv_csv(args.output, rows)
    print(f"Generated {len(rows)} candles -> {args.output}")


if __name__ == "__main__":
    main()
