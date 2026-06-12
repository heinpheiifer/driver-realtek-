"""Resolve old Open Trader app static files (user's original UI)."""
from __future__ import annotations

import os
from pathlib import Path

UI_BACKUP_DIRNAME = ".opentrader_ui_backup"
# Real chart lives in OpenTrader (capital T) — not opentrade-app (engine only)
DEFAULT_CHART_ROOTS = (
    Path("/home/heinz/OpenTrader"),
    Path("/home/heinz/opentrade-app"),
)
PREFERRED_INDEX_RELATIVE = (
    "frontend/dist/index.html",
    "frontend/index.html",
    "staticfiles/index.html",
    "static/index.html",
    "public/index.html",
    "index.html",
)
ENGINE_STATIC_MARKERS = ("btnBookmapToggle", "runBacktestBtn", "strategyList", "startOptimizerBtn")
OLD_CHART_MARKERS = (
    "heikin",
    "Heikin",
    "drawing",
    "lightweight-charts",
    "LightweightCharts",
    "tradingview",
    "chart-container",
    "bookmap",
    "Bookmap",
    "blackbull",
    "BlackBull",
)
_SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "engine_static",
    UI_BACKUP_DIRNAME,
    "opentrader_data",
    "trading_runs",
    ".mt5",
}


def use_old_ui() -> bool:
    """Serve the user's original chart unless OPENTRADER_USE_NEW_UI=1."""
    if os.environ.get("OPENTRADER_USE_NEW_UI", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("OPENTRADER_USE_OLD_UI", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("OPENTRADER_OLD_APP", "").strip():
        return True
    return any(p.is_dir() for p in DEFAULT_CHART_ROOTS)


def _is_engine_builtin_ui(index_path: Path) -> bool:
    if index_path.name == "missing_old_ui.html":
        return True
    try:
        text = index_path.read_text(encoding="utf-8", errors="ignore")[:16000]
    except OSError:
        return False
    hits = sum(1 for marker in ENGINE_STATIC_MARKERS if marker in text)
    return hits >= 2


def _chart_score(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:16000].lower()
    except OSError:
        return -1
    if _is_engine_builtin_ui(path):
        return -1
    score = 0
    for marker in OLD_CHART_MARKERS:
        if marker.lower() in text:
            score += 3
    if path.name == "index.html":
        score += 2
    if "frontend" in path.parts and "dist" in path.parts:
        score += 4
    if "opentrader" in path.parts or "opentrade-app" in path.parts:
        score -= 5
    if "static" in path.parts or "public" in path.parts or "dist" in path.parts:
        score += 1
    return score


def _index_override() -> Path | None:
    raw = os.environ.get("OPENTRADER_UI_INDEX", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


def _preferred_index(root: Path) -> Path | None:
    for rel in PREFERRED_INDEX_RELATIVE:
        path = root / rel
        if path.is_file() and not _is_engine_builtin_ui(path):
            return path
    return None


def resolve_old_app_root() -> Path | None:
    if not use_old_ui():
        return None
    raw = os.environ.get("OPENTRADER_OLD_APP", "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
        return root if root.is_dir() else None
    for candidate in DEFAULT_CHART_ROOTS:
        if not candidate.is_dir():
            continue
        if _preferred_index(candidate) or discover_chart_html(candidate):
            return candidate.resolve()
    return None


def _backup_roots(root: Path, *, oldest_first: bool = False) -> list[Path]:
    backup_base = root / UI_BACKUP_DIRNAME
    if not backup_base.is_dir():
        return []
    dated = sorted(
        (p for p in backup_base.iterdir() if p.is_dir() and p.name != "latest"),
        reverse=not oldest_first,
    )
    latest = backup_base / "latest"
    if latest.is_dir():
        return ([latest.resolve()] if not oldest_first else []) + [p.resolve() for p in dated] + (
            [latest.resolve()] if oldest_first else []
        )
    return [p.resolve() for p in dated]


def _should_skip(path: Path, search_root: Path) -> bool:
    names = _SKIP_DIR_NAMES
    if UI_BACKUP_DIRNAME in search_root.parts:
        names = names - {UI_BACKUP_DIRNAME}
    if path.name == "missing_old_ui.html":
        return True
    return any(part in names for part in path.parts)


def discover_chart_html(search_root: Path) -> Path | None:
    preferred = _preferred_index(search_root)
    if preferred is not None:
        return preferred

    best: tuple[int, Path] | None = None
    if not search_root.is_dir():
        return None

    for html in search_root.rglob("*.html"):
        if _should_skip(html, search_root):
            continue
        if "opentrader" in html.parts and "static" in html.parts and _is_engine_builtin_ui(html):
            continue
        score = _chart_score(html)
        if score < 0:
            continue
        if best is None or score > best[0]:
            best = (score, html)

    return best[1] if best else None


def _static_candidates(root: Path) -> list[Path]:
    return [
        root / "frontend" / "dist",
        root / "frontend",
        root / "staticfiles",
        root / "static",
        root / "public",
        root / "dist",
        root / "web",
        root / "ui",
        root / "client",
        root / "chart",
        root / "templates",
        root / "assets",
        root,
    ]


def resolve_old_app_static() -> tuple[Path | None, Path | None]:
    override = _index_override()
    if override is not None:
        return override.parent, override

    root = resolve_old_app_root()
    if root is None:
        return None, None

    preferred = _preferred_index(root)
    if preferred is not None:
        return preferred.parent, preferred

    for search_root in [*_backup_roots(root, oldest_first=True), root]:
        found = discover_chart_html(search_root)
        if found is not None:
            return found.parent, found

    for search_root in [root, *_backup_roots(root)]:
        for base in _static_candidates(search_root):
            if not base.is_dir():
                continue
            index = base / "index.html"
            if index.is_file() and not _is_engine_builtin_ui(index):
                return base, index

    return None, None


def old_app_asset_dirs(root: Path | None) -> list[Path]:
    if root is None:
        return []
    names = (
        "frontend",
        "staticfiles",
        "assets",
        "js",
        "css",
        "public",
        "static",
        "dist",
        "web",
        "ui",
        "client",
        "chart",
    )
    dirs: list[Path] = []
    seen: set[Path] = set()
    for name in names:
        path = (root / name).resolve()
        if path in seen or not path.is_dir():
            continue
        seen.add(path)
        dirs.append(path)
    # frontend/dist assets often referenced as /assets/ from dist root
    fdist = (root / "frontend" / "dist").resolve()
    if fdist.is_dir() and fdist not in seen:
        seen.add(fdist)
        dirs.append(fdist)
    return dirs
