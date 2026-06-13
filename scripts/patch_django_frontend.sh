#!/usr/bin/env bash
# Fix blank page at http://127.0.0.1:8010 — serve Vite frontend/dist + /assets/
#
# Usage:
#   bash scripts/patch_django_frontend.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"
ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_SRC="$ENGINE_ROOT/opentrader/chart_patches/django_frontend_serve.py"

if [[ ! -f "$CHART_ROOT/manage.py" ]]; then
  echo "ERROR: $CHART_ROOT/manage.py not found"
  exit 1
fi

echo "==> Fix Django blank page: $CHART_ROOT"

DEST_PKG=""
for pkg in opentrader config project; do
  if [[ -d "$CHART_ROOT/$pkg" ]]; then
    DEST_PKG="$CHART_ROOT/$pkg"
    break
  fi
done
if [[ -z "$DEST_PKG" ]]; then
  DEST_PKG="$CHART_ROOT/opentrader"
  mkdir -p "$DEST_PKG"
fi
cp "$PATCH_SRC" "$DEST_PKG/frontend_serve.py"
echo "  copied frontend_serve.py → $DEST_PKG/"

if [[ ! -f "$CHART_ROOT/frontend/dist/index.html" ]]; then
  echo "==> frontend/dist missing — building ..."
  if [[ -f "$CHART_ROOT/frontend/package.json" ]] && command -v npm >/dev/null; then
    (cd "$CHART_ROOT/frontend" && npm install && npm run build)
  else
    echo "WARN: Cannot build — need Node.js: cd frontend && npm install && npm run build"
  fi
fi

if [[ -f "$CHART_ROOT/frontend/dist/index.html" ]]; then
  ASSET=$(grep -oE 'src="/assets/[^"]+' "$CHART_ROOT/frontend/dist/index.html" | head -1 | cut -d'"' -f2 || true)
  if [[ -n "$ASSET" && ! -f "$CHART_ROOT/frontend/dist$ASSET" ]]; then
    echo "WARN: missing $ASSET — run: cd frontend && npm run build"
  fi
fi

URLS=""
for f in "$CHART_ROOT"/opentrader/urls.py "$CHART_ROOT"/config/urls.py "$CHART_ROOT"/project/urls.py; do
  [[ -f "$f" ]] && URLS="$f" && break
done
[[ -z "$URLS" ]] && URLS=$(find "$CHART_ROOT" -path '*/.venv/*' -prune -o -name urls.py -print 2>/dev/null | head -1)

if [[ -z "$URLS" || ! -f "$URLS" ]]; then
  echo "ERROR: urls.py not found under $CHART_ROOT"
  exit 1
fi

PKG_NAME="$(basename "$(dirname "$URLS")")"
echo "==> Patching $URLS"

python3 - "$URLS" "$PKG_NAME" <<'PY'
import sys
from pathlib import Path

urls_path = Path(sys.argv[1])
pkg = sys.argv[2]
marker = "# opentrader-frontend-serve"
text = urls_path.read_text(encoding="utf-8")

if marker in text:
    print("  urls.py already patched")
else:
    block = f'''
{marker}
from django.urls import path, re_path
from {pkg}.frontend_serve import serve_index, serve_asset, serve_root_asset

urlpatterns = [
    path("", serve_index, name="opentrader-index"),
    re_path(r"^assets/(?P<path>.*)$", serve_asset),
    re_path(r"^(?P<filename>favicon\\.ico|manifest\\.json|robots\\.txt)$", serve_root_asset),
] + urlpatterns
'''
    urls_path.write_text(text.rstrip() + block + "\n", encoding="utf-8")
    print(f"  patched {urls_path}")
PY

SETTINGS=$(find "$CHART_ROOT" -path '*/.venv/*' -prune -o -path '*/settings.py' -print 2>/dev/null | head -1)
if [[ -f "${SETTINGS:-}" ]]; then
  python3 - "$SETTINGS" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
if "127.0.0.1" not in t and "ALLOWED_HOSTS" in t:
    t = re.sub(
        r"(ALLOWED_HOSTS\s*=\s*\[)([^\]]*)(\])",
        r"\1'*', '127.0.0.1', 'localhost'\3",
        t,
        count=1,
    )
    p.write_text(t, encoding="utf-8")
    print(f"  patched ALLOWED_HOSTS in {p}")
PY
fi

echo ""
echo "Restart:"
echo "  bash scripts/opentrader_go.sh $CHART_ROOT"
