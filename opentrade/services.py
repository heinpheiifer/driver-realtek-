from __future__ import annotations

import itertools
import random
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading.backtest import PaperTradingEngine
from trading.data import load_candles_from_csv
from trading.export_mt5 import export_champion_ea
from trading.metrics import objective_score
from trading.strategy import StrategyConfig, build_swarm
from trading.walk_forward import aggregate_rolling_metrics, expanding_walk_forward_windows, split_holdout


class BacktestService:
    def run(
        self,
        *,
        csv_path: str,
        config: dict[str, Any],
        initial_balance: float = 10_000.0,
        walk_forward: bool = False,
        train_ratio: float = 0.70,
    ) -> dict[str, Any]:
        candles = load_candles_from_csv(csv_path)
        if not candles:
            raise ValueError("No candles found in CSV.")

        strategy = StrategyConfig.from_dict(config)
        if walk_forward:
            train, test = split_holdout(candles, train_ratio, min_train=250, min_test=120)
            train_result = self._execute(train, strategy, initial_balance)
            test_result = self._execute(test, strategy, initial_balance)
            return {
                "walk_forward": True,
                "candles_total": len(candles),
                "train": self._serialize_result(train_result),
                "test": self._serialize_result(test_result),
            }

        result = self._execute(candles, strategy, initial_balance)
        return {"walk_forward": False, "result": self._serialize_result(result)}

    def _execute(self, candles, strategy: StrategyConfig, initial_balance: float):
        engine = PaperTradingEngine(
            initial_balance=initial_balance,
            risk_per_trade=strategy.risk_per_trade,
            atr_stop_multiplier=strategy.atr_stop_multiplier,
            reward_risk=strategy.reward_risk,
            spread_bps=strategy.spread_bps,
            slippage_bps=strategy.slippage_bps,
        )
        return engine.run(candles, build_swarm(strategy))

    def _serialize_result(self, result) -> dict[str, Any]:
        return {
            "initial_balance": result.initial_balance,
            "ending_balance": result.ending_balance,
            "total_return_pct": round(result.total_return_pct, 4),
            "max_drawdown_pct": round(result.max_drawdown_pct, 4),
            "win_rate_pct": round(result.win_rate_pct, 4),
            "trades": len(result.trades),
            "trading_days": result.trading_days,
            "trades_per_day": round(result.trades_per_day, 4),
            "equity_curve": [round(v, 2) for v in result.equity_curve[-500:]],
            "trade_rows": [
                {
                    "side": trade.side,
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "entry_price": round(trade.entry_price, 5),
                    "exit_price": round(trade.exit_price, 5),
                    "quantity": round(trade.quantity, 4),
                    "pnl": round(trade.pnl, 4),
                    "reason": trade.reason,
                    "entry_confidence": round(trade.entry_confidence, 4),
                    "entry_score": round(trade.entry_score, 4),
                    "entry_agents": trade.entry_agents,
                }
                for trade in result.trades
            ],
        }


class OptimizerService:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def start(
        self,
        *,
        csv_path: str,
        output_dir: str,
        config_grid: dict[str, list[Any]] | None = None,
        gates: dict[str, float] | None = None,
        max_iterations: int = 0,
    ) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "status": "running",
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "iteration": 0,
            "best": None,
            "gate_met": False,
            "message": "Optimizer started",
        }
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_loop,
            args=(job_id, csv_path, output_dir, config_grid, gates, max_iterations),
            daemon=True,
        )
        thread.start()
        return job

    def status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._jobs.values())

    def _run_loop(
        self,
        job_id: str,
        csv_path: str,
        output_dir: str,
        config_grid: dict[str, list[Any]] | None,
        gates: dict[str, float] | None,
        max_iterations: int,
    ) -> None:
        gates = gates or {
            "min_win_rate": 65.0,
            "target_test_return": 0.5,
            "max_test_drawdown": 10.0,
            "min_test_trades": 20,
        }
        grid = config_grid or {
            "risk_per_trade": [0.005, 0.0075, 0.01],
            "atr_stop_multiplier": [1.2, 1.4, 1.6],
            "reward_risk": [1.6, 1.9, 2.2],
            "min_confidence": [0.30, 0.35, 0.40, 0.45],
            "vp_window": [90, 120, 150],
            "sm_window": [35, 50, 65],
        }

        candles = load_candles_from_csv(csv_path)
        train, test = split_holdout(candles, 0.70, min_train=250, min_test=120)
        rolling_windows = expanding_walk_forward_windows(candles, folds=3, min_train=250, min_test=120)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        combinations = list(
            itertools.product(
                grid["risk_per_trade"],
                grid["atr_stop_multiplier"],
                grid["reward_risk"],
                grid["min_confidence"],
                grid["vp_window"],
                grid["sm_window"],
            )
        )

        iteration = 0
        backtest = BacktestService()
        prior_best_config: dict[str, Any] | None = None
        while True:
            iteration += 1
            rows: list[dict[str, Any]] = []
            configs: list[StrategyConfig] = [
                StrategyConfig(
                    risk_per_trade=risk,
                    atr_stop_multiplier=atr,
                    reward_risk=rr,
                    min_confidence=confidence,
                    vp_window=vp,
                    sm_window=sm,
                )
                for risk, atr, rr, confidence, vp, sm in combinations
            ]
            if prior_best_config:
                base = StrategyConfig.from_dict(prior_best_config)
                rng = random.Random(iteration)
                for _ in range(16):
                    configs.append(
                        StrategyConfig(
                            risk_per_trade=max(0.0025, min(0.02, base.risk_per_trade * rng.uniform(0.85, 1.15))),
                            atr_stop_multiplier=max(0.8, min(2.5, base.atr_stop_multiplier + rng.uniform(-0.2, 0.2))),
                            reward_risk=max(1.2, min(3.0, base.reward_risk + rng.uniform(-0.3, 0.3))),
                            min_confidence=max(0.25, min(0.60, base.min_confidence + rng.uniform(-0.05, 0.05))),
                            vp_window=max(60, min(220, base.vp_window + rng.randint(-20, 20))),
                            sm_window=max(20, min(100, base.sm_window + rng.randint(-10, 10))),
                            liq_window=base.liq_window,
                            trend_fast=base.trend_fast,
                            trend_slow=base.trend_slow,
                            min_agreeing_agents=base.min_agreeing_agents,
                        )
                    )

            for config in configs:
                train_payload = backtest._execute(train, config, 10_000.0)
                test_payload = backtest._execute(test, config, 10_000.0)
                fold_rows = []
                for window in rolling_windows:
                    fold = backtest._execute(window.test, config, 10_000.0)
                    fold_rows.append(
                        {
                            "total_return_pct": fold.total_return_pct,
                            "max_drawdown_pct": fold.max_drawdown_pct,
                            "win_rate_pct": fold.win_rate_pct,
                            "trades": len(fold.trades),
                            "trades_per_day": fold.trades_per_day,
                        }
                    )
                rolling = aggregate_rolling_metrics(fold_rows)
                objective = objective_score(
                    train_payload.total_return_pct,
                    train_payload.max_drawdown_pct,
                    train_payload.win_rate_pct,
                    len(train_payload.trades),
                )
                rows.append(
                    {
                        "objective": round(objective, 6),
                        "total_return_test_pct": round(test_payload.total_return_pct, 4),
                        "max_drawdown_test_pct": round(test_payload.max_drawdown_pct, 4),
                        "win_rate_test_pct": round(test_payload.win_rate_pct, 4),
                        "trades_test": len(test_payload.trades),
                        "trades_per_day_test": round(test_payload.trades_per_day, 4),
                        "rolling_min_return_pct": round(rolling.min_return_pct, 4),
                        "rolling_max_drawdown_pct": round(rolling.max_drawdown_pct, 4),
                        "rolling_min_win_rate_pct": round(rolling.min_win_rate_pct, 4),
                        "rolling_trades_per_day": round(
                            sum(f["trades_per_day"] for f in fold_rows) / len(fold_rows), 4
                        ),
                        "config": config.to_dict(),
                    }
                )

            ranked = sorted(rows, key=lambda row: row["objective"], reverse=True)
            best = ranked[0]
            prior_best_config = best["config"]
            gate_met = self._gate_met(best, gates)

            export_champion_ea(best["config"], output_path=out_dir / "SwarmChampionEA.mq5")

            with self._lock:
                self._jobs[job_id].update(
                    {
                        "iteration": iteration,
                        "best": best,
                        "gate_met": gate_met,
                        "message": "Profitability gate met" if gate_met else "Searching for better config",
                        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )
                if gate_met:
                    self._jobs[job_id]["status"] = "success"
                    break
                if max_iterations > 0 and iteration >= max_iterations:
                    self._jobs[job_id]["status"] = "stopped"
                    break

    @staticmethod
    def _gate_met(best: dict[str, Any], gates: dict[str, float]) -> bool:
        return (
            best["rolling_min_win_rate_pct"] >= gates["min_win_rate"]
            and best["rolling_min_return_pct"] >= gates["target_test_return"]
            and best["rolling_max_drawdown_pct"] <= gates["max_test_drawdown"]
            and best["trades_test"] >= gates["min_test_trades"]
        )
