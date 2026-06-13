"""Offline seed candle data — works with no MT5 and no Yahoo network."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _seed_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in (
        REPO_ROOT / "seeds" / "chart",
        Path.cwd() / "seeds" / "chart",
        Path.cwd() / "trading_data" / "seeds",
    ):
        resolved = candidate.resolve()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def ensure_seed_data(*, dest_root: Path | None = None) -> dict[str, object]:
    """Copy bundled seed CSVs into blackbull_import if missing."""
    base = dest_root or Path.cwd()
    dest_import = base / "trading_data" / "blackbull_import"
    dest_cache = base / "trading_data"
    dest_import.mkdir(parents=True, exist_ok=True)
    dest_cache.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for seed_root in _seed_roots():
        for seed in seed_root.glob("*.csv"):
            if seed.stat().st_size < 20:
                continue
            dest = dest_import / seed.name.lower()
            cache = dest_cache / f"{seed.stem}_blackbull.csv"
            for target in (dest, cache):
                if target.exists() and target.stat().st_mtime >= seed.stat().st_mtime:
                    continue
                shutil.copy2(seed, target)
                copied.append(str(target))
    if copied:
        logger.info("Seed data installed: %s file(s)", len(copied))
    return {"copied": copied, "count": len(copied), "seed_roots": [str(r) for r in _seed_roots()]}


def find_seed_file(symbol: str, timeframe: str) -> Path | None:
    symbol = symbol.lower().replace("/", "")
    tf = timeframe.lower()
    name = f"{symbol}_{tf}.csv"
    for seed_root in _seed_roots():
        path = seed_root / name
        if path.is_file():
            return path
    return None
