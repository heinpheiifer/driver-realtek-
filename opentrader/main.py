from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trading.data import load_candles_from_csv
from trading.blackbull_mt5 import (
    connect_mt5,
    fetch_mt5_candles,
    list_mt5_symbols,
    load_symbols_manifest,
    mt5_status,
    sync_all_mt5_symbols,
)
from trading.market_data import BlackbullDataError, import_blackbull_candles, load_market_candles
from trading.orderflow import compute_orderflow
from opentrade.journal import TradeJournal
from opentrade.live_engine import LivePaperEngine
from opentrade.services import BacktestService, OptimizerService
from opentrade.store import StrategyStore

from .bookmap_bridge import BookmapBridge
from .mt5_autosync import mt5_autosync

APP_ROOT = Path(__file__).resolve().parent
_env_path = APP_ROOT.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

DATA_ROOT = Path(os.environ.get("OPENTRADER_DATA", "opentrader_data"))
DEFAULT_CSV = Path("trading_data/eurusd_m1.csv")

store = StrategyStore(DATA_ROOT)
journal = TradeJournal(DATA_ROOT / "journal.db")
backtest_service = BacktestService()
optimizer_service = OptimizerService()
live_engine = LivePaperEngine(journal)
bookmap_bridge = BookmapBridge()

app = FastAPI(
    title="OpenTrader",
    version="2.0.0",
    description="Unified trading app: chart, Bookmap order flow, strategy, journal, backtest, and AI optimizer.",
)


@app.on_event("startup")
def _startup_mt5_autosync() -> None:
    """Auto-connect MT5 and sync all BlackBull symbols — same as old Open Trader."""
    mt5_autosync.start()


@app.on_event("shutdown")
def _shutdown_mt5_autosync() -> None:
    mt5_autosync.stop()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8010",
        "http://localhost:8010",
        "http://127.0.0.1:8011",
        "http://localhost:8011",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


class BookmapEventPayload(BaseModel):
    type: str
    timestamp: str | None = None
    price: float | None = None
    size: float | None = None
    delta: float = 0.0
    side: str | None = None


class BookmapReplayRequest(BaseModel):
    csv_path: str = str(DEFAULT_CSV)
    tick_ms: int = 200
    window: int = 80


class MarketLoadRequest(BaseModel):
    symbol: str = "BTCUSD"
    source: str = "yahoo"
    timeframe: str = "M5"
    bars: int = 800
    csv_path: str | None = None


class CandleRowPayload(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class BlackbullImportPayload(BaseModel):
    symbol: str
    timeframe: str = "M5"
    candles: list[CandleRowPayload]


def _resolve_csv(
    *,
    symbol: str = "BTCUSD",
    source: str = "yahoo",
    timeframe: str = "M5",
    csv_path: str | None = None,
    bars: int = 800,
) -> tuple[str, list]:
    _, _, path, _ = load_market_candles(
        symbol=symbol,
        source=source,
        csv_path=csv_path,
        bars=bars,
        timeframe=timeframe,
    )
    return path, load_candles_from_csv(Path(path))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "OpenTrader",
        "version": "2.0.0",
        "modules": ["chart", "bookmap", "live", "journal", "backtest", "optimizer", "market"],
        "engine": "OpenTrade",
        "unified": True,
        "mt5_autosync": mt5_autosync.status,
    }


@app.get("/api/market/sources")
def market_sources() -> dict[str, Any]:
    return {
        "sources": [
            {"id": "yahoo", "label": "Yahoo Finance"},
            {"id": "blackbull", "label": "BlackBull Markets (MT5)"},
            {"id": "csv", "label": "Local CSV"},
        ],
        "default_symbol": "BTCUSD",
        "default_source": "blackbull",
    }


@app.get("/api/market/candles")
def market_candles(
    symbol: str = "BTCUSD",
    source: str = "yahoo",
    timeframe: str = "M5",
    bars: int = 800,
    csv_path: str | None = None,
    window: int = 100,
) -> dict[str, Any]:
    try:
        candles, source_label, path, meta = load_market_candles(
            symbol=symbol,
            source=source,
            csv_path=csv_path,
            bars=bars,
            timeframe=timeframe,
        )
    except BlackbullDataError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(exc),
                "mt5": (exc.meta or {}).get("mt5"),
                "hint": "Start BlackBull MT5, set MT5_* env vars, or run scripts/mt5_python_bridge.py",
            },
        ) from exc
    if not candles:
        raise HTTPException(status_code=404, detail=f"No candles for {symbol} ({source})")
    orderflow = compute_orderflow(candles, window=min(window, len(candles)))
    last = candles[-1]
    is_synthetic = source_label.startswith("synthetic:")
    return {
        "symbol": symbol.upper(),
        "source": source_label,
        "requested_source": source.lower(),
        "is_synthetic": is_synthetic,
        "timeframe": timeframe.upper(),
        "csv_path": path,
        "count": len(candles),
        "last_price": last.close,
        "last_timestamp": last.timestamp,
        "mt5": meta.get("mt5") if meta else mt5_status() if source.lower() == "blackbull" else None,
        "used_cache": (meta or {}).get("used_cache") if meta else False,
        "candles": [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles[-min(bars, 500) :]
        ],
        "orderflow": orderflow,
    }


@app.post("/api/market/load")
def market_load(payload: MarketLoadRequest) -> dict[str, Any]:
    return market_candles(
        symbol=payload.symbol,
        source=payload.source,
        timeframe=payload.timeframe,
        bars=payload.bars,
        csv_path=payload.csv_path,
    )


@app.get("/api/market/mt5/status")
def market_mt5_status() -> dict[str, Any]:
    status = mt5_status()
    return {"mt5": status, "autosync": mt5_autosync.status}


@app.post("/api/market/mt5/sync-now")
def market_mt5_sync_now() -> dict[str, Any]:
    """Force immediate MT5 sync (all symbols) — old app did this automatically."""
    return mt5_autosync.sync_now()


@app.post("/api/market/mt5/connect")
def market_mt5_connect() -> dict[str, Any]:
    connected = connect_mt5()
    return {"connected": connected, "mt5": mt5_status()}


@app.post("/api/market/blackbull/sync")
def market_blackbull_sync(
    symbol: str = "BTCUSD",
    timeframe: str = "M5",
    bars: int = 800,
) -> dict[str, Any]:
    result = fetch_mt5_candles(symbol=symbol, timeframe=timeframe, bars=bars)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail={"message": "MT5 sync failed", "mt5": mt5_status()},
        )
    candles, source_label, path = result
    orderflow = compute_orderflow(candles, window=min(100, len(candles)))
    return {
        "synced": True,
        "source": source_label,
        "csv_path": path,
        "count": len(candles),
        "last_price": candles[-1].close,
        "orderflow": orderflow,
        "mt5": mt5_status(),
    }


@app.post("/api/market/blackbull/import")
def market_blackbull_import(payload: BlackbullImportPayload) -> dict[str, Any]:
    if not payload.candles:
        raise HTTPException(status_code=400, detail="No candles provided")
    rows = [row.model_dump() for row in payload.candles]
    candles, source_label, path = import_blackbull_candles(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        rows=rows,
    )
    orderflow = compute_orderflow(candles, window=min(100, len(candles)))
    return {
        "imported": len(candles),
        "source": source_label,
        "csv_path": path,
        "orderflow": orderflow,
        "mt5": mt5_status(),
    }


@app.get("/api/mt5/symbols")
@app.get("/api/market/symbols")
@app.get("/api/symbols")
def market_symbols(live: bool = False) -> dict[str, Any]:
    """All BlackBull/MT5 symbols — used by the Open Trader chart symbol search."""
    if live:
        symbols = list_mt5_symbols()
        return {"source": "mt5", "count": len(symbols), "symbols": symbols, "mt5": mt5_status()}
    manifest = load_symbols_manifest()
    if manifest:
        return {"source": "manifest", **manifest, "mt5": mt5_status()}
    return {
        "source": "empty",
        "count": 0,
        "symbols": [],
        "message": "Run scripts/mt5_python_bridge.py --all-symbols on Windows with BlackBull MT5",
        "mt5": mt5_status(),
    }


@app.post("/api/mt5/sync-all")
@app.post("/api/market/blackbull/sync-all")
def market_blackbull_sync_all(
    bars: int = 800,
    visible_only: bool = False,
    timeframes: str = "M1,M5,H1",
) -> dict[str, Any]:
    tfs = [t.strip().upper() for t in timeframes.split(",") if t.strip()]
    return sync_all_mt5_symbols(timeframes=tfs, bars=bars, visible_only=visible_only)


@app.get("/api/candles")
@app.get("/api/bars")
def legacy_candles(
    symbol: str = "XRPUSD",
    timeframe: str = "M1",
    source: str = "blackbull",
    bars: int = 800,
    limit: int | None = None,
) -> dict[str, Any]:
    """Legacy Open Trader chart endpoint — BlackBull/MT5 OHLCV bars."""
    return market_candles(
        symbol=symbol,
        source=source,
        timeframe=timeframe,
        bars=limit or bars,
    )


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


@app.get("/api/bookmap/status")
def bookmap_status() -> dict[str, Any]:
    return bookmap_bridge.status


@app.get("/api/bookmap/signals")
def bookmap_signals(limit: int = 100) -> dict[str, Any]:
    return {"signals": bookmap_bridge.get_signals(limit=limit), **bookmap_bridge.status}


@app.post("/api/bookmap/event")
def bookmap_ingest_event(payload: BookmapEventPayload) -> dict[str, Any]:
    bookmap_bridge.ingest_bookmap_event(payload.model_dump())
    return bookmap_bridge.status


@app.post("/api/bookmap/start-replay")
def bookmap_start_replay(payload: BookmapReplayRequest) -> dict[str, Any]:
    path = Path(payload.csv_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {path}")
    bookmap_bridge.start_replay(
        csv_path=str(path),
        tick_ms=payload.tick_ms,
        window=payload.window,
    )
    return bookmap_bridge.status


@app.post("/api/bookmap/stop")
def bookmap_stop() -> dict[str, Any]:
    bookmap_bridge.stop()
    return bookmap_bridge.status


@app.get("/api/bookmap/stream")
async def bookmap_stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    def on_event(payload: dict[str, Any]) -> None:
        queue.put_nowait(payload)

    bookmap_bridge.subscribe(on_event)

    async def generate():
        try:
            yield f"data: {json.dumps({'event': 'snapshot', **bookmap_bridge.status})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bookmap_bridge.unsubscribe(on_event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/orderflow")
def get_orderflow(
    csv_path: str | None = None,
    symbol: str = "BTCUSD",
    source: str = "yahoo",
    timeframe: str = "M5",
    end_index: int | None = None,
    window: int = 100,
) -> dict[str, Any]:
    if live_engine.is_running():
        return live_engine.get_orderflow(window=window)
    if csv_path:
        path = Path(csv_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"CSV not found: {path}")
        candles = load_candles_from_csv(path)
    else:
        _, candles = _resolve_csv(symbol=symbol, source=source, timeframe=timeframe)
    return compute_orderflow(candles, end_index=end_index, window=window)


@app.get("/api/data/default-csv")
def default_csv_info() -> dict[str, Any]:
    exists = DEFAULT_CSV.exists()
    return {"path": str(DEFAULT_CSV), "exists": exists}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(APP_ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=APP_ROOT / "static"), name="static")
