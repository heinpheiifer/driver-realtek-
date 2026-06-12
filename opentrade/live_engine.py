from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from statistics import mean
from typing import Any
from statistics import mean

from trading.data import load_candles_from_csv
from trading.models import Candle, Trade
from trading.orderflow import compute_orderflow
from trading.strategy import StrategyConfig, build_swarm

from .journal import TradeJournal


def _average_true_range(history: list[Candle], period: int = 14) -> float:
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


@dataclass
class OpenPosition:
    side: str
    entry_time: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_confidence: float
    entry_score: float
    entry_agents: str


@dataclass
class SessionState:
    session_id: str
    strategy_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    mode: str
    status: str = "idle"
    initial_balance: float = 10_000.0
    balance: float = 10_000.0
    equity: float = 10_000.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_return_pct: float = 0.0
    win_rate_pct: float = 0.0
    trades_count: int = 0
    wins: int = 0
    candle_index: int = 0
    candles_total: int = 0
    last_price: float = 0.0
    last_timestamp: str = ""
    open_position: dict[str, Any] | None = None
    equity_curve: list[float] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class LivePaperEngine:
    def __init__(self, journal: TradeJournal):
        self.journal = journal
        self._lock = threading.Lock()
        self._state: SessionState | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._subscribers: list[asyncio.Queue] = []
        self._candles: list[Candle] = []
        self._csv_path: str = ""

    def get_state(self) -> dict[str, Any] | None:
        with self._lock:
            if self._state is None:
                return None
            return self._serialize_state(self._state)

    def is_running(self) -> bool:
        with self._lock:
            return self._state is not None and self._state.status == "running"

    def start(
        self,
        *,
        csv_path: str,
        strategy: dict[str, Any],
        initial_balance: float = 10_000.0,
        tick_ms: int = 200,
        start_index: int = 0,
    ) -> dict[str, Any]:
        if self.is_running():
            raise RuntimeError("A live session is already running.")

        candles = load_candles_from_csv(csv_path)
        if not candles:
            raise ValueError("No candles in CSV.")

        config = StrategyConfig.from_dict(strategy["config"])
        session_id = self.journal.create_session(
            strategy_id=strategy["id"],
            strategy_name=strategy["name"],
            symbol=strategy.get("symbol", "EURUSD"),
            timeframe=strategy.get("timeframe", "M1"),
            mode=strategy.get("mode", "paper"),
            config_json=json.dumps(strategy["config"]),
            initial_balance=initial_balance,
        )

        self._stop_event.clear()
        self._candles = candles
        self._csv_path = csv_path
        with self._lock:
            self._state = SessionState(
                session_id=session_id,
                strategy_id=strategy["id"],
                strategy_name=strategy["name"],
                symbol=strategy.get("symbol", "EURUSD"),
                timeframe=strategy.get("timeframe", "M1"),
                mode=strategy.get("mode", "paper"),
                status="running",
                initial_balance=initial_balance,
                balance=initial_balance,
                equity=initial_balance,
                candle_index=start_index,
                candles_total=len(candles),
                config=strategy["config"],
            )

        self._thread = threading.Thread(
            target=self._run_loop,
            args=(candles, config, initial_balance, tick_ms, start_index, strategy),
            daemon=True,
        )
        self._thread.start()
        return self.get_state() or {}

    def stop(self) -> dict[str, Any] | None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        with self._lock:
            if self._state:
                self._state.status = "stopped"
                self.journal.stop_session(self._state.session_id)
                snapshot = self._serialize_state(self._state)
                self._broadcast(snapshot)
                return snapshot
        return None

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def _broadcast(self, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def _serialize_state(self, state: SessionState) -> dict[str, Any]:
        return {
            "session_id": state.session_id,
            "strategy_id": state.strategy_id,
            "strategy_name": state.strategy_name,
            "symbol": state.symbol,
            "timeframe": state.timeframe,
            "mode": state.mode,
            "status": state.status,
            "initial_balance": round(state.initial_balance, 2),
            "balance": round(state.balance, 2),
            "equity": round(state.equity, 2),
            "unrealized_pnl": round(state.unrealized_pnl, 2),
            "realized_pnl": round(state.realized_pnl, 2),
            "total_return_pct": round(state.total_return_pct, 4),
            "win_rate_pct": round(state.win_rate_pct, 2),
            "trades_count": state.trades_count,
            "wins": state.wins,
            "candle_index": state.candle_index,
            "candles_total": state.candles_total,
            "progress_pct": round(state.candle_index / max(1, state.candles_total) * 100, 2),
            "last_price": round(state.last_price, 5),
            "last_timestamp": state.last_timestamp,
            "open_position": state.open_position,
            "equity_curve": state.equity_curve[-200:],
        }

    def get_orderflow(self, *, window: int = 100) -> dict:
        with self._lock:
            end_index = self._state.candle_index if self._state else len(self._candles)
            candles = list(self._candles)
        return compute_orderflow(candles, end_index=end_index, window=window)

    def _run_loop(
        self,
        candles: list[Candle],
        config: StrategyConfig,
        initial_balance: float,
        tick_ms: int,
        start_index: int,
        strategy: dict[str, Any],
    ) -> None:
        swarm = build_swarm(config)
        history: list[Candle] = list(candles[:start_index])
        position: OpenPosition | None = None
        balance = initial_balance
        trades: list[Trade] = []

        for idx in range(start_index, len(candles)):
            if self._stop_event.is_set():
                break

            candle = candles[idx]
            history.append(candle)

            if position is not None:
                exit_price = None
                exit_reason = ""
                if position.side == "long":
                    if candle.low <= position.stop_loss:
                        exit_price = position.stop_loss
                        exit_reason = "stop_loss"
                    elif candle.high >= position.take_profit:
                        exit_price = position.take_profit
                        exit_reason = "take_profit"
                else:
                    if candle.high >= position.stop_loss:
                        exit_price = position.stop_loss
                        exit_reason = "stop_loss"
                    elif candle.low <= position.take_profit:
                        exit_price = position.take_profit
                        exit_reason = "take_profit"

                if exit_price is not None:
                    pnl = (
                        (exit_price - position.entry_price) * position.quantity
                        if position.side == "long"
                        else (position.entry_price - exit_price) * position.quantity
                    )
                    balance += pnl
                    trade = Trade(
                        side=position.side,  # type: ignore[arg-type]
                        entry_time=position.entry_time,
                        exit_time=candle.timestamp,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        quantity=position.quantity,
                        pnl=pnl,
                        reason=exit_reason,
                        entry_confidence=position.entry_confidence,
                        entry_score=position.entry_score,
                        entry_agents=position.entry_agents,
                    )
                    trades.append(trade)
                    risk_amount = balance * config.risk_per_trade
                    pnl_pct = (pnl / risk_amount * 100.0) if risk_amount > 0 else 0.0
                    with self._lock:
                        session_id = self._state.session_id if self._state else ""
                    self.journal.log_trade(
                        {
                            "session_id": session_id,
                            "strategy_id": strategy["id"],
                            "symbol": strategy.get("symbol", "EURUSD"),
                            "side": trade.side,
                            "entry_time": trade.entry_time,
                            "exit_time": trade.exit_time,
                            "entry_price": trade.entry_price,
                            "exit_price": trade.exit_price,
                            "quantity": trade.quantity,
                            "pnl": trade.pnl,
                            "pnl_pct": pnl_pct,
                            "reason": trade.reason,
                            "entry_confidence": trade.entry_confidence,
                            "entry_score": trade.entry_score,
                            "entry_agents": trade.entry_agents,
                            "balance_after": balance,
                        }
                    )
                    position = None
                    self._broadcast({"event": "trade_closed", "trade": trade.__dict__})

            if position is None:
                decision = swarm.decide(history)
                if decision is not None:
                    atr = _average_true_range(history, period=14)
                    if atr > 0:
                        drag = (config.spread_bps + config.slippage_bps) / 10_000.0
                        stop_distance = atr * config.atr_stop_multiplier
                        if stop_distance > 0:
                            risk_amount = balance * config.risk_per_trade
                            quantity = risk_amount / stop_distance
                            entry = candle.close
                            if decision.side == "long":
                                entry *= 1 + drag
                                stop = entry - stop_distance
                                target = entry + stop_distance * config.reward_risk
                            else:
                                entry *= 1 - drag
                                stop = entry + stop_distance
                                target = entry - stop_distance * config.reward_risk
                            position = OpenPosition(
                                side=decision.side,
                                entry_time=candle.timestamp,
                                entry_price=entry,
                                quantity=quantity,
                                stop_loss=stop,
                                take_profit=target,
                                entry_confidence=decision.confidence,
                                entry_score=decision.score,
                                entry_agents="; ".join(
                                    f"{s.agent}:{s.side}:{s.score:.2f}" for s in decision.signals
                                ),
                            )
                            self._broadcast(
                                {
                                    "event": "trade_opened",
                                    "side": position.side,
                                    "entry_price": position.entry_price,
                                    "entry_time": position.entry_time,
                                }
                            )

            if position is None:
                equity = balance
                unrealized = 0.0
            elif position.side == "long":
                unrealized = (candle.close - position.entry_price) * position.quantity
                equity = balance + unrealized
            else:
                unrealized = (position.entry_price - candle.close) * position.quantity
                equity = balance + unrealized

            wins = sum(1 for t in trades if t.pnl > 0)
            win_rate = (wins / len(trades) * 100.0) if trades else 0.0
            realized = balance - initial_balance
            total_return = ((equity - initial_balance) / initial_balance) * 100.0

            with self._lock:
                if self._state:
                    self._state.balance = balance
                    self._state.equity = equity
                    self._state.unrealized_pnl = unrealized
                    self._state.realized_pnl = realized
                    self._state.total_return_pct = total_return
                    self._state.win_rate_pct = win_rate
                    self._state.trades_count = len(trades)
                    self._state.wins = wins
                    self._state.candle_index = idx + 1
                    self._state.last_price = candle.close
                    self._state.last_timestamp = candle.timestamp
                    self._state.open_position = (
                        {
                            "side": position.side,
                            "entry_time": position.entry_time,
                            "entry_price": position.entry_price,
                            "quantity": position.quantity,
                            "stop_loss": position.stop_loss,
                            "take_profit": position.take_profit,
                            "unrealized_pnl": unrealized,
                        }
                        if position
                        else None
                    )
                    self._state.equity_curve.append(equity)
                    snapshot = self._serialize_state(self._state)
                    orderflow = compute_orderflow(candles, end_index=idx + 1, window=100)
                    self._broadcast({"event": "tick", "orderflow": orderflow, **snapshot})

            time.sleep(max(0.05, tick_ms / 1000.0))

        if position is not None and candles:
            last = candles[-1]
            exit_price = last.close
            pnl = (
                (exit_price - position.entry_price) * position.quantity
                if position.side == "long"
                else (position.entry_price - exit_price) * position.quantity
            )
            balance += pnl
            with self._lock:
                session_id = self._state.session_id if self._state else ""
            self.journal.log_trade(
                {
                    "session_id": session_id,
                    "strategy_id": strategy["id"],
                    "symbol": strategy.get("symbol", "EURUSD"),
                    "side": position.side,
                    "entry_time": position.entry_time,
                    "exit_time": last.timestamp,
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "quantity": position.quantity,
                    "pnl": pnl,
                    "reason": "session_end",
                    "entry_confidence": position.entry_confidence,
                    "entry_score": position.entry_score,
                    "entry_agents": position.entry_agents,
                    "balance_after": balance,
                }
            )

        with self._lock:
            if self._state:
                self._state.status = "completed"
                self._state.balance = balance
                self._state.equity = balance
                self.journal.stop_session(self._state.session_id)
                self._broadcast({"event": "session_end", **self._serialize_state(self._state)})
