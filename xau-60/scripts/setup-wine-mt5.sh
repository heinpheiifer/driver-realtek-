#!/usr/bin/env bash
# One-shot setup for MT5 in Wine + mt5linux on a single Linux laptop.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> XAU-60 Wine MT5 setup"
echo "    Project: $ROOT"
echo ""

# --- Linux venv ---
if [[ ! -d .venv ]]; then
  echo "==> Creating Python venv..."
  python3 -m venv .venv
fi

echo "==> Installing Linux Python deps (mt5linux)..."
.venv/bin/pip install -U pip wheel -q
.venv/bin/pip install -r requirements.txt -q
.venv/bin/pip install mt5linux -q

# --- .env ---
ensure_env() {
  local key="$1"
  local value="$2"
  if [[ "$value" == *" "* ]]; then
    value="\"${value}\""
  fi
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> Enabling MT5 Wine mode in .env..."
ensure_env "MT5_WINE_ENABLED" "true"
ensure_env "MT5_WINE_HOST" "localhost"
ensure_env "MT5_WINE_PORT" "18812"
ensure_env "MT5_WINE_TIMEOUT" "300"
ensure_env "MT5_WINE_USE_TERMINAL_SESSION" "true"

# tmux keeps Wine bridge running in background (required — Wine Python breaks with nohup)
if ! command -v tmux >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
  echo "==> Installing tmux (needed for Wine MT5 bridge)..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tmux 2>/dev/null || true
fi

# --- Install embeddable Windows Python in Wine if missing ---
install_wine_python_embedded() {
  local prefix="${WINEPREFIX:-$HOME/.wine}"
  local dest="$prefix/drive_c/Python312"
  local py="$dest/python.exe"

  if [[ -f "$py" ]]; then
    return 0
  fi

  echo "==> Installing embeddable Python 3.12 inside Wine..."
  export WINEARCH="${WINEARCH:-win64}"
  export WINEPREFIX="$prefix"
  if [[ ! -d "$prefix" ]]; then
    wineboot --init >/dev/null 2>&1 || true
  fi

  local tmp="/tmp/xau60-py-embed"
  mkdir -p "$tmp"
  curl -fsSL -o "$tmp/py-embed.zip" \
    "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
  mkdir -p "$dest"
  unzip -qo "$tmp/py-embed.zip" -d "$dest"
  chmod +x "$py"
  # Enable pip/site-packages
  if grep -q "^#import site" "$dest/python312._pth" 2>/dev/null; then
    sed -i 's/^#import site/import site/' "$dest/python312._pth"
  elif ! grep -q "^import site" "$dest/python312._pth" 2>/dev/null; then
    echo "import site" >> "$dest/python312._pth"
  fi
  curl -fsSL -o "$dest/get-pip.py" https://bootstrap.pypa.io/get-pip.py
  wine "$py" "$dest/get-pip.py" -q
  echo "==> Wine Python installed at $dest"
}

# --- Wine ---
if ! command -v wine >/dev/null 2>&1; then
  echo ""
  echo "Wine is not installed."
  if command -v apt-get >/dev/null 2>&1; then
    echo "==> Installing Wine (may take a few minutes)..."
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y wine64 wine32 2>/dev/null \
      || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y wine 2>/dev/null \
      || true
  fi
fi

if ! command -v wine >/dev/null 2>&1; then
  echo ""
  echo "WARNING: Could not install Wine automatically."
  echo "  On Mint: sudo apt install wine64"
  echo "  Then re-run: ./scripts/setup-wine-mt5.sh"
  WINE_OK=false
else
  WINE_OK=true
  echo "==> Wine: $(wine --version 2>/dev/null || echo 'installed')"
fi

# --- Find Wine Python ---
find_wine_python() {
  local candidates=()
  if [[ -n "${MT5_WINE_PYTHON:-}" ]] && [[ "$MT5_WINE_PYTHON" != "wine python" ]]; then
    echo "$MT5_WINE_PYTHON"
    return
  fi

  if wine python --version >/dev/null 2>&1; then
    echo "wine python"
    return
  fi

  while IFS= read -r py; do
    candidates+=("$py")
  done < <(find "${WINEPREFIX:-$HOME/.wine}" -name python.exe 2>/dev/null | head -5)

  # Common embeddable Python path
  if [[ -f "${WINEPREFIX:-$HOME/.wine}/drive_c/Python312/python.exe" ]]; then
    echo "wine ${WINEPREFIX:-$HOME/.wine}/drive_c/Python312/python.exe"
    return
  fi

  if ((${#candidates[@]} > 0)); then
    echo "wine ${candidates[0]}"
    return
  fi

  echo ""
}

WINE_PY=""
if [[ "$WINE_OK" == true ]]; then
  WINE_PY="$(find_wine_python || true)"
  if [[ -z "$WINE_PY" ]]; then
    install_wine_python_embedded && WINE_PY="$(find_wine_python || true)"
  fi
fi

if [[ -n "$WINE_PY" ]]; then
  echo "==> Wine Python: $WINE_PY"
  ensure_env "MT5_WINE_PYTHON" "$WINE_PY"
  echo "==> Installing MetaTrader5 + mt5linux in Wine Python..."
  $WINE_PY -m pip install --upgrade pip -q 2>/dev/null || true
  $WINE_PY -m pip install MetaTrader5 mt5linux -q
  WINE_PY_OK=true
else
  WINE_PY_OK=false
  echo ""
  echo "WARNING: Windows Python not found inside Wine."
  echo "  1. Download Python for Windows: https://www.python.org/downloads/windows/"
  echo "  2. Install it inside Wine (wine ~/Downloads/python-*-amd64.exe)"
  echo "  3. Re-run this script"
fi

chmod +x scripts/start-wine-mt5linux.sh scripts/stop-wine-mt5linux.sh \
  scripts/check-wine-mt5.py scripts/setup-wine-mt5.sh \
  scripts/ensure-wine-bridge.sh scripts/debug-wine-mt5.sh \
  scripts/start-wine-and-bridge.sh 2>/dev/null || true

echo ""
echo "==> Setup summary"
echo "    MT5_WINE_ENABLED=true in .env"
echo "    Linux mt5linux: installed"
echo "    Wine:           $([ "$WINE_OK" = true ] && echo OK || echo MISSING)"
echo "    Wine Python:    $([ "$WINE_PY_OK" = true ] && echo OK || echo MISSING — install Python in Wine)"
echo ""
echo ""
echo "One-command setup + debug:"
echo "  ./scripts/setup-wine-mt5.sh"
  echo "  ./scripts/find-wine-mt5-path.sh   # if MT5 path not found"
  echo "  ./scripts/debug-wine-mt5.sh"
echo ""
echo "Daily start (after MT5 open in Wine):"
echo "  ./scripts/start.sh          # auto-starts bridge via tmux + dashboard"
echo "  # OR manually:"
echo "  ./scripts/start-wine-mt5linux.sh   # terminal 1 — keep open"
echo "  ./scripts/start.sh                 # terminal 2"
echo ""

# --- Quick test ---
echo "==> Running check-wine-mt5.py..."
if .venv/bin/python scripts/check-wine-mt5.py; then
  echo ""
  echo "==> Wine MT5 bridge is working."
  exit 0
fi

echo ""
echo "Setup files are ready. Start MT5 in Wine + start-wine-mt5linux.sh, then re-run:"
echo "  .venv/bin/python scripts/check-wine-mt5.py"
exit 0
