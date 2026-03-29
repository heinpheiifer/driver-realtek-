#!/bin/sh
set -eu

APP_DIR="/data/stormwatch"
SRC_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

echo "[install] creating ${APP_DIR}"
mkdir -p "${APP_DIR}"

echo "[install] copying files"
cp "${SRC_DIR}/stormwatchd.py" "${APP_DIR}/stormwatchd.py"
cp "${SRC_DIR}/start-stormwatch.sh" "${APP_DIR}/start-stormwatch.sh"
cp "${SRC_DIR}/requirements.txt" "${APP_DIR}/requirements.txt"
if [ ! -f "${APP_DIR}/config.json" ]; then
  cp "${SRC_DIR}/config.example.json" "${APP_DIR}/config.json"
fi
chmod +x "${APP_DIR}/stormwatchd.py" "${APP_DIR}/start-stormwatch.sh"

echo "[install] installing Python dependencies"
/usr/bin/env python3 -m pip install -r "${APP_DIR}/requirements.txt"

LOCALSERVICE="/data/rc.local.d/stormwatch.sh"
echo "[install] writing autostart script ${LOCALSERVICE}"
mkdir -p /data/rc.local.d
cat > "${LOCALSERVICE}" << 'EOF'
#!/bin/sh
APP_DIR="/data/stormwatch"
PIDFILE="/var/run/stormwatchd.pid"

if [ -f "${PIDFILE}" ] && kill -0 "$(cat "${PIDFILE}")" >/dev/null 2>&1; then
  exit 0
fi

if [ -x "${APP_DIR}/start-stormwatch.sh" ]; then
  nohup "${APP_DIR}/start-stormwatch.sh" >/dev/null 2>&1 &
  echo $! > "${PIDFILE}"
fi
EOF
chmod +x "${LOCALSERVICE}"

echo "[install] validating config syntax"
/usr/bin/env python3 - << 'PY'
import json
from pathlib import Path
path = Path("/data/stormwatch/config.json")
json.loads(path.read_text(encoding="utf-8"))
print("config.json: OK")
PY

echo "[install] done"
echo "[install] edit config: ${APP_DIR}/config.json"
echo "[install] start now: ${APP_DIR}/start-stormwatch.sh"
