"""Resolve old Open Trader app static files (user's original UI)."""
from __future__ import annotations

import os
from pathlib import Path


def resolve_old_app_root() -> Path | None:
    raw = os.environ.get("OPENTRADER_OLD_APP", "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        return None
    return root


def resolve_old_app_static() -> tuple[Path | None, Path | None]:
    """Return (static_dir, index_html) for the old app, or (None, None)."""
    root = resolve_old_app_root()
    if root is None:
        return None, None

    candidates = [
        root / "static",
        root / "public",
        root / "dist",
        root / "frontend" / "dist",
        root / "frontend" / "public",
        root,
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        index = base / "index.html"
        if index.is_file():
            return base, index

    # SPA build without index at expected path — still serve directory
    for base in candidates:
        if base.is_dir() and any(base.glob("*.html")):
            html = next(base.glob("*.html"))
            return base, html
    return None, None
