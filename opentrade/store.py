from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STRATEGY = {
    "name": "Swarm Scalper Default",
    "symbol": "EURUSD",
    "timeframe": "M1",
    "mode": "paper",
    "config": {
        "risk_per_trade": 0.0075,
        "atr_stop_multiplier": 1.4,
        "reward_risk": 1.9,
        "min_confidence": 0.40,
        "vp_window": 120,
        "sm_window": 50,
        "liq_window": 35,
        "trend_fast": 12,
        "trend_slow": 48,
        "spread_bps": 1.0,
        "slippage_bps": 0.5,
        "weight_volume_profile": 1.2,
        "weight_smart_money": 1.4,
        "weight_liquidity_sweep": 1.1,
        "weight_trend_bias": 0.8,
        "min_agreeing_agents": 2,
    },
}


class StrategyStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.strategies_dir = self.root / "strategies"
        self.runs_dir = self.root / "runs"
        self.strategies_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default()

    def _ensure_default(self) -> None:
        if not any(self.strategies_dir.glob("*.json")):
            self.save_strategy(DEFAULT_STRATEGY)

    def _now(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def list_strategies(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.strategies_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                rows.append(json.load(handle))
        return rows

    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        path = self.strategies_dir / f"{strategy_id}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_strategy(self, payload: dict[str, Any]) -> dict[str, Any]:
        strategy_id = payload.get("id") or str(uuid.uuid4())
        existing = self.get_strategy(strategy_id)
        record = {
            "id": strategy_id,
            "name": payload.get("name", "Untitled Strategy"),
            "symbol": payload.get("symbol", "EURUSD"),
            "timeframe": payload.get("timeframe", "M1"),
            "mode": payload.get("mode", "paper"),
            "config": payload.get("config", DEFAULT_STRATEGY["config"]),
            "created_at": existing.get("created_at") if existing else self._now(),
            "updated_at": self._now(),
        }
        path = self.strategies_dir / f"{strategy_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
        return record

    def delete_strategy(self, strategy_id: str) -> bool:
        path = self.strategies_dir / f"{strategy_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def save_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = payload.get("id") or str(uuid.uuid4())
        record = {"id": run_id, "created_at": self._now(), **payload}
        path = self.runs_dir / f"{run_id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
        return record

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.runs_dir.glob("*.json"), reverse=True)[:limit]:
            with path.open("r", encoding="utf-8") as handle:
                rows.append(json.load(handle))
        return rows

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
