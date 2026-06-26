"""
HTTP bridge server for MetaTrader 5 (Windows only).

Run this on the machine where MT5 is installed. Linux/macOS clients set
MT5_BRIDGE_URL to reach this server for real balances and trading.

Usage:
    python bridge/server.py
    python bridge/server.py --host 0.0.0.0 --port 8021
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import MetaTrader5 as mt5
except ImportError as exc:
    raise SystemExit(
        "MetaTrader5 package is required on the bridge host (Windows).\n"
        "Install with: pip install MetaTrader5 fastapi uvicorn"
    ) from exc

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import uvicorn


BRIDGE_TOKEN = os.getenv("MT5_BRIDGE_TOKEN", "").strip()
DEFAULT_HOST = os.getenv("MT5_BRIDGE_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("MT5_BRIDGE_PORT", "8021"))


def _serialize_account(info) -> Dict[str, Any]:
    return {
        "login": info.login,
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "margin_free": info.margin_free,
        "margin_level": info.margin_level or 0.0,
        "profit": info.profit,
        "currency": info.currency,
        "leverage": info.leverage,
        "server": info.server,
        "company": info.company,
        "trade_allowed": getattr(info, "trade_allowed", True),
        "trade_expert": getattr(info, "trade_expert", True),
    }


def _serialize_terminal(info) -> Dict[str, Any]:
    return {
        "connected": info.connected,
        "trade_allowed": info.trade_allowed,
        "company": info.company,
        "name": info.name,
        "path": info.path,
    }


def _serialize_symbol(info) -> Dict[str, Any]:
    return {
        "name": info.name,
        "description": info.description,
        "point": info.point,
        "digits": info.digits,
        "spread": info.spread,
        "volume_min": info.volume_min,
        "volume_max": info.volume_max,
        "volume_step": info.volume_step,
        "trade_tick_size": info.trade_tick_size,
        "trade_tick_value": info.trade_tick_value,
        "trade_contract_size": info.trade_contract_size,
        "trade_mode": info.trade_mode,
        "trade_stops_level": getattr(info, "trade_stops_level", 0),
        "trade_freeze_level": getattr(info, "trade_freeze_level", 0),
    }


def _serialize_tick(tick) -> Dict[str, Any]:
    return {
        "time": tick.time,
        "bid": tick.bid,
        "ask": tick.ask,
        "last": tick.last,
        "volume": tick.volume,
    }


def _serialize_position(pos) -> Dict[str, Any]:
    return {
        "ticket": pos.ticket,
        "time": pos.time,
        "type": pos.type,
        "magic": pos.magic,
        "volume": pos.volume,
        "price_open": pos.price_open,
        "sl": pos.sl,
        "tp": pos.tp,
        "price_current": pos.price_current,
        "profit": pos.profit,
        "symbol": pos.symbol,
        "comment": pos.comment,
    }


def _serialize_order(order) -> Dict[str, Any]:
    return {
        "ticket": order.ticket,
        "symbol": order.symbol,
        "type": order.type,
        "volume_current": order.volume_current,
        "price_open": order.price_open,
        "sl": order.sl,
        "tp": order.tp,
        "time_setup": order.time_setup,
        "time_expiration": order.time_expiration,
        "magic": order.magic,
        "comment": order.comment,
    }


def _serialize_deal(deal) -> Dict[str, Any]:
    return {
        "ticket": deal.ticket,
        "order": deal.order,
        "time": deal.time,
        "type": deal.type,
        "volume": deal.volume,
        "price": deal.price,
        "profit": deal.profit,
        "commission": deal.commission,
        "swap": deal.swap,
        "magic": deal.magic,
        "symbol": deal.symbol,
        "comment": deal.comment,
    }


def _serialize_rates(rates) -> List[Dict[str, Any]]:
    if rates is None:
        return []
    return [
        {
            "time": int(row["time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "tick_volume": int(row["tick_volume"]),
            "spread": int(row["spread"]),
            "real_volume": int(row["real_volume"]),
        }
        for row in rates
    ]


def _serialize_order_result(result) -> Dict[str, Any]:
    if result is None:
        return {"ok": False, "error": mt5.last_error()}
    return {
        "ok": True,
        "retcode": result.retcode,
        "deal": result.deal,
        "order": result.order,
        "volume": result.volume,
        "price": result.price,
        "bid": result.bid,
        "ask": result.ask,
        "comment": result.comment,
        "request_id": getattr(result, "request_id", 0),
    }


class InitializeRequest(BaseModel):
    path: Optional[str] = None
    timeout: int = 60000


class LoginRequest(BaseModel):
    login: int
    password: str = ""
    server: str = ""
    timeout: int = 60000


class SymbolSelectRequest(BaseModel):
    symbol: str
    enable: bool = True


class OrderSendRequest(BaseModel):
    request: Dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="XAU-60 MT5 Bridge", version="1.0.0")


def verify_token(
    authorization: Optional[str] = Header(default=None),
    x_bridge_token: Optional[str] = Header(default=None, alias="X-Bridge-Token"),
) -> None:
    if not BRIDGE_TOKEN:
        return
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_bridge_token:
        token = x_bridge_token.strip()
    if token != BRIDGE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid bridge token")


@app.get("/api/health")
def health(_: None = Depends(verify_token)) -> Dict[str, Any]:
    terminal = mt5.terminal_info()
    account = mt5.account_info()
    return {
        "status": "ok",
        "platform": "windows",
        "terminal_connected": bool(terminal and terminal.connected),
        "account_login": account.login if account else None,
        "server": account.server if account else None,
    }


@app.post("/api/initialize")
def initialize(body: InitializeRequest, _: None = Depends(verify_token)) -> Dict[str, Any]:
    params: Dict[str, Any] = {"timeout": body.timeout}
    if body.path:
        params["path"] = body.path
    ok = mt5.initialize(**params)
    if not ok:
        code, message = mt5.last_error()
        raise HTTPException(status_code=400, detail={"code": code, "message": message})
    return {"ok": True}


@app.post("/api/shutdown")
def shutdown(_: None = Depends(verify_token)) -> Dict[str, Any]:
    mt5.shutdown()
    return {"ok": True}


@app.post("/api/login")
def login(body: LoginRequest, _: None = Depends(verify_token)) -> Dict[str, Any]:
    ok = mt5.login(body.login, password=body.password, server=body.server, timeout=body.timeout)
    if not ok:
        code, message = mt5.last_error()
        raise HTTPException(status_code=400, detail={"code": code, "message": message})
    account = mt5.account_info()
    return {"ok": True, "account": _serialize_account(account) if account else None}


@app.get("/api/last_error")
def last_error(_: None = Depends(verify_token)) -> Dict[str, Any]:
    code, message = mt5.last_error()
    return {"code": code, "message": message}


@app.get("/api/terminal_info")
def terminal_info(_: None = Depends(verify_token)) -> Dict[str, Any]:
    info = mt5.terminal_info()
    if not info:
        raise HTTPException(status_code=404, detail="Terminal not available")
    return _serialize_terminal(info)


@app.get("/api/account_info")
def account_info(_: None = Depends(verify_token)) -> Dict[str, Any]:
    info = mt5.account_info()
    if not info:
        raise HTTPException(status_code=404, detail="Account not available")
    return _serialize_account(info)


@app.get("/api/symbol_info")
def symbol_info(symbol: str, _: None = Depends(verify_token)) -> Dict[str, Any]:
    info = mt5.symbol_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")
    return _serialize_symbol(info)


@app.get("/api/symbol_info_tick")
def symbol_info_tick(symbol: str, _: None = Depends(verify_token)) -> Dict[str, Any]:
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise HTTPException(status_code=404, detail=f"Tick not available: {symbol}")
    return _serialize_tick(tick)


@app.post("/api/symbol_select")
def symbol_select(body: SymbolSelectRequest, _: None = Depends(verify_token)) -> Dict[str, Any]:
    ok = mt5.symbol_select(body.symbol, body.enable)
    return {"ok": bool(ok)}


@app.get("/api/positions")
def positions(
    symbol: Optional[str] = None,
    ticket: Optional[int] = None,
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    if ticket is not None:
        rows = mt5.positions_get(ticket=ticket)
    elif symbol:
        rows = mt5.positions_get(symbol=symbol)
    else:
        rows = mt5.positions_get()
    return {"positions": [_serialize_position(row) for row in (rows or [])]}


@app.get("/api/orders")
def orders(symbol: Optional[str] = None, _: None = Depends(verify_token)) -> Dict[str, Any]:
    rows = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
    return {"orders": [_serialize_order(row) for row in (rows or [])]}


@app.post("/api/order_send")
def order_send(body: OrderSendRequest, _: None = Depends(verify_token)) -> Dict[str, Any]:
    result = mt5.order_send(body.request)
    payload = _serialize_order_result(result)
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=payload.get("error"))
    return payload


@app.get("/api/copy_rates_from_pos")
def copy_rates_from_pos(
    symbol: str,
    timeframe: int,
    start_pos: int = 0,
    count: int = 100,
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
    return {"rates": _serialize_rates(rates)}


@app.get("/api/copy_rates_from")
def copy_rates_from(
    symbol: str,
    timeframe: int,
    date_from: datetime,
    count: int = 100,
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    rates = mt5.copy_rates_from(symbol, timeframe, date_from, count)
    return {"rates": _serialize_rates(rates)}


@app.get("/api/copy_rates_range")
def copy_rates_range(
    symbol: str,
    timeframe: int,
    date_from: datetime,
    date_to: datetime,
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    return {"rates": _serialize_rates(rates)}


@app.get("/api/history_deals")
def history_deals(
    date_from: datetime,
    date_to: datetime,
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    deals = mt5.history_deals_get(date_from, date_to)
    return {"deals": [_serialize_deal(row) for row in (deals or [])]}


def main() -> None:
    parser = argparse.ArgumentParser(description="XAU-60 MT5 bridge server (Windows)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    print(f"Starting MT5 bridge on http://{args.host}:{args.port}")
    if BRIDGE_TOKEN:
        print("Bridge token authentication: enabled")
    else:
        print("Bridge token authentication: disabled (set MT5_BRIDGE_TOKEN for LAN security)")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
