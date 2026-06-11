from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Side = Literal["long", "short"]


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    agent: str
    side: Side
    score: float
    reason: str


@dataclass
class SwarmDecision:
    side: Side
    confidence: float
    score: float
    signals: list[Signal] = field(default_factory=list)


@dataclass
class Trade:
    side: Side
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    reason: str
