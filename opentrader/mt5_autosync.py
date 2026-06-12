"""Auto-sync BlackBull MT5 data on server startup — matches old Open Trader behavior."""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class Mt5AutoSync:
    """Background thread: connect MT5 on startup and refresh all symbols periodically."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._running = False
        self._last_result: dict[str, Any] = {}

    @property
    def enabled(self) -> bool:
        raw = os.environ.get("MT5_AUTO_SYNC", "").strip().lower()
        if raw in ("0", "false", "no"):
            return False
        if raw in ("1", "true", "yes"):
            return True
        # Old Open Trader app already connects to MT5 — skip duplicate sync unless opted in.
        if os.environ.get("OPENTRADER_OLD_APP", "").strip():
            return False
        return True

    @property
    def interval_sec(self) -> int:
        return max(15, int(os.environ.get("MT5_SYNC_INTERVAL", "60")))

    @property
    def timeframes(self) -> list[str]:
        raw = os.environ.get("MT5_SYNC_TIMEFRAMES", "M1,M5,H1")
        return [t.strip().upper() for t in raw.split(",") if t.strip()]

    @property
    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_sec": self.interval_sec,
            "timeframes": self.timeframes,
            "last_result": self._last_result,
        }

    def start(self) -> None:
        if not self.enabled or self._running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="mt5-autosync", daemon=True)
        self._thread.start()
        self._running = True
        logger.info("MT5 auto-sync started (interval=%ss)", self.interval_sec)

    def stop(self) -> None:
        self._stop.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def sync_now(self) -> dict[str, Any]:
        from trading.blackbull_mt5 import connect_mt5, mt5_status, sync_all_mt5_symbols

        try:
            import MetaTrader5  # noqa: F401
        except ImportError:
            result = {"ok": False, "reason": "MetaTrader5 not installed (Windows + MT5 required)"}
            self._last_result = result
            return result

        if not connect_mt5():
            result = {"ok": False, "reason": "MT5 connect failed", "mt5": mt5_status()}
            self._last_result = result
            return result

        result = sync_all_mt5_symbols(timeframes=self.timeframes, bars=800)
        result["ok"] = result.get("synced", 0) > 0
        self._last_result = result
        logger.info("MT5 sync: %s symbols, %s pairs", result.get("symbols"), result.get("synced"))
        return result

    def _loop(self) -> None:
        # Initial sync immediately on startup (like old app)
        self.sync_now()
        while not self._stop.wait(self.interval_sec):
            try:
                self.sync_now()
            except Exception as exc:
                logger.warning("MT5 auto-sync error: %s", exc)
                self._last_result = {"ok": False, "error": str(exc)}


mt5_autosync = Mt5AutoSync()
