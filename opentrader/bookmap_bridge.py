from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from trading.data import load_candles_from_csv
from trading.orderflow import compute_orderflow


class BookmapBridge:
    """Bridge Bookmap-style order-flow signals for the Open Trader chart UI.

    When Bookmap Python API is not connected, synthesizes signals from OHLCV replay
    so the Order Flow panel can show live-like updates.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._cvd = 0.0
        self._signals: list[dict[str, Any]] = []
        self._status = "waiting"
        self._source = "synthetic"

    @property
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self._status,
                "source": self._source,
                "cvd": round(self._cvd, 3),
                "signal_count": len(self._signals),
                "connected": self._running,
            }

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def _emit(self, payload: dict[str, Any]) -> None:
        for callback in list(self._subscribers):
            try:
                callback(payload)
            except Exception:
                pass

    def ingest_bookmap_event(self, event: dict[str, Any]) -> None:
        """Accept events from Bookmap Python API export addon."""
        with self._lock:
            self._source = "bookmap"
            self._status = "live"
            event_type = event.get("type", "unknown")
            delta = float(event.get("delta", 0.0))
            self._cvd += delta
            signal = {
                "type": event_type,
                "timestamp": event.get("timestamp", datetime.now(tz=timezone.utc).isoformat()),
                "price": event.get("price"),
                "size": event.get("size"),
                "delta": delta,
                "side": event.get("side"),
            }
            self._signals.append(signal)
            self._signals = self._signals[-500:]
        self._emit({"event": "bookmap_signal", "signal": signal, "cvd": self._cvd})

    def start_replay(
        self,
        *,
        csv_path: str,
        tick_ms: int = 200,
        window: int = 80,
    ) -> None:
        self.stop()
        self._running = True
        self._thread = threading.Thread(
            target=self._replay_loop,
            args=(csv_path, tick_ms, window),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def _replay_loop(self, csv_path: str, tick_ms: int, window: int) -> None:
        candles = load_candles_from_csv(csv_path)
        if not candles:
            with self._lock:
                self._status = "error"
            return

        with self._lock:
            self._source = "ohlcv_replay"
            self._status = "live"
            self._cvd = 0.0
            self._signals = []

        start = max(0, len(candles) - 500)
        for idx in range(start, len(candles)):
            if not self._running:
                break
            candle = candles[idx]
            flow = compute_orderflow(candles, end_index=idx + 1, window=window)
            delta = flow.get("delta", 0.0)
            self._cvd += delta * 0.01

            signals: list[dict[str, Any]] = []
            body = abs(candle.close - candle.open)
            rng = max(candle.high - candle.low, 1e-9)
            body_ratio = body / rng

            if body_ratio > 0.65:
                signals.append(
                    {
                        "type": "large_print",
                        "timestamp": candle.timestamp,
                        "price": candle.close,
                        "size": candle.volume,
                        "delta": delta,
                        "side": "buy" if candle.close >= candle.open else "sell",
                    }
                )
            if candle.close > candle.open and delta > 0:
                signals.append(
                    {
                        "type": "absorption",
                        "timestamp": candle.timestamp,
                        "price": candle.close,
                        "size": candle.volume * 0.5,
                        "delta": delta,
                        "side": "buy",
                    }
                )
            elif candle.close < candle.open and delta < 0:
                signals.append(
                    {
                        "type": "sweep",
                        "timestamp": candle.timestamp,
                        "price": candle.low if candle.close < candle.open else candle.high,
                        "size": candle.volume * 0.4,
                        "delta": delta,
                        "side": "sell",
                    }
                )
            if abs(delta) > flow.get("total_buy", 1) * 0.15:
                signals.append(
                    {
                        "type": "imbalance",
                        "timestamp": candle.timestamp,
                        "price": candle.close,
                        "size": abs(delta),
                        "delta": delta,
                        "side": "buy" if delta > 0 else "sell",
                    }
                )

            with self._lock:
                self._signals.extend(signals)
                self._signals = self._signals[-500:]

            payload = {
                "event": "bookmap_tick",
                "cvd": round(self._cvd, 3),
                "orderflow": flow,
                "signals": signals,
                "candle": {
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                },
            }
            self._emit(payload)
            time.sleep(max(0.05, tick_ms / 1000.0))

        with self._lock:
            self._status = "completed"

    def get_signals(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._signals[-limit:])
