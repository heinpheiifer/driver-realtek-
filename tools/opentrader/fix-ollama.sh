#!/usr/bin/env bash
# Fix Ollama CLI not in PATH + ensure API reachable for Tradenator 2.0 / OpenTrader.
# Run on heinz-Predator:  bash tools/opentrader/fix-ollama.sh
set -euo pipefail

OPENTRADER="${OPENTRADER_ROOT:-$HOME/OpenTrader}"
MARKER="# OpenTrader Ollama PATH (added by fix-ollama.sh)"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

log() { echo "  → $*"; }
ok()  { echo "  ✅ $*"; }
warn(){ echo "  ⚠️  $*"; }

find_ollama_bin() {
  local candidate
  for candidate in \
    "$(command -v ollama 2>/dev/null || true)" \
    "/usr/local/bin/ollama" \
    "/usr/bin/ollama" \
    "$HOME/.ollama/bin/ollama" \
    "/snap/bin/ollama"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

install_ollama_if_missing() {
  if find_ollama_bin >/dev/null 2>&1; then
    return 0
  fi
  warn "Ollama binary not found — installing via official script..."
  if ! command -v curl >/dev/null 2>&1; then
    echo "  ❌ curl required to install Ollama" >&2
    exit 1
  fi
  curl -fsSL https://ollama.com/install.sh | sh
}

add_path_to_profile() {
  local profile dir
  profile="${HOME}/.bashrc"
  [[ -f "${HOME}/.profile" ]] && profile="${HOME}/.profile"

  dir="$(dirname "$(find_ollama_bin)")"
  if grep -Fq "$MARKER" "$profile" 2>/dev/null; then
    ok "PATH block already in $profile"
    return 0
  fi

  {
    echo ""
    echo "$MARKER"
    echo "export PATH=\"$dir:/usr/local/bin:\$HOME/.ollama/bin:\$PATH\""
    echo "export OLLAMA_HOST=\"\${OLLAMA_HOST:-127.0.0.1:11434}\""
  } >> "$profile"
  ok "Added Ollama PATH to $profile"
}

write_opentrader_env() {
  local env_file="${OPENTRADER}/.env.ollama"
  local bin dir
  bin="$(find_ollama_bin)"
  dir="$(dirname "$bin")"

  cat > "$env_file" <<EOF
# Sourced by OpenTrader runners — do not commit secrets here
export PATH="${dir}:/usr/local/bin:${HOME}/.ollama/bin:\${PATH}"
export OLLAMA_HOST="${OLLAMA_HOST}"
EOF
  ok "Wrote ${env_file}"
}

patch_runner_scripts() {
  local script patched=0
  for script in \
    "${OPENTRADER}/scripts/ai_paper_runner.py" \
    "${OPENTRADER}/scripts/run_forward_paper.py"; do
    [[ -f "$script" ]] || continue
    if head -5 "$script" | grep -q ".env.ollama"; then
      continue
    fi
    # Only patch shell wrappers; skip pure Python unless there's a .sh launcher
    :
  done

  local sh_scripts=(
    "${OPENTRADER}/scripts/ai_paper_runner.sh"
    "${OPENTRADER}/scripts/setup_ai_paper_trading.sh"
    "${OPENTRADER}/scripts/system_watchdog.sh"
  )
  for script in "${sh_scripts[@]}"; do
    [[ -f "$script" ]] || continue
    if grep -q ".env.ollama" "$script"; then
      continue
    fi
    sed -i "2i# shellcheck disable=SC1091\n[ -f \"${OPENTRADER}/.env.ollama\" ] && . \"${OPENTRADER}/.env.ollama\"" "$script"
    ok "Patched $(basename "$script") to source .env.ollama"
    patched=1
  done

  # Create launcher wrapper for ai_paper if only .py exists
  local py_runner="${OPENTRADER}/scripts/ai_paper_runner.py"
  local sh_runner="${OPENTRADER}/scripts/run_ai_paper.sh"
  if [[ -f "$py_runner" && ! -f "$sh_runner" ]]; then
    cat > "$sh_runner" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
OT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$OT_ROOT/.env.ollama" ] && . "$OT_ROOT/.env.ollama"
exec "$OT_ROOT/.venv/bin/python" "$OT_ROOT/scripts/ai_paper_runner.py" "$@"
LAUNCHER
    chmod +x "$sh_runner"
    ok "Created scripts/run_ai_paper.sh wrapper (sources .env.ollama)"
    patched=1
  fi

  if [[ "$patched" -eq 0 ]]; then
    log "No shell runners to patch (ai_paper_runner.py uses HTTP — .env.ollama still helps manual CLI)"
  fi
}

ensure_ollama_service() {
  local bin
  bin="$(find_ollama_bin)"

  if pgrep -x ollama >/dev/null 2>&1 || pgrep -f "ollama serve" >/dev/null 2>&1; then
    ok "Ollama process already running"
    return 0
  fi

  if systemctl --user is-active ollama.service >/dev/null 2>&1; then
    ok "ollama.service active (user systemd)"
    return 0
  fi

  if systemctl is-active ollama >/dev/null 2>&1; then
    ok "ollama.service active (system)"
    return 0
  fi

  warn "Starting ollama serve in background..."
  nohup "$bin" serve >> "${OPENTRADER}/logs/ollama.log" 2>&1 &
  sleep 2
}

verify_api() {
  local host="${OLLAMA_HOST#http://}"
  host="${host#https://}"
  local url="http://${host}/api/tags"

  if curl -sf --max-time 5 "$url" >/dev/null; then
    ok "Ollama API reachable at ${host}"
    curl -sf --max-time 5 "$url" | head -c 400
    echo ""
    return 0
  fi

  warn "Ollama API not reachable at ${host}"
  warn "If ai_paper_runner works, set OLLAMA_HOST in ${OPENTRADER}/.env.ollama to your remote endpoint"
  return 1
}

main() {
  echo "══════════════════════════════════════════════════"
  echo "  Fix Ollama — Tradenator 2.0 / OpenTrader"
  echo "  OpenTrader: ${OPENTRADER}"
  echo "══════════════════════════════════════════════════"

  mkdir -p "${OPENTRADER}/logs" 2>/dev/null || true

  install_ollama_if_missing

  local bin
  bin="$(find_ollama_bin)"
  ok "Ollama binary: ${bin}"

  # Apply to current shell immediately
  export PATH="$(dirname "$bin"):/usr/local/bin:${HOME}/.ollama/bin:${PATH}"

  add_path_to_profile
  write_opentrader_env
  patch_runner_scripts
  ensure_ollama_service

  echo ""
  log "Verification:"
  "$bin" list 2>/dev/null || warn "ollama list failed — API may still work via HTTP"
  verify_api || true

  echo ""
  ok "Done. Open a new terminal or run:  source ~/.bashrc"
  echo "  Then test:  ollama list && curl -s ${OLLAMA_HOST}/api/tags | head"
}

main "$@"
