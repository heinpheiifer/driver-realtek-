"""Resolve old Open Trader app static files (user's original UI)."""
from __future__ import annotations

import os
from pathlib import Path

UI_BACKUP_DIRNAME = ".opentrader_ui_backup"
DEFAULT_OLD_APP = Path("/home/heinz/opentrade-app")
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
}


def use_old_ui() -> bool:
    """Serve the user's original chart unless OPENTRADER_USE_NEW_UI=1."""
    if os.environ.get("OPENTRADER_USE_NEW_UI", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("OPENTRADER_USE_OLD_UI", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("OPENTRADER_OLD_APP", "").strip():
        return True
    return DEFAULT_OLD_APP.is_dir()


def resolve_old_app_root() -> Path | None:
    if not use_old_ui():
        return None
    raw = os.environ.get("OPENTRADER_OLD_APP", "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
        return root if root.is_dir() else None
    if DEFAULT_OLD_APP.is_dir():
        return DEFAULT_OLD_APP.resolve()
    return None


def _is_engine_builtin_ui(index_path: Path) -> bool:
    """Detect git unified UI — must not serve as the user's original chart."""
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
    if "static" in path.parts or "public" in path.parts or "dist" in path.parts:
        score += 1
    return score


def _index_override() -> Path | None:
    raw = os.environ.get("OPENTRADER_UI_INDEX", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


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
    # When explicitly scanning a backup folder, allow HTML inside it
    if UI_BACKUP_DIRNAME in search_root.parts:
        names = names - {UI_BACKUP_DIRNAME}
    return any(part in names for part in path.parts)


def discover_chart_html(search_root: Path) -> Path | None:
    """Find the best chart HTML under a directory tree."""
    best: tuple[int, Path] | None = None
    if not search_root.is_dir():
        return None

    for html in search_root.rglob("*.html"):
        if _should_skip(html, search_root):
            continue
        if "opentrader" in html.parts and "static" in html.parts and "engine_static" not in html.parts:
            # Skip git engine copy under opentrader/static unless nothing else exists
            if _is_engine_builtin_ui(html):
                continue
        score = _chart_score(html)
        if score < 0:
            continue
        if best is None or score > best[0]:
            best = (score, html)

    return best[1] if best else None


def _static_candidates(root: Path) -> list[Path]:
    return [
        root / "static",
        root / "public",
        root / "dist",
        root / "frontend" / "dist",
        root / "frontend" / "public",
        root / "frontend",
        root / "web",
        root / "ui",
        root / "client",
        root / "chart",
        root / "templates",
        root / "assets",
        root,
    ]


def resolve_old_app_static() -> tuple[Path | None, Path | None]:
    """Return (static_dir, index_html) for the old app, or (None, None)."""
    override = _index_override()
    if override is not None:
        return override.parent, override

    root = resolve_old_app_root()
    if root is None:
        return None, None

    # Search backups oldest-first first (latest may be corrupted git UI)
    for search_root in [*_backup_roots(root, oldest_first=True), root]:
        found = discover_chart_html(search_root)
        if found is not None:
            return found.parent, found

    # Legacy path-based lookup
    for search_root in [root, *_backup_roots(root)]:
        for base in _static_candidates(search_root):
            if not base.is_dir():
                continue
            index = base / "index.html"
            if index.is_file() and not _is_engine_builtin_ui(index):
                return base, index

    return None, None


def old_app_asset_dirs(root: Path | None) -> list[Path]:
    """Extra directories under the old app root to expose as static mounts."""
    if root is None:
        return []
    names = (
        "assets",
        "js",
        "css",
        "public",
        "static",
        "dist",
        "web",
        "ui",
        "client",
        "frontend",
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
    return dirs
