from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fetch_data import save_ohlcv_csv
from .models import Candle
from .seed_data import ensure_seed_data, find_seed_file

logger = logging.getLogger(__name__)

MT5_TIMEFRAMES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}

_last_status: dict[str, Any] = {
    "available": False,
    "connected": False,
    "broker": None,
    "server": None,
    "account": None,
    "terminal": None,
    "last_error": None,
    "last_sync": None,
}


def mt5_status() -> dict[str, Any]:
    return dict(_last_status)


def _set_status(**kwargs: Any) -> None:
    _last_status.update(kwargs)


def _import_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore

        return mt5
    except ImportError:
        _set_status(
            available=False,
            connected=False,
            last_error="MetaTrader5 package not installed. Run: pip install MetaTrader5",
        )
        return None


def _cache_path(symbol: str, timeframe: str) -> Path:
    return Path("trading_data") / f"{symbol.lower()}_{timeframe.lower()}_blackbull.csv"


def _import_path(symbol: str, timeframe: str) -> Path:
    return Path("trading_data") / "blackbull_import" / f"{symbol.lower()}_{timeframe.lower()}.csv"


def find_wine_mt5_files_dirs() -> list[Path]:
    """Find MQL5/Files folders under Wine MT5 (~/.mt5/drive_c)."""
    dirs: list[Path] = []
    seen: set[Path] = set()
    for wine_root in (
        Path.home() / ".mt5" / "drive_c",
        Path.home() / ".wine" / "drive_c",
        Path(os.environ.get("WINEPREFIX", "")).expanduser() / "drive_c"
        if os.environ.get("WINEPREFIX")
        else None,
    ):
        if wine_root is None or not wine_root.is_dir():
            continue
        for files_dir in wine_root.rglob("MQL5"):
            candidate = files_dir / "Files"
            if candidate.is_dir():
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    dirs.append(resolved)
    return dirs


def find_wine_mt5_terminal() -> Path | None:
    """Find terminal64.exe under Wine MT5 prefix."""
    for wine_root in (Path.home() / ".mt5" / "drive_c", Path.home() / ".wine" / "drive_c"):
        if not wine_root.is_dir():
            continue
        for exe in wine_root.rglob("terminal64.exe"):
            return exe.resolve()
    return None


def _parse_csv_name(name: str) -> tuple[str, str] | None:
    stem = Path(name).stem.lower()
    match = re.match(r"^([a-z0-9]+)_([mhdw][0-9]+|mn1)$", stem)
    if not match:
        return None
    return match.group(1).upper(), match.group(2).upper()


def sync_wine_mt5_exports(*, dest_root: Path | None = None) -> dict[str, Any]:
    """Import BlackBull CSV exports from Wine MT5 MQL5/Files → trading_data."""
    base = dest_root or Path.cwd()
    dest_import = base / "trading_data" / "blackbull_import"
    dest_cache = base / "trading_data"
    dest_import.mkdir(parents=True, exist_ok=True)
    dest_cache.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    sources: list[str] = []

    for files_dir in find_wine_mt5_files_dirs():
        sources.append(str(files_dir))
        search_dirs = [files_dir / "blackbull_import", files_dir]
        for src_dir in search_dirs:
            if not src_dir.is_dir():
                continue
            for csv in src_dir.glob("*.csv"):
                try:
                    if csv.stat().st_size < 20:
                        continue
                    dest_import_path = dest_import / csv.name.lower()
                    if dest_import_path.exists() and dest_import_path.stat().st_mtime >= csv.stat().st_mtime:
                        continue
                    shutil.copy2(csv, dest_import_path)
                    copied.append(str(dest_import_path))

                    parsed = _parse_csv_name(csv.name)
                    if parsed:
                        sym, tf = parsed
                        cache_path = dest_cache / f"{sym.lower()}_{tf.lower()}_blackbull.csv"
                        shutil.copy2(csv, cache_path)
                        copied.append(str(cache_path))
                except OSError as exc:
                    logger.warning("Wine MT5 import failed for %s: %s", csv, exc)

    if copied:
        _set_status(
            last_sync=datetime.now(tz=timezone.utc).isoformat(),
            last_source="blackbull:wine_files",
            wine_files_sources=sources,
        )
    return {"copied": copied, "count": len(copied), "sources": sources}


def _wine_mt5_path_for_init() -> str | None:
    """Path for MetaTrader5.initialize() — Wine-style if under ~/.mt5."""
    explicit = os.environ.get("MT5_PATH", "").strip()
    if explicit:
        return explicit
    terminal = find_wine_mt5_terminal()
    if terminal is None:
        return None
    # MetaTrader5 on Wine often expects C:/... style path inside the prefix
    drive_c = Path.home() / ".mt5" / "drive_c"
    try:
        rel = terminal.relative_to(drive_c)
        return str(rel).replace("\\", "/")
    except ValueError:
        return str(terminal)


def _extra_data_roots() -> list[Path]:
    """Also load BlackBull CSV cache from OpenTrader project folder."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for raw in (
        os.environ.get("OPENTRADER_OLD_APP", ""),
        os.environ.get("OPENTRADER_CHART_ROOT", ""),
        "/home/heinz/OpenTrader",
    ):
        if not raw:
            continue
        base = Path(raw).expanduser().resolve()
        if base in seen or not base.is_dir():
            continue
        seen.add(base)
        roots.append(base)
    return roots


def _resolve_cache_file(symbol: str, timeframe: str) -> Path | None:
    symbol = symbol.upper().replace("/", "")
    tf = timeframe.upper()
    names = (
        f"{symbol.lower()}_{tf.lower()}.csv",
        f"{symbol.lower()}_{tf.lower()}_blackbull.csv",
    )
    rel_dirs = (
        Path("trading_data") / "blackbull_import",
        Path("trading_data"),
        Path("data") / "blackbull_import",
        Path("data") / "market",
        Path("market_data"),
    )
    search_roots = [Path.cwd(), *_extra_data_roots()]
    for root in search_roots:
        for rel in rel_dirs:
            for name in names:
                path = (root / rel / name).resolve()
                if path.is_file():
                    return path
        for name in names:
            direct = (root / name).resolve()
            if direct.is_file():
                return direct
    for path in (_cache_path(symbol, tf), _import_path(symbol, tf)):
        if path.is_file():
            return path
    seed = find_seed_file(symbol, tf)
    if seed is not None:
        return seed
    return None


def _candles_to_rows(candles: list[Candle]) -> list[dict[str, str | float]]:
    return [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]


def save_blackbull_candles(
    *,
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    source_label: str = "blackbull:import",
) -> str:
    symbol = symbol.upper().replace("/", "")
    tf = timeframe.upper()
    path = _cache_path(symbol, tf)
    save_ohlcv_csv(path, _candles_to_rows(candles))
    _set_status(last_sync=datetime.now(tz=timezone.utc).isoformat(), last_source=source_label)
    return str(path)


def load_cached_blackbull(
    *,
    symbol: str,
    timeframe: str,
    bars: int,
) -> tuple[list[Candle], str, str] | None:
    from .data import load_candles_from_csv

    symbol = symbol.upper().replace("/", "")
    tf = timeframe.upper()
    path = _resolve_cache_file(symbol, tf)
    if path is not None:
        candles = load_candles_from_csv(path)
        if candles:
            label = "blackbull:import" if "blackbull_import" in str(path) else "blackbull:cache"
            return candles[-bars:], label, str(path)
    return None


def resolve_mt5_symbol(mt5, symbol: str) -> str | None:
    symbol = symbol.upper().replace("/", "")
    candidates = [
        symbol,
        f"{symbol}.a",
        f"{symbol}.b",
        f"{symbol}.pro",
        f"{symbol}m",
        f"{symbol}.m",
        f"{symbol}.raw",
    ]
    for candidate in candidates:
        info = mt5.symbol_info(candidate)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(candidate, True)
            return candidate

    matches = []
    for info in mt5.symbols_get() or []:
        name = info.name.upper()
        if name == symbol or name.startswith(symbol):
            matches.append(info.name)
    if matches:
        chosen = sorted(matches, key=len)[0]
        mt5.symbol_select(chosen, True)
        return chosen
    return None


def _mt5_timeframe(mt5, timeframe: str):
    tf = timeframe.upper()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }
    return mapping.get(tf, mt5.TIMEFRAME_M5)


def connect_mt5() -> bool:
    mt5 = _import_mt5()
    if mt5 is None:
        return False

    _set_status(available=True)
    path = _wine_mt5_path_for_init()
    login = os.environ.get("MT5_LOGIN")
    password = os.environ.get("MT5_PASSWORD")
    server = os.environ.get("MT5_SERVER")

    init_kwargs: dict[str, Any] = {}
    if path:
        init_kwargs["path"] = path
    if login and password and server:
        init_kwargs["login"] = int(login)
        init_kwargs["password"] = password
        init_kwargs["server"] = server

    if not mt5.initialize(**init_kwargs):
        err = mt5.last_error()
        _set_status(connected=False, last_error=f"MT5 initialize failed: {err}")
        return False

    info = mt5.account_info()
    terminal = mt5.terminal_info()
    _set_status(
        connected=True,
        last_error=None,
        account=getattr(info, "login", None),
        server=getattr(info, "server", None) or server,
        broker=getattr(info, "company", None),
        terminal=getattr(terminal, "name", None),
    )
    return True


def fetch_mt5_candles(
    *,
    symbol: str,
    timeframe: str = "M5",
    bars: int = 800,
) -> tuple[list[Candle], str, str] | None:
    mt5 = _import_mt5()
    if mt5 is None:
        return None

    if not _last_status.get("connected"):
        if not connect_mt5():
            return None

    mt5_symbol = resolve_mt5_symbol(mt5, symbol)
    if mt5_symbol is None:
        _set_status(last_error=f"Symbol not found in MT5: {symbol}")
        return None

    tf = _mt5_timeframe(mt5, timeframe)
    rates = mt5.copy_rates_from_pos(mt5_symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        _set_status(last_error=f"No MT5 rates for {mt5_symbol} {timeframe}: {mt5.last_error()}")
        return None

    candles: list[Candle] = []
    for row in rates:
        ts = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        volume = float(row["real_volume"] or row["tick_volume"] or 0)
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=volume,
            )
        )

    path = save_blackbull_candles(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        source_label=f"blackbull:mt5({mt5_symbol})",
    )
    _set_status(
        last_sync=datetime.now(tz=timezone.utc).isoformat(),
        last_symbol=mt5_symbol,
        last_error=None,
    )
    return candles, f"blackbull:mt5({mt5_symbol})", path


def shutdown_mt5() -> None:
    mt5 = _import_mt5()
    if mt5 is not None:
        try:
            mt5.shutdown()
        except Exception:
            pass
    _set_status(connected=False)


def list_mt5_symbols(*, visible_only: bool = False, tradeable_only: bool = True) -> list[dict[str, Any]]:
    """Return all BlackBull/MT5 symbols for the Open Trader symbol picker."""
    mt5 = _import_mt5()
    if mt5 is None:
        return []
    if not _last_status.get("connected") and not connect_mt5():
        return []

    rows: list[dict[str, Any]] = []
    for info in mt5.symbols_get() or []:
        if visible_only and not info.visible:
            continue
        if tradeable_only and getattr(info, "trade_mode", 0) == 0:
            continue
        rows.append(
            {
                "name": info.name,
                "description": getattr(info, "description", "") or "",
                "path": getattr(info, "path", "") or "",
                "digits": getattr(info, "digits", 5),
                "visible": bool(info.visible),
                "currency_base": getattr(info, "currency_base", ""),
                "currency_profit": getattr(info, "currency_profit", ""),
            }
        )
    rows.sort(key=lambda r: r["name"])
    _set_status(symbol_count=len(rows))
    return rows


def _symbols_manifest_path() -> Path:
    return Path("trading_data") / "blackbull_symbols.json"


def save_symbols_manifest(symbols: list[dict[str, Any]], *, timeframes: list[str]) -> str:
    import json

    manifest = {
        "updated": datetime.now(tz=timezone.utc).isoformat(),
        "broker": _last_status.get("broker"),
        "server": _last_status.get("server"),
        "count": len(symbols),
        "timeframes": timeframes,
        "symbols": [s["name"] for s in symbols],
        "details": symbols,
    }
    path = _symbols_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(path)


def load_symbols_manifest() -> dict[str, Any] | None:
    import json

    path = _symbols_manifest_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def sync_all_mt5_symbols(
    *,
    timeframes: list[str] | None = None,
    bars: int = 800,
    visible_only: bool = False,
) -> dict[str, Any]:
    """Pull all BlackBull symbols from MT5 and cache OHLCV CSVs."""
    tfs = timeframes or ["M1", "M5", "H1"]
    symbols = list_mt5_symbols(visible_only=visible_only)
    if not symbols:
        return {"synced": 0, "errors": 1, "message": "No MT5 symbols", "mt5": mt5_status()}

    manifest_path = save_symbols_manifest(symbols, timeframes=tfs)
    synced = 0
    errors: list[str] = []

    for row in symbols:
        sym = row["name"]
        clean = sym.upper().replace("/", "").split(".")[0]
        for tf in tfs:
            result = fetch_mt5_candles(symbol=clean, timeframe=tf, bars=bars)
            if result:
                synced += 1
            else:
                errors.append(f"{sym}:{tf}")

    _set_status(
        last_sync=datetime.now(tz=timezone.utc).isoformat(),
        last_sync_count=synced,
        symbol_manifest=manifest_path,
    )
    return {
        "synced": synced,
        "symbols": len(symbols),
        "timeframes": tfs,
        "manifest": manifest_path,
        "errors": errors[:20],
        "error_count": len(errors),
        "mt5": mt5_status(),
    }


def load_blackbull_candles(
    *,
    symbol: str = "BTCUSD",
    timeframe: str = "M5",
    bars: int = 800,
) -> tuple[list[Candle], str, str, dict[str, Any]]:
    """Load BlackBull candles — Wine MT5 files, cache, then live MT5."""
    meta: dict[str, Any] = {"mt5": mt5_status()}

    # 0. Pull latest CSV exports from Wine MT5 (Linux + Wine)
    if os.environ.get("MT5_WINE_SYNC", "1").strip().lower() not in ("0", "false", "no"):
        wine = sync_wine_mt5_exports()
        if wine.get("count"):
            meta["wine_sync"] = wine

    # 1. Cached / imported data (works on Linux after bridge sync — no error)
    cached = load_cached_blackbull(symbol=symbol, timeframe=timeframe, bars=bars)
    if cached:
        candles, label, path = cached
        meta["used_cache"] = True
        return candles, label, path, meta

    # 1b. Same symbol, different timeframe cache (e.g. M5 when M1 not synced yet)
    for alt_tf in ("M5", "M1", "M15", "H1", "H4", "D1"):
        if alt_tf == timeframe.upper():
            continue
        alt = load_cached_blackbull(symbol=symbol, timeframe=alt_tf, bars=bars)
        if alt:
            candles, label, path = alt
            meta["used_cache"] = True
            meta["timeframe_fallback"] = alt_tf
            return candles, label, path, meta

    # 2. Live MT5 pull when terminal is connected (Windows, same machine as MT5)
    mt5 = _import_mt5()
    if mt5 is not None and (_last_status.get("connected") or connect_mt5()):
        live = fetch_mt5_candles(symbol=symbol, timeframe=timeframe, bars=bars)
        if live:
            candles, label, path = live
            meta["mt5"]["connected"] = True
            return candles, label, path, meta

    meta["mt5"]["hint"] = (
        "No BlackBull data for this symbol/timeframe yet. "
        "If your old app had MT5 working, run: bash scripts/restore_old_ui.sh && FORCE=1 bash run.sh. "
        "On Linux, run scripts/mt5_python_bridge.py on Windows pointing at this machine, "
        "or click Yahoo/CSV until MT5 cache is populated."
    )
    return [], "blackbull:unavailable", "", meta
