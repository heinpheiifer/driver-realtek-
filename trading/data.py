from __future__ import annotations

import csv
from pathlib import Path

from .models import Candle


def _pick(row: dict[str, str], *names: str) -> str:
    lookup = {k.lower(): v for k, v in row.items()}
    for name in names:
        value = lookup.get(name.lower())
        if value is not None:
            return value
    raise KeyError(f"Missing CSV column. Tried: {names}")


def load_candles_from_csv(path: str | Path) -> list[Candle]:
    """Load OHLCV candles from CSV.

    Required columns (case-insensitive aliases supported):
    - timestamp: timestamp, time, date
    - open: open, o
    - high: high, h
    - low: low, l
    - close: close, c
    - volume: volume, vol, tick_volume
    """

    candles: list[Candle] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            candles.append(
                Candle(
                    timestamp=_pick(row, "timestamp", "time", "date"),
                    open=float(_pick(row, "open", "o")),
                    high=float(_pick(row, "high", "h")),
                    low=float(_pick(row, "low", "l")),
                    close=float(_pick(row, "close", "c")),
                    volume=float(_pick(row, "volume", "vol", "tick_volume")),
                )
            )
    return candles
