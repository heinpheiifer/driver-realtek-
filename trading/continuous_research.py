from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .backtest import BacktestResult, PaperTradingEngine
from .data import load_candles_from_csv
from .swarm import (
    LiquiditySweepAgent,
    SmartMoneyStructureAgent,
    SwarmCoordinator,
    TrendBiasAgent,
    VolumeProfileAgent,
)


@dataclass
class RunnerConfig:
    risk_per_trade: float
    atr_stop_multiplier: float
    reward_risk: float
    min_confidence: float
    vp_window: int
    sm_window: int
    liq_window: int
    trend_fast: int
    trend_slow: int


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously optimize and evaluate the swarm strategy until "
            "profitability gates are satisfied."
        )
    )
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV data.")
    parser.add_argument("--output-dir", default="trading_runs/continuous")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M1")
    parser.add_argument("--interval-seconds", type=int, default=90)
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="0 means run forever.",
    )
    parser.add_argument("--stop-on-success", action="store_true", default=True)
    parser.add_argument("--no-stop-on-success", action="store_false", dest="stop_on_success")

    parser.add_argument("--walk-forward", action="store_true", default=True)
    parser.add_argument("--no-walk-forward", action="store_false", dest="walk_forward")
    parser.add_argument("--wf-train-ratio", type=float, default=0.70)
    parser.add_argument("--wf-min-train", type=int, default=250)
    parser.add_argument("--wf-min-test", type=int, default=120)

    parser.add_argument("--target-test-return", type=float, default=1.0)
    parser.add_argument("--max-test-drawdown", type=float, default=8.0)
    parser.add_argument("--min-test-win-rate", type=float, default=45.0)
    parser.add_argument("--min-test-trades", type=int, default=20)

    parser.add_argument("--risk-grid", default="0.005,0.0075,0.01")
    parser.add_argument("--atr-grid", default="1.2,1.4,1.6")
    parser.add_argument("--rr-grid", default="1.6,1.9,2.2")
    parser.add_argument("--confidence-grid", default="0.30,0.35,0.40")
    parser.add_argument("--vp-window-grid", default="90,120,150")
    parser.add_argument("--sm-window-grid", default="35,50,65")
    parser.add_argument("--liq-window", type=int, default=35)
    parser.add_argument("--trend-fast", type=int, default=12)
    parser.add_argument("--trend-slow", type=int, default=48)
    parser.add_argument("--top-n", type=int, default=5)
    return parser


def _parse_float_grid(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def _parse_int_grid(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_walk_forward(candles, train_ratio: float, min_train: int, min_test: int):
    if not 0.50 <= train_ratio < 0.95:
        raise SystemExit("--wf-train-ratio must be between 0.50 and 0.95.")
    split_idx = int(len(candles) * train_ratio)
    train = candles[:split_idx]
    test = candles[split_idx:]
    if len(train) < min_train or len(test) < min_test:
        raise SystemExit(
            "Not enough candles for walk-forward split. "
            f"Need at least train={min_train}, test={min_test}, got train={len(train)}, test={len(test)}."
        )
    return train, test


def _build_swarm(config: RunnerConfig) -> SwarmCoordinator:
    agents = [
        VolumeProfileAgent(window=config.vp_window, bins=24, value_area=0.70),
        SmartMoneyStructureAgent(window=config.sm_window, body_multiplier=1.5),
        LiquiditySweepAgent(window=config.liq_window, tolerance_bps=5.0, min_cluster=2),
        TrendBiasAgent(fast_period=config.trend_fast, slow_period=config.trend_slow),
    ]
    return SwarmCoordinator(
        agents=agents,
        weights={
            "volume_profile": 1.2,
            "smart_money": 1.4,
            "liquidity_sweep": 1.1,
            "trend_bias": 0.8,
        },
        min_confidence=config.min_confidence,
    )


def _run_backtest(candles, config: RunnerConfig, initial_balance: float) -> BacktestResult:
    swarm = _build_swarm(config)
    engine = PaperTradingEngine(
        initial_balance=initial_balance,
        risk_per_trade=config.risk_per_trade,
        atr_stop_multiplier=config.atr_stop_multiplier,
        reward_risk=config.reward_risk,
        spread_bps=1.0,
        slippage_bps=0.5,
    )
    return engine.run(candles, swarm)


def _objective(total_return_pct: float, max_drawdown_pct: float, win_rate_pct: float, trades: int) -> float:
    # Reward returns and execution quality while penalizing drawdown.
    return total_return_pct - (0.45 * max_drawdown_pct) + (0.03 * win_rate_pct) + (0.002 * trades)


def _save_mt5_signals(path: Path, symbol: str, timeframe: str, trades) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "symbol",
                "timeframe",
                "action",
                "side",
                "price",
                "quantity",
                "confidence",
                "score",
                "reason",
                "agents",
            ],
        )
        writer.writeheader()
        for trade in trades:
            writer.writerow(
                {
                    "timestamp": trade.entry_time,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "action": "OPEN",
                    "side": trade.side.upper(),
                    "price": f"{trade.entry_price:.8f}",
                    "quantity": f"{trade.quantity:.6f}",
                    "confidence": f"{trade.entry_confidence:.4f}",
                    "score": f"{trade.entry_score:.4f}",
                    "reason": "swarm_entry",
                    "agents": trade.entry_agents,
                }
            )
            writer.writerow(
                {
                    "timestamp": trade.exit_time,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "action": "CLOSE",
                    "side": trade.side.upper(),
                    "price": f"{trade.exit_price:.8f}",
                    "quantity": f"{trade.quantity:.6f}",
                    "confidence": f"{trade.entry_confidence:.4f}",
                    "score": f"{trade.entry_score:.4f}",
                    "reason": trade.reason,
                    "agents": trade.entry_agents,
                }
            )


def _meets_profitability_gate(args, row: dict) -> bool:
    return (
        row["total_return_test_pct"] >= args.target_test_return
        and row["max_drawdown_test_pct"] <= args.max_test_drawdown
        and row["win_rate_test_pct"] >= args.min_test_win_rate
        and row["trades_test"] >= args.min_test_trades
    )


def main() -> None:
    args = _build_parser().parse_args()
    candles = load_candles_from_csv(args.csv)
    if not candles:
        raise SystemExit("No candles found in CSV.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.walk_forward:
        train_candles, test_candles = _split_walk_forward(
            candles, args.wf_train_ratio, args.wf_min_train, args.wf_min_test
        )
    else:
        train_candles = candles
        test_candles = candles

    risk_grid = _parse_float_grid(args.risk_grid)
    atr_grid = _parse_float_grid(args.atr_grid)
    rr_grid = _parse_float_grid(args.rr_grid)
    confidence_grid = _parse_float_grid(args.confidence_grid)
    vp_grid = _parse_int_grid(args.vp_window_grid)
    sm_grid = _parse_int_grid(args.sm_window_grid)

    combinations = list(
        itertools.product(risk_grid, atr_grid, rr_grid, confidence_grid, vp_grid, sm_grid)
    )
    print(f"[{_timestamp()}] Continuous runner started. combinations={len(combinations)}")
    print(
        f"[{_timestamp()}] Dataset split: train={len(train_candles)} test={len(test_candles)} "
        f"(walk_forward={'on' if args.walk_forward else 'off'})"
    )

    iteration = 0
    while True:
        iteration += 1
        iteration_started = _timestamp()
        rows: list[dict] = []

        for risk, atr, rr, confidence, vp_window, sm_window in combinations:
            config = RunnerConfig(
                risk_per_trade=risk,
                atr_stop_multiplier=atr,
                reward_risk=rr,
                min_confidence=confidence,
                vp_window=vp_window,
                sm_window=sm_window,
                liq_window=args.liq_window,
                trend_fast=args.trend_fast,
                trend_slow=args.trend_slow,
            )
            train_result = _run_backtest(train_candles, config, initial_balance=10_000.0)
            test_result = _run_backtest(test_candles, config, initial_balance=10_000.0)
            objective_train = _objective(
                train_result.total_return_pct,
                train_result.max_drawdown_pct,
                train_result.win_rate_pct,
                len(train_result.trades),
            )
            objective_test = _objective(
                test_result.total_return_pct,
                test_result.max_drawdown_pct,
                test_result.win_rate_pct,
                len(test_result.trades),
            )
            rows.append(
                {
                    "objective_train": round(objective_train, 6),
                    "objective_test": round(objective_test, 6),
                    "total_return_train_pct": round(train_result.total_return_pct, 6),
                    "max_drawdown_train_pct": round(train_result.max_drawdown_pct, 6),
                    "win_rate_train_pct": round(train_result.win_rate_pct, 6),
                    "trades_train": len(train_result.trades),
                    "total_return_test_pct": round(test_result.total_return_pct, 6),
                    "max_drawdown_test_pct": round(test_result.max_drawdown_pct, 6),
                    "win_rate_test_pct": round(test_result.win_rate_pct, 6),
                    "trades_test": len(test_result.trades),
                    "risk_per_trade": risk,
                    "atr_stop_multiplier": atr,
                    "reward_risk": rr,
                    "min_confidence": confidence,
                    "vp_window": vp_window,
                    "sm_window": sm_window,
                    "liq_window": args.liq_window,
                    "trend_fast": args.trend_fast,
                    "trend_slow": args.trend_slow,
                }
            )

        ranked = sorted(rows, key=lambda row: row["objective_train"], reverse=True)
        best = ranked[0]
        top_n = ranked[: max(1, args.top_n)]

        iter_prefix = output_dir / f"iteration_{iteration:05d}"
        iter_csv = iter_prefix.with_suffix(".csv")
        with iter_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ranked[0].keys()))
            writer.writeheader()
            writer.writerows(ranked)

        best_json = iter_prefix.with_suffix(".best.json")
        with best_json.open("w", encoding="utf-8") as handle:
            json.dump({"iteration": iteration, "timestamp": iteration_started, "best": best}, handle, indent=2)

        print(
            f"[{_timestamp()}] iteration={iteration} "
            f"best_train_obj={best['objective_train']:.3f} "
            f"test_ret={best['total_return_test_pct']:.2f}% "
            f"test_dd={best['max_drawdown_test_pct']:.2f}% "
            f"test_wr={best['win_rate_test_pct']:.2f}% "
            f"test_trades={best['trades_test']}"
        )

        champion_config = RunnerConfig(
            risk_per_trade=best["risk_per_trade"],
            atr_stop_multiplier=best["atr_stop_multiplier"],
            reward_risk=best["reward_risk"],
            min_confidence=best["min_confidence"],
            vp_window=int(best["vp_window"]),
            sm_window=int(best["sm_window"]),
            liq_window=int(best["liq_window"]),
            trend_fast=int(best["trend_fast"]),
            trend_slow=int(best["trend_slow"]),
        )
        champion_forward = _run_backtest(test_candles, champion_config, initial_balance=10_000.0)
        _save_mt5_signals(output_dir / "champion_mt5_signals.csv", args.symbol, args.timeframe, champion_forward.trades)

        history_path = output_dir / "history.csv"
        write_header = not history_path.exists()
        with history_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["timestamp", "iteration"] + list(best.keys()),
            )
            if write_header:
                writer.writeheader()
            writer.writerow({"timestamp": _timestamp(), "iteration": iteration, **best})

        with (output_dir / "champion_config.json").open("w", encoding="utf-8") as handle:
            json.dump(asdict(champion_config), handle, indent=2)

        with (output_dir / "top_candidates.json").open("w", encoding="utf-8") as handle:
            json.dump(top_n, handle, indent=2)

        if _meets_profitability_gate(args, best):
            report = {
                "timestamp": _timestamp(),
                "iteration": iteration,
                "profitability_gate_met": True,
                "gate": {
                    "target_test_return": args.target_test_return,
                    "max_test_drawdown": args.max_test_drawdown,
                    "min_test_win_rate": args.min_test_win_rate,
                    "min_test_trades": args.min_test_trades,
                },
                "best": best,
            }
            with (output_dir / "champion_report.json").open("w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
            print(f"[{_timestamp()}] Profitability gate met on iteration {iteration}.")
            if args.stop_on_success:
                print(f"[{_timestamp()}] stop_on_success enabled, stopping.")
                break

        if args.max_iterations > 0 and iteration >= args.max_iterations:
            print(f"[{_timestamp()}] Reached max iterations ({args.max_iterations}), stopping.")
            break

        print(f"[{_timestamp()}] Sleeping {args.interval_seconds}s before next iteration.")
        time.sleep(max(1, args.interval_seconds))


if __name__ == "__main__":
    main()
