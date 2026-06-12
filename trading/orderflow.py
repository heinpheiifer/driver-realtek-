from __future__ import annotations

from typing import Sequence

from .models import Candle


def compute_orderflow(
    candles: Sequence[Candle],
    *,
    end_index: int | None = None,
    window: int = 100,
    price_bins: int = 48,
) -> dict:
    """Build a Bookmap-style order-flow heatmap from OHLCV candles.

    Buy/sell volume is estimated per candle from close position in the range.
    """
    if not candles:
        return {"columns": [], "price_min": 0.0, "price_max": 0.0, "bins": price_bins}

    end = len(candles) if end_index is None else min(len(candles), max(1, end_index))
    start = max(0, end - window)
    sample = list(candles[start:end])
    if not sample:
        return {"columns": [], "price_min": 0.0, "price_max": 0.0, "bins": price_bins}

    price_min = min(c.low for c in sample)
    price_max = max(c.high for c in sample)
    if price_max <= price_min:
        price_max = price_min + 1e-5

    bin_size = (price_max - price_min) / price_bins
    columns: list[dict] = []
    total_buy = 0.0
    total_sell = 0.0
    poc_bin = 0
    poc_volume = 0.0
    bin_totals = [0.0 for _ in range(price_bins)]

    for candle in sample:
        buy_row = [0.0] * price_bins
        sell_row = [0.0] * price_bins
        span = max(candle.high - candle.low, 1e-9)
        buy_vol = candle.volume * max(0.0, (candle.close - candle.low) / span)
        sell_vol = max(0.0, candle.volume - buy_vol)

        touched: list[int] = []
        for idx in range(price_bins):
            mid = price_min + (idx + 0.5) * bin_size
            if candle.low <= mid <= candle.high:
                touched.append(idx)

        if not touched:
            idx = min(price_bins - 1, max(0, int((candle.close - price_min) / bin_size)))
            touched = [idx]

        share = 1.0 / len(touched)
        for idx in touched:
            buy_row[idx] += buy_vol * share
            sell_row[idx] += sell_vol * share
            vol = buy_row[idx] + sell_row[idx]
            bin_totals[idx] += buy_vol * share + sell_vol * share

        total_buy += buy_vol
        total_sell += sell_vol
        columns.append(
            {
                "timestamp": candle.timestamp,
                "open": round(candle.open, 5),
                "high": round(candle.high, 5),
                "low": round(candle.low, 5),
                "close": round(candle.close, 5),
                "buy": [round(v, 4) for v in buy_row],
                "sell": [round(v, 4) for v in sell_row],
            }
        )

    poc_bin = max(range(price_bins), key=lambda i: bin_totals[i])
    poc_price = price_min + (poc_bin + 0.5) * bin_size

    return {
        "price_min": round(price_min, 5),
        "price_max": round(price_max, 5),
        "bins": price_bins,
        "poc_price": round(poc_price, 5),
        "delta": round(total_buy - total_sell, 2),
        "total_buy": round(total_buy, 2),
        "total_sell": round(total_sell, 2),
        "columns": columns,
    }
