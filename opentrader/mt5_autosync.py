"""Auto-sync BlackBull MT5 data on server startup — matches old Open Trader behavior."""
from __future__ import annotations

import logging
import os
import platform
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class Mt5AutoSync:
    """Background thread: Wine MT5 file import + optional live MT5 sync."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._running = False
        self._last_result: dict[str, Any] = {}

    @property
    def wine_sync_enabled(self) -> bool:
        raw = os.environ.get("MT5_WINE_SYNC", "").strip().lower()
        if raw in ("0", "false", "no"):
            return False
        if raw in ("1", "true", "yes"):
            return True
        return platform.system() == "Linux"

    @property
    def enabled(self) -> bool:
        raw = os.environ.get("MT5_AUTO_SYNC", "").strip().lower()
        if raw in ("0", "false", "no"):
            return False
        if raw in ("1", "true", "yes"):
            return True
        return False

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
            "wine_sync": self.wine_sync_enabled,
            "running": self._running,
            "interval_sec": self.interval_sec,
            "timeframes": self.timeframes,
            "last_result": self._last_result,
        }

    def start(self) -> None:
        if self._running or (not self.enabled and not self.wine_sync_enabled):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="mt5-autosync", daemon=True)
        self._thread.start()
        self._running = True
        logger.info(
            "MT5 sync started (wine_files=%s, live_mt5=%s, interval=%ss)",
            self.wine_sync_enabled,
            self.enabled,
            self.interval_sec,
        )

    def stop(self) -> None:
        self._stop.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def sync_wine_files(self) -> dict[str, Any]:
        from trading.blackbull_mt5 import sync_wine_mt5_exports

        result = sync_wine_mt5_exports()
        result["ok"] = result.get("count", 0) > 0
        self._last_result = result
        if result.get("count"):
            logger.info("Wine MT5 import: %s file(s)", result["count"])
        return result

    def sync_now(self) -> dict[str, Any]:
        from trading.blackbull_mt5 import connect_mt5, mt5_status, sync_all_mt5_symbols

        if self.wine_sync_enabled:
            wine = self.sync_wine_files()
            if wine.get("ok") and not self.enabled:
                return wine

        try:
            import MetaTrader5  # noqa: F401
        except ImportError:
            if self.wine_sync_enabled:
                return self._last_result
            result = {"ok": False, "reason": "MetaTrader5 not installed (Windows + MT5 required)"}
            self._last_result = result
            return result

        if not connect_mt5():
            if self._last_result.get("ok"):
                return self._last_result
            result = {"ok": False, "reason": "MT5 connect failed", "mt5": mt5_status()}
            self._last_result = result
            return result

        result = sync_all_mt5_symbols(timeframes=self.timeframes, bars=800)
        result["ok"] = result.get("synced", 0) > 0
        self._last_result = result
        logger.info("MT5 sync: %s symbols, %s pairs", result.get("symbols"), result.get("synced"))
        return result

    def _loop(self) -> None:
        self.sync_now()
        while not self._stop.wait(self.interval_sec):
            try:
                self.sync_now()
            except Exception as exc:
                logger.warning("MT5 auto-sync error: %s", exc)
                self._last_result = {"ok": False, "error": str(exc)}


mt5_autosync = Mt5AutoSync()
