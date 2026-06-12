from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TradeJournal:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT,
                    strategy_name TEXT,
                    symbol TEXT,
                    timeframe TEXT,
                    mode TEXT,
                    config_json TEXT,
                    initial_balance REAL,
                    started_at TEXT,
                    stopped_at TEXT,
                    status TEXT
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    strategy_id TEXT,
                    symbol TEXT,
                    side TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    reason TEXT,
                    entry_confidence REAL,
                    entry_score REAL,
                    entry_agents TEXT,
                    balance_after REAL,
                    created_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id);
                CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
                """
            )

    def create_session(
        self,
        *,
        strategy_id: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        mode: str,
        config_json: str,
        initial_balance: float,
    ) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, strategy_id, strategy_name, symbol, timeframe, mode,
                    config_json, initial_balance, started_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    strategy_id,
                    strategy_name,
                    symbol,
                    timeframe,
                    mode,
                    config_json,
                    initial_balance,
                    now,
                    "running",
                ),
            )
        return session_id

    def stop_session(self, session_id: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, stopped_at = ? WHERE id = ?",
                ("stopped", now, session_id),
            )

    def log_trade(self, payload: dict[str, Any]) -> str:
        trade_id = payload.get("id") or str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trades (
                    id, session_id, strategy_id, symbol, side,
                    entry_time, exit_time, entry_price, exit_price,
                    quantity, pnl, pnl_pct, reason,
                    entry_confidence, entry_score, entry_agents,
                    balance_after, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id,
                    payload["session_id"],
                    payload.get("strategy_id", ""),
                    payload.get("symbol", ""),
                    payload["side"],
                    payload["entry_time"],
                    payload["exit_time"],
                    payload["entry_price"],
                    payload["exit_price"],
                    payload["quantity"],
                    payload["pnl"],
                    payload.get("pnl_pct", 0.0),
                    payload.get("reason", ""),
                    payload.get("entry_confidence", 0.0),
                    payload.get("entry_score", 0.0),
                    payload.get("entry_agents", ""),
                    payload.get("balance_after", 0.0),
                    now,
                ),
            )
        return trade_id

    def list_trades(
        self,
        *,
        session_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM trades"
        params: list[Any] = []
        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)
        query += " ORDER BY exit_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def compute_stats(self, session_id: str | None = None) -> dict[str, Any]:
        query = "SELECT * FROM trades"
        params: list[Any] = []
        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        if not rows:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "avg_pnl": 0.0,
            }

        pnls = [row["pnl"] for row in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        return {
            "total_trades": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(pnls) * 100.0, 2),
            "total_pnl": round(sum(pnls), 2),
            "avg_win": round(gross_profit / len(wins), 2) if wins else 0.0,
            "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0,
            "best_trade": round(max(pnls), 2),
            "worst_trade": round(min(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(pnls), 2),
        }
