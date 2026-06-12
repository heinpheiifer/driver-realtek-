from trading.models import Candle
from trading.orderflow import compute_orderflow


def _sample_candles(count: int = 12) -> list[Candle]:
    return [
        Candle(
            timestamp=f"2024-03-15 09:{i:02d}:00",
            open=50.0 + i * 0.1,
            high=50.5 + i * 0.1,
            low=49.5 + i * 0.1,
            close=50.2 + i * 0.1,
            volume=100.0 + i * 5,
        )
        for i in range(count)
    ]


def test_compute_orderflow_on_sample_candles():
    candles = _sample_candles()
    result = compute_orderflow(candles, window=8, price_bins=16)

    assert result["bins"] == 16
    assert result["price_min"] < result["price_max"]
    assert len(result["columns"]) == 8
    assert result["total_buy"] >= 0
    assert result["total_sell"] >= 0
    assert "poc_price" in result
    assert "delta" in result

    column = result["columns"][0]
    assert len(column["buy"]) == 16
    assert len(column["sell"]) == 16


def test_compute_orderflow_empty_candles():
    result = compute_orderflow([])
    assert result["columns"] == []
    assert result["price_min"] == 0.0
    assert result["price_max"] == 0.0
