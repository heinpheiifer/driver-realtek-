from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .services import BacktestService, OptimizerService
from .store import StrategyStore

APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path("opentrade_data")
DEFAULT_CSV = Path("trading_data/eurusd_m1.csv")

app = FastAPI(title="OpenTrade", version="0.1.0")
store = StrategyStore(DATA_ROOT)
backtest_service = BacktestService()
optimizer_service = OptimizerService()


class StrategyConfigPayload(BaseModel):
    risk_per_trade: float = 0.0075
    atr_stop_multiplier: float = 1.4
    reward_risk: float = 1.9
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


class StrategyPayload(BaseModel):
    id: str | None = None
    name: str = "Swarm Scalper"
    symbol: str = "EURUSD"
    timeframe: str = "M1"
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    config: StrategyConfigPayload


class BacktestRequest(BaseModel):
    strategy_id: str | None = None
    config: StrategyConfigPayload | None = None
    csv_path: str = str(DEFAULT_CSV)
    mode: str = Field(default="paper", pattern="^(paper|live)$")
    walk_forward: bool = True
    initial_balance: float = 10_000.0


class OptimizerRequest(BaseModel):
    csv_path: str = str(DEFAULT_CSV)
    max_iterations: int = 0
    gates: dict[str, float] | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "OpenTrade"}


@app.get("/api/strategies")
def list_strategies() -> list[dict[str, Any]]:
    return store.list_strategies()


@app.get("/api/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> dict[str, Any]:
    strategy = store.get_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@app.post("/api/strategies")
def save_strategy(payload: StrategyPayload) -> dict[str, Any]:
    return store.save_strategy(payload.model_dump())


@app.delete("/api/strategies/{strategy_id}")
def delete_strategy(strategy_id: str) -> dict[str, bool]:
    deleted = store.delete_strategy(strategy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"deleted": True}


@app.post("/api/backtest")
def run_backtest(payload: BacktestRequest) -> dict[str, Any]:
    config = payload.config.model_dump() if payload.config else None
    if payload.strategy_id:
        strategy = store.get_strategy(payload.strategy_id)
        if strategy is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        config = strategy["config"]
        payload.mode = strategy.get("mode", payload.mode)

    if config is None:
        raise HTTPException(status_code=400, detail="Strategy config required")

    csv_path = Path(payload.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")

    result = backtest_service.run(
        csv_path=str(csv_path),
        config=config,
        initial_balance=payload.initial_balance,
        walk_forward=payload.walk_forward,
    )
    run_record = store.save_run(
        {
            "type": "backtest",
            "mode": payload.mode,
            "strategy_id": payload.strategy_id,
            "config": config,
            "csv_path": str(csv_path),
            "result": result,
        }
    )
    return {"run_id": run_record["id"], **result}


@app.post("/api/optimizer/start")
def start_optimizer(payload: OptimizerRequest) -> dict[str, Any]:
    csv_path = Path(payload.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")
    job = optimizer_service.start(
        csv_path=str(csv_path),
        output_dir="trading_runs/opentrade_optimizer",
        gates=payload.gates,
        max_iterations=payload.max_iterations,
    )
    return job


@app.get("/api/optimizer/jobs")
def list_optimizer_jobs() -> list[dict[str, Any]]:
    return optimizer_service.list_jobs()


@app.get("/api/optimizer/jobs/{job_id}")
def optimizer_job_status(job_id: str) -> dict[str, Any]:
    job = optimizer_service.status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Optimizer job not found")
    return job


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    return store.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/data/default-csv")
def default_csv_info() -> dict[str, Any]:
    exists = DEFAULT_CSV.exists()
    return {"path": str(DEFAULT_CSV), "exists": exists}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
