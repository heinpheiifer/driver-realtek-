#!/bin/sh
set -e

SCRIPT_DIR="/data/stormwatch"
LOG_FILE="/data/stormwatch/stormwatch.log"

if [ ! -d "$SCRIPT_DIR" ]; then
  echo "Missing $SCRIPT_DIR. Run install.sh first."
  exit 1
fi

cd "$SCRIPT_DIR"
exec /usr/bin/env python3 stormwatchd.py --config config.json >> "$LOG_FILE" 2>&1
