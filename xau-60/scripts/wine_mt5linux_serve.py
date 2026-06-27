#!/usr/bin/env python3
"""
mt5linux RPyC server entry for Wine Python.

Preloads numpy before the server starts so RPyC eval has `np` in namespace
(fixes: NameError: name 'np' is not defined on order_send/order_check).

Run inside Wine:
  wine python scripts/wine_mt5linux_serve.py --host 127.0.0.1 -p 18812
"""
from __future__ import annotations

import runpy
import sys

try:
    import numpy as np  # noqa: F401 — required for mt5linux RPyC on Wine
except ImportError:
    print(
        "ERROR: numpy not installed in Wine Python. Run:\n"
        "  wine python -m pip install numpy MetaTrader5 mt5linux",
        file=sys.stderr,
    )
    raise SystemExit(1)

runpy.run_module("mt5linux", run_name="__main__")
