import opentrade.live_engine as live_engine_module
from opentrade.live_engine import _average_true_range
from trading.models import Candle


def _sample_candles(count: int = 20) -> list[Candle]:
    return [
        Candle(
            timestamp=f"2024-01-02 {i:02d}:00:00",
            open=100.0 + i * 0.2,
            high=101.0 + i * 0.2,
            low=99.0 + i * 0.2,
            close=100.5 + i * 0.2,
            volume=10.0 + i,
        )
        for i in range(count)
    ]


def test_import_live_engine_module():
    assert hasattr(live_engine_module, "_average_true_range")
    assert hasattr(live_engine_module, "LivePaperEngine")


def test_average_true_range_does_not_crash():
    candles = _sample_candles(20)
    atr = _average_true_range(candles, period=14)
    assert isinstance(atr, float)
    assert atr > 0


def test_average_true_range_short_history_returns_zero():
    candles = _sample_candles(5)
    assert _average_true_range(candles, period=14) == 0.0
