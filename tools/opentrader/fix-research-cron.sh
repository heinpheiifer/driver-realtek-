#!/usr/bin/env bash
# Fix overlapping run_research_cycle.py instances (cron overlap + missing flock).
# Run on heinz-Predator:  bash tools/opentrader/fix-research-cron.sh
set -euo pipefail

OPENTRADER="${OPENTRADER_ROOT:-$HOME/OpenTrader}"
CRON_SCRIPT="${OPENTRADER}/scripts/run_research_cron.sh"
LOCK_DIR="${OPENTRADER}/.locks"
LOCK_FILE="${LOCK_DIR}/research-cron.lock"
FLOCK_MARKER="# flock guard (added by fix-research-cron.sh)"

log() { echo "  → $*"; }
ok()  { echo "  ✅ $*"; }
warn(){ echo "  ⚠️  $*"; }

backup_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  cp -a "$f" "${f}.bak.$(date +%Y%m%d-%H%M%S)"
  ok "Backed up $(basename "$f")"
}

patch_research_cron_script() {
  if [[ ! -f "$CRON_SCRIPT" ]]; then
    warn "Missing ${CRON_SCRIPT} — creating minimal cron wrapper"
    mkdir -p "$(dirname "$CRON_SCRIPT")"
    cat > "$CRON_SCRIPT" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
OT_ROOT="${OPENTRADER_ROOT:-$HOME/OpenTrader}"
cd "$OT_ROOT"
exec "$OT_ROOT/.venv/bin/python" "$OT_ROOT/scripts/run_research_cycle.py"
EOF
    chmod +x "$CRON_SCRIPT"
  fi

  backup_file "$CRON_SCRIPT"

  if grep -q "flock guard" "$CRON_SCRIPT" 2>/dev/null; then
    ok "run_research_cron.sh already has flock guard"
    return 0
  fi

  local tmp body
  tmp="$(mktemp)"
  body="$(mktemp)"

  # Preserve original script body (everything after shebang)
  tail -n +2 "$CRON_SCRIPT" > "$body"

  cat > "$tmp" <<EOF
#!/usr/bin/env bash
# ${FLOCK_MARKER}
set -euo pipefail

OPENTRADER="\${OPENTRADER_ROOT:-$HOME/OpenTrader}"
LOCK_DIR="\${OPENTRADER}/.locks"
LOCK_FILE="\${LOCK_DIR}/research-cron.lock"
mkdir -p "\${LOCK_DIR}"

exec 9>"\${LOCK_FILE}"
if ! flock -n 9; then
  echo "\$(date -Is) research cron skipped — another instance is running" >&2
  exit 0
fi

EOF
  cat "$body" >> "$tmp"
  rm -f "$body"
  mv "$tmp" "$CRON_SCRIPT"
  chmod +x "$CRON_SCRIPT"
  ok "Patched run_research_cron.sh with flock (single-instance lock)"
}

dedupe_crontab() {
  local current filtered tmp count_before count_after

  if ! crontab -l >/dev/null 2>&1; then
    warn "No user crontab — nothing to dedupe"
    return 0
  fi

  current="$(crontab -l 2>/dev/null || true)"
  count_before="$(echo "$current" | grep -c "run_research_cron" || true)"

  if [[ "$count_before" -le 1 ]]; then
    ok "Crontab has ${count_before} research cron line(s) — OK"
    echo "$current" | grep "run_research_cron" | sed 's/^/      /' || true
    return 0
  fi

  warn "Found ${count_before} duplicate research cron entries — consolidating to one"

  backup_file "${HOME}/.crontab.backup.opentrader"

  # Keep first research line; drop other run_research_cron lines
  filtered="$(echo "$current" | awk '
    /run_research_cron/ {
      if (seen++) next
    }
    { print }
  ')"

  tmp="$(mktemp)"
  echo "$filtered" > "$tmp"
  crontab "$tmp"
  rm -f "$tmp"

  count_after="$(crontab -l | grep -c "run_research_cron" || true)"
  ok "Crontab now has ${count_after} research cron line(s)"
  crontab -l | grep "run_research_cron" | sed 's/^/      /' || true
}

kill_extra_research_processes() {
  local pids count
  mapfile -t pids < <(pgrep -f "run_research_cycle.py" 2>/dev/null || true)
  count="${#pids[@]}"

  if [[ "$count" -le 1 ]]; then
    ok "At most one run_research_cycle.py running (${count})"
    return 0
  fi

  warn "${count} run_research_cycle.py processes — keeping oldest, stopping others"
  # Sort by start time via ps; keep first PID
  local keep stop
  keep="$(ps -o pid=,etimes= -p "${pids[@]}" 2>/dev/null | sort -k2 -rn | tail -1 | awk '{print $1}')"
  for stop in "${pids[@]}"; do
    if [[ "$stop" != "$keep" ]]; then
      kill "$stop" 2>/dev/null || true
      log "Stopped PID ${stop}"
    fi
  done
  ok "Kept PID ${keep}"
}

install_suggested_cron_if_missing() {
  if crontab -l 2>/dev/null | grep -q "run_research_cron"; then
    return 0
  fi

  warn "No research cron entry found — adding hourly run (optional)"
  local line="0 * * * * ${CRON_SCRIPT} >> ${OPENTRADER}/logs/research-cron.log 2>&1"
  (crontab -l 2>/dev/null; echo "$line") | crontab -
  ok "Added hourly research cron"
}

main() {
  echo "══════════════════════════════════════════════════"
  echo "  Fix research cron overlap — OpenTrader"
  echo "  OpenTrader: ${OPENTRADER}"
  echo "══════════════════════════════════════════════════"

  mkdir -p "${LOCK_DIR}" "${OPENTRADER}/logs" 2>/dev/null || true

  patch_research_cron_script
  dedupe_crontab
  kill_extra_research_processes
  install_suggested_cron_if_missing

  echo ""
  log "Current research processes:"
  pgrep -af "run_research_cycle" 2>/dev/null | sed 's/^/      /' || echo "      (none)"

  echo ""
  ok "Done. New cron runs will skip if previous cycle still running (flock)."
}

main "$@"
