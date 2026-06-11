from __future__ import annotations

from datetime import datetime
from typing import Sequence

from .models import Candle, Trade


def _parse_timestamp(value: str) -> datetime | None:
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value.replace("Z", ""), fmt.replace("Z", ""))
        except ValueError:
            continue
    return None


def count_trading_days(candles: Sequence[Candle]) -> int:
    days: set[str] = set()
    for candle in candles:
        parsed = _parse_timestamp(candle.timestamp)
        if parsed is not None:
            days.add(parsed.date().isoformat())
    return max(1, len(days))


def trades_per_day(trades: Sequence[Trade], candles: Sequence[Candle]) -> float:
    days = count_trading_days(candles)
    return len(trades) / days


def objective_score(
    total_return_pct: float,
    max_drawdown_pct: float,
    win_rate_pct: float,
    trades: int,
    *,
    trades_per_day_value: float | None = None,
    target_trades_per_day: float = 3.0,
) -> float:
    return total_return_pct - (0.45 * max_drawdown_pct) + (0.08 * win_rate_pct) + (0.002 * trades)
