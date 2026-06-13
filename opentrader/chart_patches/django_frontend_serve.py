"""
Serve Vite production build (frontend/dist) from Django.
Drop-in for ~/OpenTrader — import from opentrader.urls
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.views.static import serve as static_serve

_DIST = Path(settings.BASE_DIR) / "frontend" / "dist"
_ASSETS = _DIST / "assets"


def _dist_file(rel: str) -> Path | None:
    path = (_DIST / rel).resolve()
    try:
        path.relative_to(_DIST.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def serve_index(_request):
    index = _DIST / "index.html"
    if not index.is_file():
        raise Http404(
            "frontend/dist/index.html missing — run: cd frontend && npm install && npm run build"
        )
    return FileResponse(index.open("rb"), content_type="text/html")


def serve_asset(request, path: str):
    if not _ASSETS.is_dir():
        raise Http404("frontend/dist/assets missing — run npm run build in frontend/")
    return static_serve(request, path, document_root=str(_ASSETS))


def serve_root_asset(_request, filename: str):
    """Files referenced from dist root (favicon, manifest, etc.)."""
    found = _dist_file(filename)
    if found is None:
        return HttpResponseNotFound(filename)
    return FileResponse(found.open("rb"))
