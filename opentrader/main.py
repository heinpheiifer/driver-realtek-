from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trading.data import load_candles_from_csv
from trading.orderflow import compute_orderflow
from opentrade.live_engine import LivePaperEngine
from opentrade.services import BacktestService, OptimizerService
from opentrade.store import StrategyStore

APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("OPENTRADER_DATA", "opentrader_data"))
DEFAULT_CSV = Path("trading_data/eurusd_m1.csv")

store = StrategyStore(DATA_ROOT)
journal = TradeJournal(DATA_ROOT / "journal.db")
backtest_service = BacktestService()
optimizer_service = OptimizerService()
live_engine = LivePaperEngine(journal)

app = FastAPI(
    title="OpenTrader",
    version="1.0.0",
    description="Unified trading app: live PnL, journal, backtesting, and AI optimizer (OpenTrade engine).",
)


class StrategyConfigPayload(BaseModel):
    risk_per_trade: float = 0.0075
    atr_stop_multiplier: float = 1.4
    reward_risk: float = 1.9
    min_confidence: float = 0.40
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
    min_agreeing_agents: int = 2
    require_quality_setup: bool = True


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


class LiveSessionRequest(BaseModel):
    strategy_id: str
    csv_path: str = str(DEFAULT_CSV)
    initial_balance: float = 10_000.0
    tick_ms: int = 150
    start_index: int = 0


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "OpenTrader",
        "version": "1.0.0",
        "modules": ["live", "journal", "backtest", "optimizer"],
        "engine": "OpenTrade",
    }


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


@app.post("/api/session/start")
def start_live_session(payload: LiveSessionRequest) -> dict[str, Any]:
    strategy = store.get_strategy(payload.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    csv_path = Path(payload.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")
    try:
        state = live_engine.start(
            csv_path=str(csv_path),
            strategy=strategy,
            initial_balance=payload.initial_balance,
            tick_ms=payload.tick_ms,
            start_index=payload.start_index,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return state


@app.post("/api/session/stop")
def stop_live_session() -> dict[str, Any]:
    state = live_engine.stop()
    if state is None:
        raise HTTPException(status_code=404, detail="No active session")
    return state


@app.get("/api/session/status")
def session_status() -> dict[str, Any]:
    state = live_engine.get_state()
    if state is None:
        return {"status": "idle"}
    return state


@app.get("/api/session/stream")
async def session_stream(request: Request) -> StreamingResponse:
    queue = live_engine.subscribe(asyncio.get_running_loop())

    async def generate():
        try:
            current = live_engine.get_state()
            if current:
                yield f"data: {json.dumps({'event': 'snapshot', **current})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            live_engine.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/journal")
def list_journal(
    session_id: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    trades = journal.list_trades(session_id=session_id, limit=limit, offset=offset)
    stats = journal.compute_stats(session_id=session_id)
    return {"trades": trades, "stats": stats}


@app.get("/api/journal/stats")
def journal_stats(session_id: str | None = None) -> dict[str, Any]:
    return journal.compute_stats(session_id=session_id)


@app.get("/api/journal/sessions")
def list_journal_sessions(limit: int = 20) -> list[dict[str, Any]]:
    sessions = journal.list_sessions(limit=limit)
    enriched = []
    for session in sessions:
        stats = journal.compute_stats(session_id=session["id"])
        enriched.append({**session, "stats": stats})
    return enriched


@app.post("/api/optimizer/start")
def start_optimizer(payload: OptimizerRequest) -> dict[str, Any]:
    csv_path = Path(payload.csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")
    job = optimizer_service.start(
        csv_path=str(csv_path),
        output_dir="trading_runs/opentrader_optimizer",
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


@app.get("/api/orderflow")
def get_orderflow(
    csv_path: str = str(DEFAULT_CSV),
    end_index: int | None = None,
    window: int = 100,
) -> dict[str, Any]:
    path = Path(csv_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {path}")
    if live_engine.is_running():
        return live_engine.get_orderflow(window=window)
    candles = load_candles_from_csv(path)
    return compute_orderflow(candles, end_index=end_index, window=window)


@app.get("/api/data/default-csv")
def default_csv_info() -> dict[str, Any]:
    exists = DEFAULT_CSV.exists()
    return {"path": str(DEFAULT_CSV), "exists": exists}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
