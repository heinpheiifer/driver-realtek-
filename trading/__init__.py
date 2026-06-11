"""Swarm-based scalping toolkit with paper trading support."""

from .backtest import BacktestResult, PaperTradingEngine
from .continuous_research import main as continuous_research_main
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
    "continuous_research_main",
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
