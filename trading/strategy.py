from __future__ import annotations

from dataclasses import asdict, dataclass

from .swarm import (
    LiquiditySweepAgent,
    SmartMoneyStructureAgent,
    SwarmCoordinator,
    TrendBiasAgent,
    VolumeProfileAgent,
)


@dataclass
class StrategyConfig:
    risk_per_trade: float = 0.01
    atr_stop_multiplier: float = 1.4
    reward_risk: float = 1.8
    min_confidence: float = 0.35
    vp_window: int = 120
    sm_window: int = 50
    liq_window: int = 35
    trend_fast: int = 12
    trend_slow: int = 48
    spread_bps: float = 1.0
    slippage_bps: float = 0.5
    weight_volume_profile: float = 1.2
    weight_smart_money: float = 1.4
    weight_liquidity_sweep: float = 1.1
    weight_trend_bias: float = 0.8
    min_agreeing_agents: int = 2
    require_quality_setup: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> StrategyConfig:
        known = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{key: value for key, value in payload.items() if key in known})


def build_swarm(config: StrategyConfig) -> SwarmCoordinator:
    agents = [
        VolumeProfileAgent(window=config.vp_window, bins=24, value_area=0.70),
        SmartMoneyStructureAgent(window=config.sm_window, body_multiplier=1.5),
        LiquiditySweepAgent(window=config.liq_window, tolerance_bps=5.0, min_cluster=2),
        TrendBiasAgent(fast_period=config.trend_fast, slow_period=config.trend_slow),
    ]
    return SwarmCoordinator(
        agents=agents,
        weights={
            "volume_profile": config.weight_volume_profile,
            "smart_money": config.weight_smart_money,
            "liquidity_sweep": config.weight_liquidity_sweep,
            "trend_bias": config.weight_trend_bias,
        },
        min_confidence=config.min_confidence,
        min_agreeing_agents=config.min_agreeing_agents,
        require_quality_setup=config.require_quality_setup,
    )
