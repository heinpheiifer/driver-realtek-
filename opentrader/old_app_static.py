"""Resolve old Open Trader app static files (user's original UI)."""
from __future__ import annotations

import os
from pathlib import Path

UI_BACKUP_DIRNAME = ".opentrader_ui_backup"
DEFAULT_OLD_APP = Path("/home/heinz/opentrade-app")
ENGINE_STATIC_MARKERS = ("Open Trader", "btnBookmapToggle", "runBacktestBtn")


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
    """Detect git unified UI — must not replace user's original chart app."""
    try:
        text = index_path.read_text(encoding="utf-8", errors="ignore")[:12000]
    except OSError:
        return False
    return sum(1 for marker in ENGINE_STATIC_MARKERS if marker in text) >= 2


def _index_override() -> Path | None:
    raw = os.environ.get("OPENTRADER_UI_INDEX", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


def _backup_roots(root: Path) -> list[Path]:
    backup_base = root / UI_BACKUP_DIRNAME
    if not backup_base.is_dir():
        return []
    latest = backup_base / "latest"
    roots: list[Path] = []
    if latest.is_dir():
        roots.append(latest.resolve())
    roots.extend(
        sorted(
            (p for p in backup_base.iterdir() if p.is_dir() and p.name != "latest"),
            reverse=True,
        )
    )
    return roots


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

    search_roots = [root, *_backup_roots(root)]

    for search_root in search_roots:
        for base in _static_candidates(search_root):
            if not base.is_dir():
                continue
            index = base / "index.html"
            if not index.is_file():
                continue
            if search_root is root and _is_engine_builtin_ui(index):
                continue
            return base, index

        for base in _static_candidates(search_root):
            if not base.is_dir():
                continue
            for html in sorted(base.glob("*.html")):
                if html.name.startswith("."):
                    continue
                if search_root is root and _is_engine_builtin_ui(html):
                    continue
                return base, html

    return None, None


def old_app_asset_dirs(root: Path | None) -> list[Path]:
    """Extra directories under the old app root to expose as static mounts."""
    if root is None:
        return []
    names = ("assets", "js", "css", "public", "static", "dist", "web", "ui", "client", "frontend")
    dirs: list[Path] = []
    seen: set[Path] = set()
    for name in names:
        path = (root / name).resolve()
        if path in seen or not path.is_dir():
            continue
        seen.add(path)
        dirs.append(path)
    return dirs
