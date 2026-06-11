from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from .models import Candle, Trade
from .swarm import SwarmCoordinator


@dataclass
class BacktestResult:
    initial_balance: float
    ending_balance: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: list[Trade]
    win_rate_pct: float
    equity_curve: list[float]


@dataclass
class _Position:
    side: str
    entry_time: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float


def _average_true_range(history: Sequence[Candle], period: int = 14) -> float:
    if len(history) < period + 1:
        return 0.0
    trs: list[float] = []
    for idx in range(-period, 0):
        candle = history[idx]
        prev_close = history[idx - 1].close
        tr = max(
            candle.high - candle.low,
            abs(candle.high - prev_close),
            abs(candle.low - prev_close),
        )
        trs.append(tr)
    return mean(trs) if trs else 0.0


def _max_drawdown_pct(equity_curve: Sequence[float]) -> float:
    peak = 0.0
    max_dd = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak <= 0:
            continue
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)
    return max_dd * 100.0


class PaperTradingEngine:
    def __init__(
        self,
        initial_balance: float = 10_000.0,
        risk_per_trade: float = 0.01,
        atr_stop_multiplier: float = 1.4,
        reward_risk: float = 1.8,
        spread_bps: float = 1.0,
        slippage_bps: float = 0.5,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.atr_stop_multiplier = atr_stop_multiplier
        self.reward_risk = reward_risk
        self.spread_bps = spread_bps
        self.slippage_bps = slippage_bps

    def run(self, candles: Sequence[Candle], strategy: SwarmCoordinator) -> BacktestResult:
        balance = self.initial_balance
        equity_curve: list[float] = []
        trades: list[Trade] = []
        history: list[Candle] = []
        position: _Position | None = None

        for candle in candles:
            history.append(candle)

            if position is not None:
                exit_price = None
                exit_reason = ""

                if position.side == "long":
                    stop_hit = candle.low <= position.stop_loss
                    target_hit = candle.high >= position.take_profit
                    if stop_hit:
                        exit_price = position.stop_loss
                        exit_reason = "stop_loss"
                    elif target_hit:
                        exit_price = position.take_profit
                        exit_reason = "take_profit"
                else:
                    stop_hit = candle.high >= position.stop_loss
                    target_hit = candle.low <= position.take_profit
                    if stop_hit:
                        exit_price = position.stop_loss
                        exit_reason = "stop_loss"
                    elif target_hit:
                        exit_price = position.take_profit
                        exit_reason = "take_profit"

                if exit_price is not None:
                    pnl = (
                        (exit_price - position.entry_price) * position.quantity
                        if position.side == "long"
                        else (position.entry_price - exit_price) * position.quantity
                    )
                    balance += pnl
                    trades.append(
                        Trade(
                            side=position.side,  # type: ignore[arg-type]
                            entry_time=position.entry_time,
                            exit_time=candle.timestamp,
                            entry_price=position.entry_price,
                            exit_price=exit_price,
                            quantity=position.quantity,
                            pnl=pnl,
                            reason=exit_reason,
                        )
                    )
                    position = None

            if position is None:
                decision = strategy.decide(history)
                if decision is not None:
                    atr = _average_true_range(history, period=14)
                    if atr > 0:
                        execution_drag = (self.spread_bps + self.slippage_bps) / 10_000.0
                        stop_distance = atr * self.atr_stop_multiplier
                        if stop_distance > 0:
                            risk_amount = balance * self.risk_per_trade
                            quantity = risk_amount / stop_distance
                            entry = candle.close
                            if decision.side == "long":
                                entry = entry * (1 + execution_drag)
                                stop = entry - stop_distance
                                target = entry + stop_distance * self.reward_risk
                            else:
                                entry = entry * (1 - execution_drag)
                                stop = entry + stop_distance
                                target = entry - stop_distance * self.reward_risk

                            position = _Position(
                                side=decision.side,
                                entry_time=candle.timestamp,
                                entry_price=entry,
                                quantity=quantity,
                                stop_loss=stop,
                                take_profit=target,
                            )

            mark_price = candle.close
            if position is None:
                equity = balance
            elif position.side == "long":
                equity = balance + (mark_price - position.entry_price) * position.quantity
            else:
                equity = balance + (position.entry_price - mark_price) * position.quantity

            equity_curve.append(equity)

        if position is not None and candles:
            last = candles[-1]
            exit_price = last.close
            pnl = (
                (exit_price - position.entry_price) * position.quantity
                if position.side == "long"
                else (position.entry_price - exit_price) * position.quantity
            )
            balance += pnl
            trades.append(
                Trade(
                    side=position.side,  # type: ignore[arg-type]
                    entry_time=position.entry_time,
                    exit_time=last.timestamp,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    quantity=position.quantity,
                    pnl=pnl,
                    reason="end_of_data",
                )
            )
            if equity_curve:
                equity_curve[-1] = balance
            else:
                equity_curve.append(balance)

        wins = sum(1 for trade in trades if trade.pnl > 0)
        win_rate = (wins / len(trades) * 100.0) if trades else 0.0
        total_return = ((balance - self.initial_balance) / self.initial_balance) * 100.0

        return BacktestResult(
            initial_balance=self.initial_balance,
            ending_balance=balance,
            total_return_pct=total_return,
            max_drawdown_pct=_max_drawdown_pct(equity_curve),
            trades=trades,
            win_rate_pct=win_rate,
            equity_curve=equity_curve,
        )
