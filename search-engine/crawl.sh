#!/usr/bin/env bash
# Run the web crawler (respects robots.txt, stores pages locally)
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

python3 crawler.py "$@"
