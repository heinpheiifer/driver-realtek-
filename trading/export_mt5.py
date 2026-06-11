from __future__ import annotations

import json
from pathlib import Path


def export_champion_ea(
    config: dict,
    *,
    output_path: str | Path,
    symbol: str = "EURUSD",
    timeframe: str = "M1",
) -> Path:
    """Write a minimal MT5 Expert Advisor template from champion config JSON."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    risk = config.get("risk_per_trade", 0.01)
    atr_mult = config.get("atr_stop_multiplier", 1.4)
    rr = config.get("reward_risk", 1.8)
    min_conf = config.get("min_confidence", 0.35)
    vp_window = config.get("vp_window", 120)
    sm_window = config.get("sm_window", 50)
    liq_window = config.get("liq_window", 35)
    trend_fast = config.get("trend_fast", 12)
    trend_slow = config.get("trend_slow", 48)

    source = f"""//+------------------------------------------------------------------+
//| SwarmChampionEA.mq5 - generated from Python research champion    |
//+------------------------------------------------------------------+
#property strict

input double RiskPerTrade      = {risk};
input double AtrStopMultiplier = {atr_mult};
input double RewardRisk        = {rr};
input double MinConfidence     = {min_conf};
input int    VpWindow          = {vp_window};
input int    SmWindow          = {sm_window};
input int    LiqWindow         = {liq_window};
input int    TrendFast         = {trend_fast};
input int    TrendSlow         = {trend_slow};
input string ResearchSymbol    = "{symbol}";
input string ResearchTimeframe = "{timeframe}";

// NOTE: This EA is a scaffold. Wire signal logic to your MT5 bridge or
// re-implement swarm agents in MQL5 before live trading.

int OnInit()
{{
   Print("SwarmChampionEA loaded for ", ResearchSymbol, " ", ResearchTimeframe);
   return(INIT_SUCCEEDED);
}}

void OnTick()
{{
   // Placeholder: consume signals from CSV bridge or port swarm logic here.
}}
"""
    output.write_text(source, encoding="utf-8")
    return output


def export_from_champion_json(
    champion_json_path: str | Path,
    *,
    output_path: str | Path,
    symbol: str = "EURUSD",
    timeframe: str = "M1",
) -> Path:
    with Path(champion_json_path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    config = payload.get("best", payload)
    return export_champion_ea(
        config,
        output_path=output_path,
        symbol=symbol,
        timeframe=timeframe,
    )
