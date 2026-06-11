"""Swarm-based scalping toolkit with paper trading support."""

from .backtest import BacktestResult, PaperTradingEngine
from .data import load_candles_from_csv
from .models import Candle, Signal, SwarmDecision, Trade
from .swarm import (
    LiquiditySweepAgent,
    SmartMoneyStructureAgent,
    SwarmCoordinator,
    TrendBiasAgent,
    VolumeProfileAgent,
)

__all__ = [
    "BacktestResult",
    "Candle",
    "LiquiditySweepAgent",
    "PaperTradingEngine",
    "Signal",
    "SmartMoneyStructureAgent",
    "SwarmCoordinator",
    "SwarmDecision",
    "Trade",
    "TrendBiasAgent",
    "VolumeProfileAgent",
    "load_candles_from_csv",
]
