"""
Locate MetaTrader 5 terminal inside Wine and build paths for the MT5 Python API.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from utils.config import get_env


def wine_prefixes() -> List[Path]:
    """Return likely Wine prefix directories."""
    home = Path.home()
    found: List[Path] = []
    seen = set()

    def add(p: Path) -> None:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            found.append(p)

    add(Path(os.environ.get("WINEPREFIX", home / ".wine")))
    add(home / ".wine")

    for p in home.glob(".wine-*"):
        if p.is_dir():
            add(p)

    local = home / ".local/share/wineprefixes"
    if local.is_dir():
        for p in local.iterdir():
            if p.is_dir():
                add(p)

    return found


def wine_prefix() -> Path:
    return wine_prefixes()[0]


def unix_to_wine_path(unix_path: str | Path) -> str:
    """Convert a Linux path under WINEPREFIX to a C:\\... path for MetaTrader5.initialize()."""
    unix_path = Path(unix_path)
    for prefix in wine_prefixes():
        try:
            prefix_real = os.path.realpath(str(prefix))
            real = os.path.realpath(str(unix_path))
            if real.startswith(prefix_real):
                rel = real[len(prefix_real):].lstrip("/\\")
                if rel.lower().startswith("drive_c"):
                    rel = rel[7:].lstrip("/\\")
                return "C:\\" + rel.replace("/", "\\")
        except OSError:
            continue
    return str(unix_path).replace("/", "\\")


def _score_terminal_path(wine_path: str) -> int:
    """Prefer BlackBull / MetaTrader installs over random matches."""
    lower = wine_path.lower()
    score = 0
    if "black" in lower and "bull" in lower:
        score += 100
    if "metatrader" in lower or "mt5" in lower:
        score += 50
    if "terminal64.exe" in lower:
        score += 10
    return score


def list_wine_mt5_terminals() -> List[str]:
    """Find all terminal64.exe / terminal.exe under Wine prefixes."""
    results: List[str] = []
    seen = set()

    for prefix in wine_prefixes():
        drive_c = prefix / "drive_c"
        if not drive_c.is_dir():
            continue
        try:
            for name in ("terminal64.exe", "terminal.exe"):
                for exe in drive_c.rglob(name):
                    if exe.is_file():
                        wp = unix_to_wine_path(exe)
                        if wp not in seen:
                            seen.add(wp)
                            results.append(wp)
        except OSError:
            continue

    results.sort(key=_score_terminal_path, reverse=True)
    return results


def find_wine_mt5_terminal() -> Optional[str]:
    """Return the best MT5 terminal path for MetaTrader5.initialize(path=...)."""
    from_process = find_mt5_from_running_process()
    if from_process:
        return from_process

    terminals = list_wine_mt5_terminals()
    return terminals[0] if terminals else None


def find_mt5_from_running_process() -> Optional[str]:
    """If MT5 is running under Wine, infer terminal64.exe path from /proc."""
    prefix_paths = [os.path.realpath(str(p)) for p in wine_prefixes()]

    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            cmdline_path = f"/proc/{entry}/cmdline"
            try:
                raw = Path(cmdline_path).read_bytes()
            except OSError:
                continue
            parts = [p.decode("utf-8", errors="ignore") for p in raw.split(b"\0") if p]
            line = " ".join(parts).lower()
            if "terminal64" not in line and "terminal.exe" not in line:
                continue
            for part in parts:
                if "terminal64.exe" in part.lower() or part.lower().endswith("terminal.exe"):
                    p = Path(part.replace("\\", "/"))
                    if p.is_file():
                        return unix_to_wine_path(p)
                    # Wine Z: path
                    if part.startswith("Z:") or part.startswith("z:"):
                        unix = part[2:].replace("\\", "/")
                        if Path(unix).is_file():
                            return unix_to_wine_path(unix)
            try:
                exe = os.readlink(f"/proc/{entry}/exe")
                if "terminal64" in exe.lower():
                    for prefix in prefix_paths:
                        if exe.startswith(prefix):
                            return unix_to_wine_path(exe)
            except OSError:
                pass
    except OSError:
        pass

    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "-f", "terminal64"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        for line in out.splitlines():
            match = re.search(r"(/[^ ]*terminal64\.exe)", line, re.I)
            if match and Path(match.group(1)).is_file():
                return unix_to_wine_path(match.group(1))
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return None


def resolve_mt5_terminal_path(account_path: Optional[str] = None) -> Optional[str]:
    """
    Resolve MT5 terminal path for connect().

    Priority: running process → account path → MT5_WINE_PATH → MT5_PATH → scan Wine.
    """
    running = find_mt5_from_running_process()
    if running:
        return running

    for raw in (account_path, get_env("MT5_WINE_PATH", ""), get_env("MT5_PATH", "")):
        if not raw:
            continue
        expanded = os.path.expanduser(raw.strip().strip('"'))
        p = Path(expanded)
        if p.is_file():
            return unix_to_wine_path(p) if any(
                str(p.resolve()).startswith(os.path.realpath(str(prefix)))
                for prefix in wine_prefixes()
            ) else raw.replace("/", "\\")
        # Already Windows path e.g. C:\Program Files\...
        if re.match(r"^[A-Za-z]:\\", expanded):
            return expanded

    return find_wine_mt5_terminal()
