#!/usr/bin/env bash
# Full Wine MT5 / mt5linux diagnostic (run from xau-60 folder).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}OK${NC}   $*"; }
fail() { echo -e "${RED}FAIL${NC} $*"; }
warn() { echo -e "${YELLOW}WARN${NC} $*"; }

echo "========================================"
echo " XAU-60 Wine MT5 Debug"
echo " $(date)"
echo "========================================"
echo ""

# --- .env ---
echo "--- .env (MT5_WINE_*) ---"
if [[ -f .env ]]; then
  grep -E '^MT5_WINE_' .env || warn "No MT5_WINE_* vars in .env"
else
  fail ".env missing — run ./scripts/setup-wine-mt5.sh"
fi
echo ""

# --- Linux Python ---
echo "--- Linux Python ---"
if [[ -x .venv/bin/python ]]; then
  ok "venv: $(.venv/bin/python --version 2>&1)"
  if .venv/bin/python -c "import mt5linux" 2>/dev/null; then
    ok "mt5linux installed (Linux)"
  else
    fail "mt5linux missing — pip install mt5linux"
  fi
else
  fail ".venv missing — ./scripts/install-linux.sh"
fi
echo ""

# --- Wine ---
echo "--- Wine ---"
if command -v wine >/dev/null; then
  ok "$(wine --version 2>/dev/null)"
else
  fail "wine not installed — sudo apt install wine64"
fi
echo ""

# --- Wine Python ---
echo "--- Wine Python ---"
WINE_PY=""
if [[ -f .env ]]; then
  line="$(grep -m1 '^MT5_WINE_PYTHON=' .env || true)"
  if [[ -n "$line" ]]; then
    WINE_PY="${line#MT5_WINE_PYTHON=}"
    WINE_PY="${WINE_PY%\"}"
    WINE_PY="${WINE_PY#\"}"
    WINE_PY="${WINE_PY//\$HOME/$HOME}"
  fi
fi
if [[ -z "$WINE_PY" ]] || [[ "$WINE_PY" == "wine python" ]]; then
  PYEXE="$(find "${WINEPREFIX:-$HOME/.wine}" -name python.exe 2>/dev/null | head -1)"
  if [[ -n "$PYEXE" ]]; then
    WINE_PY="wine $PYEXE"
    warn "MT5_WINE_PYTHON not set — using $PYEXE"
  fi
fi

if [[ -n "$WINE_PY" ]]; then
  echo "  Command: $WINE_PY"
  read -ra WINE_CMD <<< "$WINE_PY"
  if "${WINE_CMD[@]}" --version >/dev/null 2>&1; then
    ok "Wine Python responds"
  else
    fail "Wine Python does not run — check MT5_WINE_PYTHON in .env"
  fi
  if "${WINE_CMD[@]}" -m pip show MetaTrader5 mt5linux >/dev/null 2>&1; then
    ok "MetaTrader5 + mt5linux in Wine Python"
  else
    fail "Missing Wine packages — $WINE_PY -m pip install MetaTrader5 mt5linux"
  fi
else
  fail "No Wine Python found — run ./scripts/setup-wine-mt5.sh"
fi
echo ""

# --- MT5 terminal ---
echo "--- MT5 terminal (Wine) ---"
if [[ -x .venv/bin/python ]]; then
  TERM_PATH="$(.venv/bin/python -c "from utils.mt5_paths import find_wine_mt5_terminal; print(find_wine_mt5_terminal() or '')")"
  if [[ -n "$TERM_PATH" ]]; then
    ok "Found: $TERM_PATH"
  else
    warn "terminal64.exe not found under ~/.wine — set MT5_WINE_PATH in .env"
  fi
fi
echo ""

# --- Port 18812 ---
PORT="${MT5_WINE_PORT:-18812}"
echo "--- Bridge port $PORT ---"
if (echo >/dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; then
  ok "Port $PORT is open"
else
  fail "Port $PORT closed — bridge not running"
fi

if [[ -f logs/wine-bridge.log ]]; then
  echo "  Last log lines:"
  tail -5 logs/wine-bridge.log | sed 's/^/    /'
fi
if [[ -f logs/wine-bridge.pid ]]; then
  pid="$(cat logs/wine-bridge.pid 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    ok "Background bridge pid $pid"
  else
    warn "Stale pid file (process dead)"
  fi
fi
echo ""

# --- Python checks ---
echo "--- Python connectivity ---"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python scripts/check-wine-mt5.py || true
  echo ""
  .venv/bin/python scripts/connect-account.py || true
fi
echo ""

echo "========================================"
echo " Fix checklist"
echo "========================================"
echo " 1. Open MT5 in Wine → login 517035 @ BlackBullMarkets-Live"
echo " 2. Enable Algo Trading (green) in MT5 toolbar"
echo " 3. Terminal A: ./scripts/start-wine-mt5linux.sh   (keep open)"
echo " 4. Terminal B: ./scripts/start.sh"
echo ""
echo " If bridge fails in background, use foreground start (step 3)."
echo " Debug log: tail -f logs/wine-bridge.log"
echo ""
