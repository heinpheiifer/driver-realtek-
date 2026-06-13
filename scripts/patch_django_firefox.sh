#!/usr/bin/env bash
# Patch ~/OpenTrader Django so Firefox + Cursor both work (localhost / 127.0.0.1).
#
# Usage:
#   bash scripts/patch_django_firefox.sh
#   bash scripts/patch_django_firefox.sh /home/heinz/OpenTrader
#
set -euo pipefail

CHART_ROOT="${1:-/home/heinz/OpenTrader}"

_find_settings() {
  local manage
  for manage in \
    "$CHART_ROOT/manage.py" \
    "$CHART_ROOT/backend/manage.py" \
    "$CHART_ROOT/server/manage.py"; do
    [[ -f "$manage" ]] || continue
    local dir
    dir="$(dirname "$manage")"
    while IFS= read -r f; do
      [[ -f "$f" ]] && echo "$f" && return 0
    done < <(find "$dir" -path '*/settings.py' -not -path '*/.venv/*' 2>/dev/null | head -5)
  done
  find "$CHART_ROOT" -path '*/.venv/*' -prune -o -name 'settings.py' -print 2>/dev/null | head -1
}

SETTINGS="$(_find_settings || true)"
if [[ -z "$SETTINGS" || ! -f "$SETTINGS" ]]; then
  echo "WARN: settings.py not found under $CHART_ROOT (skipped Django patch)"
  exit 0
fi

echo "==> Patching Django settings: $SETTINGS"

python3 - "$SETTINGS" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
original = text

hosts = ["127.0.0.1", "localhost", "[::1]", "0.0.0.0", "*"]
cors = [
    "http://127.0.0.1:8010",
    "http://localhost:8010",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

def merge_list(name: str, values: list[str]) -> None:
    global text
    pat = rf"^{name}\s*=\s*\[(.*?)\]"
    m = re.search(pat, text, re.M | re.S)
    if m:
        inner = m.group(1)
        existing = re.findall(r"['\"]([^'\"]+)['\"]", inner)
        merged: list[str] = []
        for v in existing + values:
            if v not in merged:
                merged.append(v)
        repl = f"{name} = [{', '.join(repr(v) for v in merged)}]"
        text = text[: m.start()] + repl + text[m.end() :]
    else:
        block = f"\n{name} = [{', '.join(repr(v) for v in values)}]\n"
        text = text.rstrip() + block

merge_list("ALLOWED_HOSTS", hosts)

if "corsheaders" in text or "django-cors-headers" in text:
    merge_list("CORS_ALLOWED_ORIGINS", cors)
    if "corsheaders.middleware.CorsMiddleware" not in text:
        text = re.sub(
            r"(MIDDLEWARE\s*=\s*\[)",
            r"\1\n    'corsheaders.middleware.CorsMiddleware',",
            text,
            count=1,
        )
    if "corsheaders" not in text:
        text = re.sub(
            r"(INSTALLED_APPS\s*=\s*\[)",
            r"\1\n    'corsheaders',",
            text,
            count=1,
        )

# Serve Vite dist + chart_patch if not configured
if "chart_patch" not in text and "frontend/dist" not in text:
    extra = """

# OpenTrader patch: serve frontend/dist (Vite build + chart_patch)
from pathlib import Path as _Path
_OT_ROOT = _Path(__file__).resolve().parents[1]
_OT_DIST = _OT_ROOT / "frontend" / "dist"
if _OT_DIST.is_dir():
    STATICFILES_DIRS = list(globals().get("STATICFILES_DIRS", [])) + [str(_OT_DIST)]
"""
    text = text.rstrip() + extra

if text != original:
    path.write_text(text, encoding="utf-8")
    print(f"  updated {path}")
else:
    print(f"  no changes needed: {path}")
PY

echo "Done. Use http://127.0.0.1:8010 in Firefox (avoid localhost if IPv6 fails)."
