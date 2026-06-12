from trading.market_data import import_blackbull_candles, load_market_candles
from trading.models import Candle


def _sample_rows(count: int = 5) -> list[dict]:
    return [
        {
            "timestamp": f"2024-06-01 10:0{i}:00",
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 50.0 + i,
        }
        for i in range(count)
    ]


def test_load_market_candles_synthetic_fallback(monkeypatch):
    monkeypatch.setattr("trading.market_data._fetch_yahoo_candles", lambda **kwargs: None)

    candles, label, path, meta = load_market_candles(
        symbol="BTCUSD",
        source="yahoo",
        timeframe="M5",
        bars=25,
    )

    assert len(candles) == 25
    assert label.startswith("synthetic:")
    assert path.endswith("_synthetic.csv")
    assert meta is None
    assert all(isinstance(c, Candle) for c in candles)


def test_import_blackbull_candles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows = _sample_rows(3)

    candles, label, path = import_blackbull_candles(
        symbol="EURUSD",
        timeframe="M5",
        rows=rows,
    )

    assert len(candles) == 3
    assert label == "blackbull:import"
    assert candles[0].close == 100.5
    assert "eurusd_m5_blackbull.csv" in path
