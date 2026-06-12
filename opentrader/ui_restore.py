"""Restore user's original chart UI if integrate accidentally replaced it with git engine UI."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .old_app_static import (
    UI_BACKUP_DIRNAME,
    _is_engine_builtin_ui,
    discover_chart_html,
    resolve_old_app_root,
)

logger = logging.getLogger(__name__)

_UI_ITEMS = (
    "index.html",
    "static",
    "public",
    "dist",
    "frontend",
    "web",
    "ui",
    "client",
    "chart",
    "templates",
    "assets",
    "js",
    "css",
)


def _backup_roots(root: Path) -> list[Path]:
    base = root / UI_BACKUP_DIRNAME
    if not base.is_dir():
        return []
    dated = sorted(
        (p for p in base.iterdir() if p.is_dir() and p.name != "latest"),
        reverse=False,
    )
    latest = base / "latest"
    roots = [p.resolve() for p in dated]
    if latest.is_dir():
        roots.append(latest.resolve())
    return roots


def _find_custom_index(root: Path) -> Path | None:
    return discover_chart_html(root)


def _restore_item(backup: Path, old_app: Path, name: str) -> bool:
    src = backup / name
    if not src.exists():
        return False
    dest = old_app / name
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return True


def _remove_engine_ui(root: Path) -> None:
    """Delete git engine UI files that block serving the real chart."""
    targets = [
        root / "static" / "index.html",
        root / "opentrader" / "static" / "index.html",
    ]
    for path in targets:
        if path.is_file() and _is_engine_builtin_ui(path):
            path.unlink()
            logger.warning("Removed git engine UI: %s", path)


def ensure_old_ui_restored() -> dict[str, object]:
    """Restore the oldest backup that contains a real chart (not git engine UI)."""
    root = resolve_old_app_root()
    if root is None:
        return {"restored": False, "reason": "no OPENTRADER_OLD_APP"}

    current = _find_custom_index(root)
    if current is not None and not _is_engine_builtin_ui(current):
        return {"restored": False, "reason": "custom_ui_present", "index": str(current)}

    _remove_engine_ui(root)

    for backup in _backup_roots(root):
        custom = _find_custom_index(backup)
        if custom is None or _is_engine_builtin_ui(custom):
            continue
        restored: list[str] = []
        for item in _UI_ITEMS:
            if _restore_item(backup, root, item):
                restored.append(item)
        if (backup / "opentrader" / "static").is_dir():
            dest = root / "opentrader" / "static"
            idx = dest / "index.html"
            if not idx.is_file() or not _is_engine_builtin_ui(idx):
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(backup / "opentrader" / "static", dest)
                restored.append("opentrader/static")
        _remove_engine_ui(root)
        found = _find_custom_index(root)
        logger.warning("Restored old chart UI from backup %s → %s", backup, root)
        return {
            "restored": True,
            "backup": str(backup),
            "items": restored,
            "index": str(found or custom),
        }

    found = _find_custom_index(root)
    if found is not None:
        return {"restored": False, "reason": "found_after_cleanup", "index": str(found)}

    return {
        "restored": False,
        "reason": "no_custom_backup",
        "hint": (
            "Original chart not in backups. Search: find /home/heinz/opentrade-app -name '*.html' "
            "then set OPENTRADER_UI_INDEX=/path/to/your/chart.html in .env"
        ),
    }
