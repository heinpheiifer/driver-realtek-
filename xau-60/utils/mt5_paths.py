"""
Locate MetaTrader 5 terminal inside Wine and build paths for the MT5 Python API.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from utils.config import get_env


def wine_prefix() -> Path:
    return Path(os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine")))


def unix_to_wine_path(unix_path: str | Path) -> str:
    """Convert a Linux path under WINEPREFIX to a C:\\... path for MetaTrader5.initialize()."""
    prefix = os.path.realpath(str(wine_prefix()))
    real = os.path.realpath(str(unix_path))
    if not real.startswith(prefix):
        return str(unix_path).replace("/", "\\")

    rel = real[len(prefix):].lstrip("/\\")
    if rel.lower().startswith("drive_c"):
        rel = rel[7:].lstrip("/\\")
    elif rel.lower().startswith("drive_c/"):
        rel = rel[8:]

    return "C:\\" + rel.replace("/", "\\")


def find_wine_mt5_terminal() -> Optional[str]:
    """
    Find terminal64.exe under the Wine prefix.

    Returns:
        Windows-style path suitable for MetaTrader5.initialize(path=...), or None.
    """
    prefix = wine_prefix()
    candidates = [
        prefix / "drive_c/Program Files/MetaTrader 5/terminal64.exe",
        prefix / "drive_c/Program Files/Black Bull Markets MT5/terminal64.exe",
        prefix / "drive_c/Program Files/BlackBull Markets MT5/terminal64.exe",
        prefix / "drive_c/Program Files (x86)/MetaTrader 5/terminal64.exe",
    ]

    try:
        for exe in prefix.glob("drive_c/Program Files/*/terminal64.exe"):
            candidates.append(exe)
    except OSError:
        pass

    seen = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return unix_to_wine_path(path)

    return None


def resolve_mt5_terminal_path(account_path: Optional[str] = None) -> Optional[str]:
    """
    Resolve MT5 terminal path for connect().

    Priority: account path → MT5_WINE_PATH → MT5_PATH → auto-detect in Wine.
    """
    for raw in (account_path, get_env("MT5_WINE_PATH", ""), get_env("MT5_PATH", "")):
        if not raw:
            continue
        p = Path(os.path.expanduser(raw))
        if p.is_file():
            return unix_to_wine_path(p) if str(p).startswith(str(wine_prefix())) else raw
        return raw

    return find_wine_mt5_terminal()
