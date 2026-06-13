#!/usr/bin/env bash
# End-to-end test: patch + start Django + verify / and /assets/ return 200.
set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOCK="${1:-/tmp/OpenTrader-test}"
PORT="${PORT:-8019}"

bash "$ENGINE_ROOT/scripts/create_mock_opentrader.sh" "$MOCK"

echo "==> patch django frontend"
bash "$ENGINE_ROOT/scripts/patch_django_frontend.sh" "$MOCK"

export PATH="$HOME/.local/bin:$PATH"
cd "$MOCK"
rm -rf .venv
if command -v uv >/dev/null 2>&1; then
  uv venv .venv
  uv pip install -r requirements.txt
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi

PY="$MOCK/.venv/bin/python3"
[[ -x "$PY" ]] || PY="$MOCK/.venv/bin/python"
"$PY" manage.py migrate --noinput >/dev/null
"$PY" manage.py check

fuser -k "${PORT}/tcp" 2>/dev/null || true
"$PY" manage.py runserver "127.0.0.1:${PORT}" &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  curl -sf "http://127.0.0.1:${PORT}/api/health/" >/dev/null && break
  sleep 0.5
done

ROOT_CODE=$(curl -s -o /tmp/ot_root.html -w '%{http_code}' "http://127.0.0.1:${PORT}/")
JS_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/assets/index.js")
CSS_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/assets/index.css")
BODY=$(curl -s "http://127.0.0.1:${PORT}/assets/index.js")

echo "GET /           → HTTP $ROOT_CODE"
echo "GET /assets/index.js  → HTTP $JS_CODE"
echo "GET /assets/index.css → HTTP $CSS_CODE"
echo "JS body: $BODY"

if [[ "$ROOT_CODE" != "200" || "$JS_CODE" != "200" || "$CSS_CODE" != "200" ]]; then
  echo "FAIL: expected 200 for / and assets"
  exit 1
fi
if [[ "$BODY" != *"OpenTrader chart OK"* ]]; then
  echo "FAIL: JS content wrong"
  exit 1
fi

grep -q 'opentrader-frontend-serve' "$MOCK/opentrader/urls.py"
test -f "$MOCK/opentrader/frontend_serve.py"

echo "PASS: blank-page fix verified on mock OpenTrader (port $PORT)"
kill $PID 2>/dev/null || true
