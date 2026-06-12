"""Restore user's original chart UI if integrate accidentally replaced it with git engine UI."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .old_app_static import UI_BACKUP_DIRNAME, _is_engine_builtin_ui, resolve_old_app_root

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
    "templates",
    "assets",
    "js",
    "css",
)


def _backup_roots(root: Path) -> list[Path]:
    base = root / UI_BACKUP_DIRNAME
    if not base.is_dir():
        return []
    latest = base / "latest"
    roots: list[Path] = []
    if latest.is_dir():
        roots.append(latest.resolve())
    roots.extend(
        sorted(
            (p for p in base.iterdir() if p.is_dir() and p.name != "latest"),
            reverse=True,
        )
    )
    return roots


def _find_custom_index(root: Path) -> Path | None:
    candidates = [
        root / "index.html",
        root / "static" / "index.html",
        root / "public" / "index.html",
        root / "dist" / "index.html",
        root / "frontend" / "index.html",
    ]
    for path in candidates:
        if path.is_file() and not _is_engine_builtin_ui(path):
            return path
    return None


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


def ensure_old_ui_restored() -> dict[str, object]:
    """If only git engine UI is present, restore the newest backup that has a custom chart."""
    root = resolve_old_app_root()
    if root is None:
        return {"restored": False, "reason": "no OPENTRADER_OLD_APP"}

    current = _find_custom_index(root)
    if current is not None:
        return {"restored": False, "reason": "custom_ui_present", "index": str(current)}

    # Engine UI may be masking a missing custom UI — check if static/index is git UI
    engine_index = root / "static" / "index.html"
    needs_restore = engine_index.is_file() and _is_engine_builtin_ui(engine_index)
    if not needs_restore and not (root / "index.html").is_file():
        needs_restore = True

    if not needs_restore:
        return {"restored": False, "reason": "no_ui_detected"}

    for backup in _backup_roots(root):
        custom = _find_custom_index(backup)
        if custom is None:
            continue
        restored: list[str] = []
        for item in _UI_ITEMS:
            if _restore_item(backup, root, item):
                restored.append(item)
        if (backup / "opentrader" / "static").is_dir():
            dest = root / "opentrader" / "static"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(backup / "opentrader" / "static", dest)
            restored.append("opentrader/static")
        logger.warning("Restored old chart UI from backup %s → %s", backup, root)
        return {
            "restored": True,
            "backup": str(backup),
            "items": restored,
            "index": str(_find_custom_index(root) or custom),
        }

    return {
        "restored": False,
        "reason": "no_custom_backup",
        "hint": "Original chart files not found. Set OPENTRADER_UI_INDEX=/path/to/your/index.html in .env",
    }
