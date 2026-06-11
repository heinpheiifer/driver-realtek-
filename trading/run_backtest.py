from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .backtest import PaperTradingEngine
from .data import load_candles_from_csv
from .swarm import (
    LiquiditySweepAgent,
    SmartMoneyStructureAgent,
    SwarmCoordinator,
    TrendBiasAgent,
    VolumeProfileAgent,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run swarm-based volume-profile + smart-money paper backtest."
    )
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV file.")
    parser.add_argument("--initial-balance", type=float, default=10_000.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--atr-stop-multiplier", type=float, default=1.4)
    parser.add_argument("--reward-risk", type=float, default=1.8)
    parser.add_argument("--spread-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=0.5)
    parser.add_argument("--save-trades", default="", help="Optional path to save trades CSV.")
    return parser


def _save_trades(path: str | Path, trades) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "side",
                "entry_time",
                "exit_time",
                "entry_price",
                "exit_price",
                "quantity",
                "pnl",
                "reason",
            ],
        )
        writer.writeheader()
        for trade in trades:
            writer.writerow(trade.__dict__)


def main() -> None:
    args = _build_parser().parse_args()
    candles = load_candles_from_csv(args.csv)
    if not candles:
        raise SystemExit("No candles found in CSV.")

    agents = [
        VolumeProfileAgent(window=120, bins=24, value_area=0.70),
        SmartMoneyStructureAgent(window=50, body_multiplier=1.5),
        LiquiditySweepAgent(window=35, tolerance_bps=5.0, min_cluster=2),
        TrendBiasAgent(fast_period=12, slow_period=48),
    ]
    swarm = SwarmCoordinator(
        agents=agents,
        weights={
            "volume_profile": 1.2,
            "smart_money": 1.4,
            "liquidity_sweep": 1.1,
            "trend_bias": 0.8,
        },
        min_confidence=0.35,
    )
    engine = PaperTradingEngine(
        initial_balance=args.initial_balance,
        risk_per_trade=args.risk_per_trade,
        atr_stop_multiplier=args.atr_stop_multiplier,
        reward_risk=args.reward_risk,
        spread_bps=args.spread_bps,
        slippage_bps=args.slippage_bps,
    )
    result = engine.run(candles, swarm)

    print("=== Swarm Scalping Paper Backtest ===")
    print(f"Candles:         {len(candles)}")
    print(f"Trades:          {len(result.trades)}")
    print(f"Initial Balance: {result.initial_balance:,.2f}")
    print(f"Ending Balance:  {result.ending_balance:,.2f}")
    print(f"Total Return:    {result.total_return_pct:.2f}%")
    print(f"Win Rate:        {result.win_rate_pct:.2f}%")
    print(f"Max Drawdown:    {result.max_drawdown_pct:.2f}%")

    if args.save_trades:
        _save_trades(args.save_trades, result.trades)
        print(f"Trades saved to: {args.save_trades}")


if __name__ == "__main__":
    main()
