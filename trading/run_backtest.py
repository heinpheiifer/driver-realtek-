from __future__ import annotations

import argparse
import csv
import itertools
from pathlib import Path

from .backtest import PaperTradingEngine
from .data import load_candles_from_csv
from .walk_forward import split_holdout
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
    parser.add_argument("--mode", choices=["single", "sweep"], default="single")
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV file.")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol for MT5 signal export metadata.")
    parser.add_argument("--timeframe", default="M1", help="Timeframe label for MT5 signal export.")
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Enable train/test time split. In sweep mode: optimize on train, validate on test.",
    )
    parser.add_argument("--wf-train-ratio", type=float, default=0.70)
    parser.add_argument("--wf-min-train", type=int, default=250)
    parser.add_argument("--wf-min-test", type=int, default=120)
    parser.add_argument("--initial-balance", type=float, default=10_000.0)
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--atr-stop-multiplier", type=float, default=1.4)
    parser.add_argument("--reward-risk", type=float, default=1.8)
    parser.add_argument("--spread-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=0.5)
    parser.add_argument("--vp-window", type=int, default=120)
    parser.add_argument("--sm-window", type=int, default=50)
    parser.add_argument("--liq-window", type=int, default=35)
    parser.add_argument("--trend-fast", type=int, default=12)
    parser.add_argument("--trend-slow", type=int, default=48)
    parser.add_argument("--min-confidence", type=float, default=0.35)
    parser.add_argument("--save-trades", default="", help="Optional path to save trades CSV.")
    parser.add_argument(
        "--save-mt5-signals",
        default="",
        help="Optional path to save MT5 signal-export CSV (open/close actions).",
    )
    parser.add_argument("--save-sweep", default="", help="Optional path to save sweep results CSV.")
    parser.add_argument("--sweep-top-n", type=int, default=10)
    parser.add_argument("--sweep-risk-per-trade", default="0.0075,0.01")
    parser.add_argument("--sweep-atr-stop", default="1.2,1.4")
    parser.add_argument("--sweep-reward-risk", default="1.6,1.9")
    parser.add_argument("--sweep-min-confidence", default="0.32,0.38")
    parser.add_argument("--sweep-vp-window", default="100,140")
    parser.add_argument("--sweep-sm-window", default="40,55")
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
                "entry_confidence",
                "entry_score",
                "entry_agents",
            ],
        )
        writer.writeheader()
        for trade in trades:
            writer.writerow(trade.__dict__)


def _save_mt5_signals(path: str | Path, symbol: str, timeframe: str, trades) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
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


def _parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def _parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _split_walk_forward(candles, train_ratio: float, min_train: int, min_test: int):
    try:
        return split_holdout(candles, train_ratio, min_train, min_test)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _build_swarm(
    *,
    vp_window: int,
    sm_window: int,
    liq_window: int,
    trend_fast: int,
    trend_slow: int,
    min_confidence: float,
) -> SwarmCoordinator:
    agents = [
        VolumeProfileAgent(window=vp_window, bins=24, value_area=0.70),
        SmartMoneyStructureAgent(window=sm_window, body_multiplier=1.5),
        LiquiditySweepAgent(window=liq_window, tolerance_bps=5.0, min_cluster=2),
        TrendBiasAgent(fast_period=trend_fast, slow_period=trend_slow),
    ]
    return SwarmCoordinator(
        agents=agents,
        weights={
            "volume_profile": 1.2,
            "smart_money": 1.4,
            "liquidity_sweep": 1.1,
            "trend_bias": 0.8,
        },
        min_confidence=min_confidence,
    )


def _run_config(
    candles,
    *,
    args,
    risk_per_trade: float,
    atr_stop_multiplier: float,
    reward_risk: float,
    min_confidence: float,
    vp_window: int,
    sm_window: int,
):
    swarm = _build_swarm(
        vp_window=vp_window,
        sm_window=sm_window,
        liq_window=args.liq_window,
        trend_fast=args.trend_fast,
        trend_slow=args.trend_slow,
        min_confidence=min_confidence,
    )
    engine = PaperTradingEngine(
        initial_balance=args.initial_balance,
        risk_per_trade=risk_per_trade,
        atr_stop_multiplier=atr_stop_multiplier,
        reward_risk=reward_risk,
        spread_bps=args.spread_bps,
        slippage_bps=args.slippage_bps,
    )
    result = engine.run(candles, swarm)
    objective = _objective(
        result.total_return_pct,
        result.max_drawdown_pct,
        result.win_rate_pct,
    )
    return result, objective


def _run_single(args, candles):
    if args.walk_forward:
        train, test = _split_walk_forward(
            candles,
            train_ratio=args.wf_train_ratio,
            min_train=args.wf_min_train,
            min_test=args.wf_min_test,
        )
        train_result, train_objective = _run_config(
            train,
            args=args,
            risk_per_trade=args.risk_per_trade,
            atr_stop_multiplier=args.atr_stop_multiplier,
            reward_risk=args.reward_risk,
            min_confidence=args.min_confidence,
            vp_window=args.vp_window,
            sm_window=args.sm_window,
        )
        test_result, test_objective = _run_config(
            test,
            args=args,
            risk_per_trade=args.risk_per_trade,
            atr_stop_multiplier=args.atr_stop_multiplier,
            reward_risk=args.reward_risk,
            min_confidence=args.min_confidence,
            vp_window=args.vp_window,
            sm_window=args.sm_window,
        )

        print("=== Swarm Scalping Walk-Forward Backtest ===")
        print(f"Candles: total={len(candles)} train={len(train)} test={len(test)}")
        print(
            f"Train -> ret={train_result.total_return_pct:.2f}% dd={train_result.max_drawdown_pct:.2f}% "
            f"wr={train_result.win_rate_pct:.2f}% trades={len(train_result.trades)} obj={train_objective:.3f}"
        )
        print(
            f"Test  -> ret={test_result.total_return_pct:.2f}% dd={test_result.max_drawdown_pct:.2f}% "
            f"wr={test_result.win_rate_pct:.2f}% trades={len(test_result.trades)} obj={test_objective:.3f}"
        )

        if args.save_trades:
            test_path = Path(args.save_trades)
            train_path = test_path.with_name(f"{test_path.stem}.train{test_path.suffix or '.csv'}")
            _save_trades(train_path, train_result.trades)
            _save_trades(test_path, test_result.trades)
            print(f"Train trades saved to: {train_path}")
            print(f"Test trades saved to:  {test_path}")
        if args.save_mt5_signals:
            _save_mt5_signals(
                args.save_mt5_signals,
                args.symbol,
                args.timeframe,
                test_result.trades,
            )
            print(f"MT5 forward signals saved to: {args.save_mt5_signals}")
        return

    result, _ = _run_config(
        candles,
        args=args,
        risk_per_trade=args.risk_per_trade,
        atr_stop_multiplier=args.atr_stop_multiplier,
        reward_risk=args.reward_risk,
        min_confidence=args.min_confidence,
        vp_window=args.vp_window,
        sm_window=args.sm_window,
    )

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
    if args.save_mt5_signals:
        _save_mt5_signals(args.save_mt5_signals, args.symbol, args.timeframe, result.trades)
        print(f"MT5 signals saved to: {args.save_mt5_signals}")


def _objective(total_return_pct: float, max_drawdown_pct: float, win_rate_pct: float) -> float:
    # Penalize high drawdown while still rewarding return and execution quality.
    return total_return_pct - (max_drawdown_pct * 0.45) + (win_rate_pct * 0.03)


def _save_sweep(path: str | Path, rows: list[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_sweep(args, candles):
    risk_grid = _parse_float_list(args.sweep_risk_per_trade)
    atr_grid = _parse_float_list(args.sweep_atr_stop)
    rr_grid = _parse_float_list(args.sweep_reward_risk)
    conf_grid = _parse_float_list(args.sweep_min_confidence)
    vp_grid = _parse_int_list(args.sweep_vp_window)
    sm_grid = _parse_int_list(args.sweep_sm_window)

    rows: list[dict] = []
    total = (
        len(risk_grid)
        * len(atr_grid)
        * len(rr_grid)
        * len(conf_grid)
        * len(vp_grid)
        * len(sm_grid)
    )
    print(f"=== Parameter Sweep Mode ===")
    print(f"Combinations: {total}")

    if args.walk_forward:
        train_candles, test_candles = _split_walk_forward(
            candles,
            train_ratio=args.wf_train_ratio,
            min_train=args.wf_min_train,
            min_test=args.wf_min_test,
        )
        print(
            f"Walk-forward split active: train={len(train_candles)} candles, test={len(test_candles)} candles."
        )
    else:
        train_candles = candles
        test_candles = None

    for risk, atr, rr, conf, vp_window, sm_window in itertools.product(
        risk_grid, atr_grid, rr_grid, conf_grid, vp_grid, sm_grid
    ):
        train_result, train_score = _run_config(
            train_candles,
            args=args,
            risk_per_trade=risk,
            atr_stop_multiplier=atr,
            reward_risk=rr,
            min_confidence=conf,
            vp_window=vp_window,
            sm_window=sm_window,
        )
        row = {
            "objective_train": round(train_score, 6),
            "total_return_train_pct": round(train_result.total_return_pct, 6),
            "max_drawdown_train_pct": round(train_result.max_drawdown_pct, 6),
            "win_rate_train_pct": round(train_result.win_rate_pct, 6),
            "trades_train": len(train_result.trades),
            "risk_per_trade": risk,
            "atr_stop_multiplier": atr,
            "reward_risk": rr,
            "min_confidence": conf,
            "vp_window": vp_window,
            "sm_window": sm_window,
            "liq_window": args.liq_window,
            "trend_fast": args.trend_fast,
            "trend_slow": args.trend_slow,
        }

        if test_candles is not None:
            test_result, test_score = _run_config(
                test_candles,
                args=args,
                risk_per_trade=risk,
                atr_stop_multiplier=atr,
                reward_risk=rr,
                min_confidence=conf,
                vp_window=vp_window,
                sm_window=sm_window,
            )
            row.update(
                {
                    "objective_test": round(test_score, 6),
                    "total_return_test_pct": round(test_result.total_return_pct, 6),
                    "max_drawdown_test_pct": round(test_result.max_drawdown_pct, 6),
                    "win_rate_test_pct": round(test_result.win_rate_pct, 6),
                    "trades_test": len(test_result.trades),
                }
            )
        rows.append(row)

    ranked = sorted(rows, key=lambda row: row["objective_train"], reverse=True)
    top_n = min(args.sweep_top_n, len(ranked))
    print(f"Top {top_n} candidates:")
    for idx, row in enumerate(ranked[:top_n], start=1):
        msg = (
            f"{idx:>2}. train_obj={row['objective_train']:.3f} "
            f"train_ret={row['total_return_train_pct']:.2f}% train_dd={row['max_drawdown_train_pct']:.2f}% "
            f"train_wr={row['win_rate_train_pct']:.2f}% train_trades={row['trades_train']} "
        )
        if "objective_test" in row:
            msg += (
                f"| test_obj={row['objective_test']:.3f} test_ret={row['total_return_test_pct']:.2f}% "
                f"test_dd={row['max_drawdown_test_pct']:.2f}% test_wr={row['win_rate_test_pct']:.2f}% "
                f"test_trades={row['trades_test']} "
            )
        msg += (
            f"[risk={row['risk_per_trade']}, atr={row['atr_stop_multiplier']}, rr={row['reward_risk']}, "
            f"conf={row['min_confidence']}, vp={row['vp_window']}, sm={row['sm_window']}]"
        )
        print(msg)

    if ranked and "objective_test" in ranked[0]:
        champion = ranked[0]
        print(
            "Champion forward validation -> "
            f"test_obj={champion['objective_test']:.3f}, "
            f"test_ret={champion['total_return_test_pct']:.2f}%, "
            f"test_dd={champion['max_drawdown_test_pct']:.2f}%, "
            f"test_wr={champion['win_rate_test_pct']:.2f}%."
        )

    if args.save_sweep:
        _save_sweep(args.save_sweep, ranked)
        print(f"Sweep results saved to: {args.save_sweep}")


def main() -> None:
    args = _build_parser().parse_args()
    candles = load_candles_from_csv(args.csv)
    if not candles:
        raise SystemExit("No candles found in CSV.")

    if args.mode == "single":
        _run_single(args, candles)
    else:
        _run_sweep(args, candles)


if __name__ == "__main__":
    main()
