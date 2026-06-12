from __future__ import annotations

from abc import ABC, abstractmethod
from statistics import mean
from typing import Sequence

from .models import Candle, Signal, SwarmDecision


def _ema(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    ema_value = values[0]
    for value in values[1:]:
        ema_value = alpha * value + (1.0 - alpha) * ema_value
    return ema_value


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def generate(self, history: Sequence[Candle]) -> Signal | None:
        raise NotImplementedError


class VolumeProfileAgent(BaseAgent):
    name = "volume_profile"

    def __init__(self, window: int = 120, bins: int = 24, value_area: float = 0.70):
        self.window = window
        self.bins = bins
        self.value_area = value_area

    def _profile(self, candles: Sequence[Candle]) -> tuple[float, float, float]:
        low = min(c.low for c in candles)
        high = max(c.high for c in candles)
        if high <= low:
            return low, low, low

        bin_size = (high - low) / self.bins
        volumes = [0.0 for _ in range(self.bins)]

        for candle in candles:
            typical_price = (candle.high + candle.low + candle.close) / 3.0
            idx = int((typical_price - low) / bin_size)
            idx = min(self.bins - 1, max(0, idx))
            volumes[idx] += candle.volume

        total_volume = sum(volumes)
        if total_volume <= 0:
            return low, low, high

        poc_idx = max(range(self.bins), key=lambda i: volumes[i])
        ranked = sorted(range(self.bins), key=lambda i: volumes[i], reverse=True)

        cumulative = 0.0
        selected: set[int] = set()
        for idx in ranked:
            selected.add(idx)
            cumulative += volumes[idx]
            if cumulative / total_volume >= self.value_area:
                break

        val_idx = min(selected)
        vah_idx = max(selected)

        poc = low + (poc_idx + 0.5) * bin_size
        val = low + val_idx * bin_size
        vah = low + (vah_idx + 1.0) * bin_size
        return poc, val, vah

    def generate(self, history: Sequence[Candle]) -> Signal | None:
        if len(history) < self.window:
            return None

        window = history[-self.window :]
        last = history[-1]
        poc, val, vah = self._profile(window)
        epsilon = max(1e-6, last.close * 0.0001)

        if last.close < val:
            distance = (val - last.close) / max(epsilon, last.close * 0.002)
            score = min(1.0, max(0.15, distance))
            return Signal(
                agent=self.name,
                side="long",
                score=score,
                reason=f"Price below value area low ({last.close:.5f} < {val:.5f}); mean reversion toward POC {poc:.5f}.",
            )

        if last.close > vah:
            distance = (last.close - vah) / max(epsilon, last.close * 0.002)
            score = min(1.0, max(0.15, distance))
            return Signal(
                agent=self.name,
                side="short",
                score=score,
                reason=f"Price above value area high ({last.close:.5f} > {vah:.5f}); mean reversion toward POC {poc:.5f}.",
            )

        return None


class SmartMoneyStructureAgent(BaseAgent):
    name = "smart_money"

    def __init__(self, window: int = 50, body_multiplier: float = 1.5):
        self.window = window
        self.body_multiplier = body_multiplier

    def generate(self, history: Sequence[Candle]) -> Signal | None:
        if len(history) < self.window + 2:
            return None

        segment = history[-(self.window + 1) :]
        last = segment[-1]
        prior = segment[:-1]

        max_high = max(c.high for c in prior)
        min_low = min(c.low for c in prior)
        avg_body = mean(abs(c.close - c.open) for c in prior)
        body = abs(last.close - last.open)
        displacement = body >= avg_body * self.body_multiplier if avg_body > 0 else False

        if displacement and last.close > max_high and last.close > last.open:
            score = min(1.0, max(0.2, body / max(1e-6, avg_body * 2.0)))
            return Signal(
                agent=self.name,
                side="long",
                score=score,
                reason="Bullish BOS with displacement candle.",
            )

        if displacement and last.close < min_low and last.close < last.open:
            score = min(1.0, max(0.2, body / max(1e-6, avg_body * 2.0)))
            return Signal(
                agent=self.name,
                side="short",
                score=score,
                reason="Bearish BOS with displacement candle.",
            )

        return None


class LiquiditySweepAgent(BaseAgent):
    name = "liquidity_sweep"

    def __init__(self, window: int = 35, tolerance_bps: float = 5.0, min_cluster: int = 2):
        self.window = window
        self.tolerance = tolerance_bps / 10_000.0
        self.min_cluster = min_cluster

    def generate(self, history: Sequence[Candle]) -> Signal | None:
        if len(history) < self.window + 2:
            return None

        sample = history[-(self.window + 1) :]
        last = sample[-1]
        prior = sample[:-1]

        local_high = max(c.high for c in prior)
        local_low = min(c.low for c in prior)

        high_cluster = sum(
            1 for c in prior if abs(c.high - local_high) / max(1e-9, local_high) <= self.tolerance
        )
        low_cluster = sum(
            1 for c in prior if abs(c.low - local_low) / max(1e-9, local_low) <= self.tolerance
        )

        if (
            high_cluster >= self.min_cluster
            and last.high > local_high * (1.0 + self.tolerance)
            and last.close < local_high
        ):
            return Signal(
                agent=self.name,
                side="short",
                score=0.65,
                reason="Buy-side liquidity sweep and rejection.",
            )

        if (
            low_cluster >= self.min_cluster
            and last.low < local_low * (1.0 - self.tolerance)
            and last.close > local_low
        ):
            return Signal(
                agent=self.name,
                side="long",
                score=0.65,
                reason="Sell-side liquidity sweep and rejection.",
            )

        return None


class TrendBiasAgent(BaseAgent):
    name = "trend_bias"

    def __init__(self, fast_period: int = 12, slow_period: int = 48):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate(self, history: Sequence[Candle]) -> Signal | None:
        if len(history) < self.slow_period + 2:
            return None

        closes = [c.close for c in history[-(self.slow_period + 5) :]]
        fast = _ema(closes, self.fast_period)
        slow = _ema(closes, self.slow_period)
        last = closes[-1]

        if fast > slow and last >= fast:
            return Signal(
                agent=self.name,
                side="long",
                score=0.35,
                reason="Bullish micro-trend bias (EMA fast > EMA slow).",
            )
        if fast < slow and last <= fast:
            return Signal(
                agent=self.name,
                side="short",
                score=0.35,
                reason="Bearish micro-trend bias (EMA fast < EMA slow).",
            )
        return None


class SwarmCoordinator:
    def __init__(
        self,
        agents: list[BaseAgent],
        weights: dict[str, float] | None = None,
        min_confidence: float = 0.35,
        min_agreeing_agents: int = 2,
        require_quality_setup: bool = True,
    ):
        self.agents = agents
        self.weights = weights or {}
        self.min_confidence = min_confidence
        self.min_agreeing_agents = min_agreeing_agents
        self.require_quality_setup = require_quality_setup

    def decide(self, history: Sequence[Candle]) -> SwarmDecision | None:
        signals: list[Signal] = []
        weighted_score = 0.0
        active_weight = 0.0

        for agent in self.agents:
            signal = agent.generate(history)
            if signal is None:
                continue
            signals.append(signal)
            weight = self.weights.get(signal.agent, 1.0)
            signed = signal.score if signal.side == "long" else -signal.score
            weighted_score += signed * weight
            active_weight += abs(weight)

        if not signals or active_weight == 0:
            return None

        side = "long" if weighted_score > 0 else "short"
        agreeing = sum(1 for s in signals if s.side == side)
        if agreeing < self.min_agreeing_agents:
            return None

        if self.require_quality_setup:
            quality = {"smart_money", "liquidity_sweep"}
            if not any(s.agent in quality for s in signals):
                return None

        trend_signals = [s for s in signals if s.agent == "trend_bias"]
        if trend_signals and trend_signals[0].side != side:
            return None

        normalized = weighted_score / active_weight
        confidence = abs(normalized)
        if confidence < self.min_confidence:
            return None

        return SwarmDecision(
            side=side,  # type: ignore[arg-type]
            confidence=confidence,
            score=normalized,
            signals=signals,
        )
