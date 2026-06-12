from __future__ import annotations

import logging
from pathlib import Path

from .data import load_candles_from_csv
from .fetch_data import _generate_realistic_ohlcv, save_ohlcv_csv
from .models import Candle

logger = logging.getLogger(__name__)

TIMEFRAME_YAHOO = {
    "M1": ("5d", "1m"),
    "M5": ("5d", "5m"),
    "M15": ("1mo", "15m"),
    "H1": ("3mo", "1h"),
    "H4": ("6mo", "1h"),
    "D1": ("1y", "1d"),
}


def _candles_to_dict(candles: list[Candle], limit: int = 500) -> list[dict]:
    rows = candles[-limit:]
    return [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in rows
    ]


def _yahoo_ticker(symbol: str) -> str:
    symbol = symbol.upper().replace("/", "")
    if symbol in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD") and "=X" not in symbol:
        return f"{symbol}=X"
    if symbol == "BTCUSD":
        return "BTC-USD"
    if symbol == "ETHUSD":
        return "ETH-USD"
    if symbol.endswith("USD") and len(symbol) > 6:
        return f"{symbol[:-3]}-USD"
    return symbol


def _flatten_yahoo_columns(data):
    import pandas as pd

    if isinstance(data.columns, pd.MultiIndex):
        data = data.copy()
        data.columns = data.columns.get_level_values(0)
    return data


def _scalar(value) -> float:
    if hasattr(value, "iloc"):
        return float(value.iloc[0])
    return float(value)


def _fetch_yahoo_candles(
    *,
    symbol: str,
    timeframe: str,
    bars: int,
) -> tuple[list[Candle], str, str] | None:
    try:
        import yfinance as yf

        ticker = _yahoo_ticker(symbol)
        tf = timeframe.upper()
        period, interval = TIMEFRAME_YAHOO.get(tf, ("5d", "5m"))
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if data is None or data.empty:
            return None

        data = _flatten_yahoo_columns(data)
        candles: list[Candle] = []
        for ts, row in data.iterrows():
            candles.append(
                Candle(
                    timestamp=str(ts)[:19],
                    open=_scalar(row["Open"]),
                    high=_scalar(row["High"]),
                    low=_scalar(row["Low"]),
                    close=_scalar(row["Close"]),
                    volume=_scalar(row["Volume"]) if "Volume" in row else 0.0,
                )
            )
        if not candles:
            return None

        out = Path("trading_data") / f"{symbol.lower()}_{tf.lower()}_yahoo.csv"
        save_ohlcv_csv(out, _candles_to_dict(candles, len(candles)))
        return candles[-bars:], f"yahoo:{ticker}", str(out)
    except Exception as exc:
        logger.warning("Yahoo fetch failed for %s: %s", symbol, exc)
        return None


def load_market_candles(
    *,
    symbol: str = "BTCUSD",
    source: str = "yahoo",
    csv_path: str | None = None,
    bars: int = 800,
    timeframe: str = "M5",
) -> tuple[list[Candle], str, str]:
    """Load candles from csv, yahoo, blackbull (stub), or synthetic.

    Returns (candles, source_label, csv_path).
    """
    symbol = symbol.upper().replace("/", "")
    source = source.lower()
    tf = timeframe.upper()

    if source == "csv" and csv_path:
        path = Path(csv_path)
        if path.exists():
            candles = load_candles_from_csv(path)
            if candles:
                return candles[-bars:], f"csv:{path.name}", str(path)

    if source in ("yahoo", "blackbull"):
        yahoo = _fetch_yahoo_candles(symbol=symbol, timeframe=tf, bars=bars)
        if yahoo:
            candles, label, path = yahoo
            if source == "blackbull":
                return candles, f"blackbull:yahoo({label.split(':', 1)[-1]})", path
            return candles, label, path

    if source == "blackbull":
        cached = Path("trading_data") / f"{symbol.lower()}_{tf.lower()}_blackbull.csv"
        if cached.exists():
            candles = load_candles_from_csv(cached)
            if candles:
                return candles[-bars:], f"blackbull:{symbol}", str(cached)

    out = Path("trading_data") / f"{symbol.lower()}_{tf.lower()}_synthetic.csv"
    start_price = 62900.0 if "BTC" in symbol else (1.0850 if "EUR" in symbol else 100.0)
    rows = _generate_realistic_ohlcv(bars=bars, start_price=start_price, seed=hash(symbol + tf) % 10000)
    save_ohlcv_csv(out, rows)
    return load_candles_from_csv(out)[-bars:], f"synthetic:{symbol}", str(out)
