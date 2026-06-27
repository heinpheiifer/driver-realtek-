#!/usr/bin/env python3
"""
Full system audit for XAU-60 — run on your laptop:
  cd ~/tradenator-xau60/xau-60
  git pull origin cursor/fix-telegram-alerts-dc2c
  .venv/bin/python scripts/full-audit.py
"""
from __future__ import annotations

import re
import socket
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
WARN = 0
FAIL = 0


def ok(section: str, msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  ✅ [{section}] {msg}")


def warn(section: str, msg: str) -> None:
    global WARN
    WARN += 1
    print(f"  ⚠️  [{section}] {msg}")


def fail(section: str, msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  ❌ [{section}] {msg}")


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def pgrep(pattern: str) -> list[str]:
    try:
        out = subprocess.check_output(["pgrep", "-af", pattern], text=True, stderr=subprocess.DEVNULL)
        return [l.strip() for l in out.splitlines() if l.strip()]
    except subprocess.CalledProcessError:
        return []


def scan_log_errors(log_path: Path, hours: int = 24) -> dict:
    """Scan recent log for error patterns."""
    result = {"errors": [], "warnings": [], "asian_range_errors": 0, "smc_loaded": False, "trades": 0}
    if not log_path.exists():
        return result

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for line in lines:
        low = line.lower()
        if "smc scalper" in low and "loaded strategy" in low:
            result["smc_loaded"] = True
        if "trade opened" in low or "execute_signal" in low:
            result["trades"] += 1
        if "error calculating asian range" in low:
            result["asian_range_errors"] += 1
        if "| ERROR" in line or " ERROR " in line:
            # skip one-off connection retries if followed by success — still collect
            if "error calculating asian range" not in low:
                result["errors"].append(line.strip()[-200:])

    result["errors"] = result["errors"][-10:]
    return result


def audit_processes() -> None:
    print("\n── 1. Processes ──")
    bot = pgrep("python main.py")
    ui = pgrep("streamlit run ui/app.py")
    if bot:
        ok("proc", f"Live bot running ({len(bot)} instance(s))")
        for b in bot:
            print(f"      {b[:100]}")
    else:
        fail("proc", "Live bot NOT running → .venv/bin/python main.py")

    if ui:
        ok("proc", f"Dashboard running ({len(ui)} instance(s))")
    else:
        warn("proc", "Dashboard not running → ./scripts/start.sh")


def audit_network() -> None:
    print("\n── 2. Network / Bridge ──")
    if port_open(18812):
        ok("net", "Wine MT5 bridge port 18812 open")
    else:
        fail("net", "Bridge down → ./scripts/ensure-wine-bridge.sh")

    if port_open(8020):
        ok("net", "Dashboard port 8020 open")
    else:
        warn("net", "Dashboard port 8020 closed")


def audit_mt5() -> None:
    print("\n── 3. MT5 & Account ──")
    try:
        from core.account_manager import get_account_manager, AccountType

        mgr = get_account_manager()
        active = mgr.get_active_account()
        if not active:
            fail("mt5", "No active account — connect 517035 in UI")
            return

        live = active.account_type == AccountType.LIVE
        ok("mt5", f"Active account {active.login}@{active.server} ({'LIVE' if live else 'DEMO'})")

        if not mgr.connect_if_needed(active.id):
            fail("mt5", f"Connection failed: {mgr.get_connection_error(active.id)}")
            return

        info = mgr.get_account_info(active.id)
        if not info:
            fail("mt5", "Connected but no account info")
            return

        ok("mt5", f"Balance {info.balance:.2f} {info.currency} | Leverage 1:{info.leverage} | Free margin {info.margin_free:.2f}")

        if info.leverage <= 10 and info.balance < 500:
            warn("mt5", f"Low balance + 1:{info.leverage} leverage — use ETHUSD not XAUUSD")

        conn = mgr.get_connector(active.id)
        if conn:
            tick = conn.get_tick("ETHUSD")
            if tick:
                ok("mt5", f"ETHUSD tick bid={tick['bid']} ask={tick['ask']}")
            else:
                fail("mt5", "ETHUSD tick unavailable — check symbol in MT5 Market Watch")

            df = conn.get_ohlcv("ETHUSD", "M15", 20)
            if df is not None and len(df) >= 10:
                last = df.iloc[-1]["time"]
                ok("mt5", f"ETHUSD M15 data OK ({len(df)} bars, last bar {last})")
            else:
                fail("mt5", "ETHUSD M15 OHLCV failed")
    except Exception as e:
        fail("mt5", str(e))


def audit_strategies() -> None:
    print("\n── 4. Strategies ──")
    try:
        import yaml
        from core.strategy_loader import StrategyLoader

        sl = StrategyLoader()
        sl.load_all_strategies()
        enabled = sl.get_enabled_strategies()

        if not enabled:
            fail("strat", "No enabled strategies!")
            return

        ok("strat", f"{len(enabled)} enabled: {', '.join(enabled.keys())}")

        expect = {"SMC Scalper", "CRT TBS"}
        for name in expect:
            if name in enabled:
                s = enabled[name]
                syms = ", ".join(s.symbols)
                ok("strat", f"{name}: {s.timeframe} on {syms}")
            else:
                warn("strat", f"{name} not enabled")

        # Check yaml files directly
        strat_dir = ROOT / "config" / "strategies"
        for yf in sorted(strat_dir.glob("*.yaml")):
            with open(yf) as f:
                cfg = yaml.safe_load(f) or {}
            name = cfg.get("name", yf.stem)
            if not cfg.get("enabled", False):
                continue
            syms = cfg.get("symbols", [])
            if any("XAU" in str(s).upper() for s in syms):
                warn("strat", f"{name} enabled on {syms} — disable on 1:5 account")

        if "Trend Break Trauma" in enabled:
            warn("strat", "Trend Break Trauma enabled — trades XAUUSD, disable recommended")

        if "SMC Scalper" not in enabled:
            fail("strat", "SMC Scalper not enabled!")
    except Exception as e:
        fail("strat", str(e))


def audit_crt_engine() -> None:
    print("\n── 5. CRT TBS engine (datetime fix) ──")
    try:
        import numpy as np
        import pandas as pd
        import pytz
        import yaml
        from strategies.crt_tbs import CRTStrategy

        with open(ROOT / "config" / "strategies/crt_tbs.yaml") as f:
            cfg = yaml.safe_load(f)
        s = CRTStrategy()
        s.initialize(cfg)
        times = pd.date_range("2026-06-26 00:00", periods=100, freq="5min", tz="UTC")
        data = pd.DataFrame({
            "time": times,
            "open": 3000 + np.random.rand(100),
            "high": 3010 + np.random.rand(100),
            "low": 2990 + np.random.rand(100),
            "close": 3005 + np.random.rand(100),
            "volume": 100,
        })
        r = s._calculate_asian_range(data, datetime.now(pytz.UTC), "ETHUSD")
        if r and r.valid:
            ok("crt", f"Asian range calculation OK (high={r.high:.2f})")
        else:
            fail("crt", "Asian range calculation returned invalid")
    except Exception as e:
        fail("crt", f"Asian range error: {e}")


def audit_timezone() -> None:
    print("\n── 6. Timezone (NZ) ──")
    try:
        from utils.timezone_utils import (
            display_timezone_name,
            trading_clock_summary,
            utc_hour_range_label,
        )

        c = trading_clock_summary()
        ok("tz", f"{display_timezone_name()}: {c['local_time']} {c['local_tz']} | UTC {c['utc_time']}")
        ok("tz", f"Session: {c['session']} | CRT killzone: {c['crt_killzone'] or 'inactive (normal)'}")
        print(f"      London KZ: {utc_hour_range_label(7, 9)}")
        print(f"      NY KZ:     {utc_hour_range_label(13, 15)}")
    except Exception as e:
        fail("tz", str(e))


def audit_alerts() -> None:
    print("\n── 7. Alerts ──")
    try:
        import yaml
        from utils.alert_config import merge_alert_settings
        from alerts.telegram_bot import validate_telegram_credentials

        with open(ROOT / "config/settings.yaml") as f:
            y = yaml.safe_load(f) or {}
        alerts = merge_alert_settings(y)
        tg = alerts.get("telegram", {})
        if tg.get("enabled"):
            valid, err = validate_telegram_credentials(tg.get("token", ""), str(tg.get("chat_id", "")))
            if valid:
                ok("alert", "Telegram token + numeric chat ID OK")
            else:
                fail("alert", f"Telegram: {err}")
        else:
            warn("alert", "Telegram disabled")

        dc = alerts.get("discord", {})
        if dc.get("enabled") and dc.get("webhook_url"):
            ok("alert", "Discord webhook configured")
        elif dc.get("enabled"):
            fail("alert", "Discord enabled but no webhook URL")
    except Exception as e:
        warn("alert", str(e))


def audit_logs() -> None:
    print("\n── 8. Log analysis ──")
    log_path = ROOT / "logs" / "trading_bot.log"
    if not log_path.exists():
        warn("log", f"No log at {log_path}")
        return

    size = log_path.stat().st_size
    ok("log", f"Log file {size:,} bytes")

    scan = scan_log_errors(log_path)
    if scan["smc_loaded"]:
        ok("log", "SMC Scalper loaded at least once")
    else:
        warn("log", "No SMC load lines in log — restart main.py?")

    if scan["asian_range_errors"] > 0:
        fail("log", f"{scan['asian_range_errors']} Asian range errors — git pull & restart main.py")
    else:
        ok("log", "No Asian range datetime errors")

    if scan["trades"] > 0:
        ok("log", f"{scan['trades']} trade-related log entries")
    else:
        warn("log", "No trades logged yet (normal if no signals)")

    recent_errors = [e for e in scan["errors"] if e]
    if recent_errors:
        warn("log", f"{len(recent_errors)} recent ERROR lines:")
        for e in recent_errors[-5:]:
            print(f"      …{e[-120:]}")
    else:
        ok("log", "No ERROR lines in log (excluding fixed Asian range)")


def audit_env() -> None:
    print("\n── 9. Environment ──")
    env_path = ROOT / ".env"
    if not env_path.exists():
        fail("env", ".env missing")
        return
    ok("env", ".env exists")

    text = env_path.read_text(encoding="utf-8", errors="replace")

    wine = re.search(r"^MT5_WINE_ENABLED=(\S+)", text, re.M)
    if wine and wine.group(1).lower() in ("true", "1", "yes", "on"):
        ok("env", "MT5_WINE_ENABLED=true")
    else:
        warn("env", "MT5_WINE_ENABLED not true")

    sym = re.search(r"^DEFAULT_TRADING_SYMBOL=(\S+)", text, re.M)
    if sym and sym.group(1).upper() == "ETHUSD":
        ok("env", "DEFAULT_TRADING_SYMBOL=ETHUSD")
    else:
        warn("env", "DEFAULT_TRADING_SYMBOL not ETHUSD")

    tz = re.search(r"^APP_TIMEZONE=(\S+)", text, re.M)
    if tz and "Auckland" in tz.group(1):
        ok("env", f"APP_TIMEZONE={tz.group(1)}")
    else:
        warn("env", "APP_TIMEZONE not Pacific/Auckland — add for NZ clock")


def audit_positions() -> None:
    print("\n── 10. Open positions ──")
    try:
        from core.account_manager import get_account_manager

        mgr = get_account_manager()
        active = mgr.get_active_account()
        if not active or not mgr.connect_if_needed(active.id):
            warn("pos", "Skipped — MT5 not connected")
            return
        conn = mgr.get_connector(active.id)
        positions = conn.get_positions() if conn else []
        if not positions:
            ok("pos", "No open positions (flat)")
        else:
            ok("pos", f"{len(positions)} open position(s):")
            for p in positions:
                print(f"      {p.symbol} {p.type.name} {p.volume} lot @ {p.open_price} P/L={p.profit:.2f}")
    except Exception as e:
        warn("pos", str(e))


def main() -> int:
    print("=" * 60)
    print("  XAU-60 FULL SYSTEM AUDIT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    audit_processes()
    audit_network()
    audit_mt5()
    audit_strategies()
    audit_crt_engine()
    audit_timezone()
    audit_alerts()
    audit_logs()
    audit_env()
    audit_positions()

    print("\n" + "=" * 60)
    print(f"  RESULT: ✅ {PASS} passed  |  ⚠️  {WARN} warnings  |  ❌ {FAIL} failed")
    print("=" * 60)

    if FAIL == 0 and WARN == 0:
        print("\n  🟢 LIVE & ERROR-FREE — all checks passed.\n")
        return 0
    if FAIL == 0:
        print("\n  🟡 LIVE with warnings — review items above.\n")
        return 0
    print("\n  🔴 ISSUES FOUND — fix failed items above.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
