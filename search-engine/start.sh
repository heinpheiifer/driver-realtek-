#!/usr/bin/env bash
# Start the private search web UI and API
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

python3 -c "from db import init_db; init_db()"
echo "Private Search running at http://127.0.0.1:8787"
exec python3 api.py
