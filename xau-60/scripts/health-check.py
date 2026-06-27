#!/usr/bin/env python3
"""Run a full health check on the XAU-60 bot (run on your laptop)."""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")


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


def main() -> int:
    print("\n=== XAU-60 Health Check ===\n")
    issues = 0

    # 1. Processes
    print("[1] Processes")
    bot = pgrep("python main.py")
    ui = pgrep("streamlit run ui/app.py")
    if bot:
        ok(f"Live bot running: {bot[0][:80]}")
    else:
        fail("Live bot NOT running — start: .venv/bin/python main.py")
        issues += 1
    if ui:
        ok(f"Dashboard running: {ui[0][:80]}")
    else:
        warn("Dashboard not running — start: ./scripts/start.sh")

    # 2. Bridge + UI port
    print("\n[2] Network")
    if port_open(18812):
        ok("Wine MT5 bridge on port 18812")
    else:
        fail("Bridge not reachable — run: ./scripts/ensure-wine-bridge.sh")
        issues += 1
    if port_open(8020):
        ok("Dashboard HTTP on port 8020")
    else:
        warn("Port 8020 not open (UI may be stopped)")

    # 3. MT5 connection
    print("\n[3] MT5 / Account")
    try:
        from core.account_manager import get_account_manager, ConnectionStatus

        mgr = get_account_manager()
        active = mgr.get_active_account()
        if not active:
            fail("No active account in UI — add/connect BlackBull account")
            issues += 1
        else:
            ok(f"Active account: {active.login}@{active.server}")
            if mgr.connect_if_needed(active.id):
                info = mgr.get_account_info(active.id)
                if info:
                    ok(f"Connected — balance {info.balance} {info.currency}, leverage 1:{info.leverage}")
                else:
                    fail("Connected but no account info")
                    issues += 1
            else:
                fail(f"MT5 connect failed: {mgr.get_connection_error(active.id)}")
                issues += 1
    except Exception as e:
        fail(f"MT5 check error: {e}")
        issues += 1

    # 4. Strategies
    print("\n[4] Strategies")
    try:
        from core.strategy_loader import StrategyLoader

        sl = StrategyLoader()
        sl.load_all_strategies()
        enabled = sl.get_enabled_strategies()
        ok(f"Loaded {len(enabled)} enabled: {', '.join(enabled.keys())}")
        for name, s in enabled.items():
            syms = ", ".join(s.symbols)
            if "XAU" in syms.upper():
                warn(f"{name} trades {syms} — may fail on low leverage account")
    except Exception as e:
        fail(f"Strategy load error: {e}")
        issues += 1

    # 5. Timezone
    print("\n[5] Timezone")
    try:
        from utils.timezone_utils import trading_clock_summary, display_timezone_name

        c = trading_clock_summary()
        ok(f"Display TZ: {display_timezone_name()} | Local: {c['local_time']} {c['local_tz']} | UTC: {c['utc_time']}")
        ok(f"Session: {c['session']} | CRT killzone: {c['crt_killzone'] or 'inactive'}")
    except Exception as e:
        fail(f"Timezone error: {e}")
        issues += 1

    # 6. Telegram
    print("\n[6] Alerts")
    try:
        import yaml
        from utils.alert_config import merge_alert_settings
        from alerts.telegram_bot import validate_telegram_credentials

        with open(ROOT / "config" / "settings.yaml") as f:
            y = yaml.safe_load(f) or {}
        tg = merge_alert_settings(y).get("telegram", {})
        if tg.get("enabled"):
            valid, err = validate_telegram_credentials(tg.get("token", ""), str(tg.get("chat_id", "")))
            if valid:
                ok("Telegram configured (token + numeric chat ID)")
            else:
                fail(f"Telegram: {err}")
                issues += 1
        else:
            warn("Telegram disabled")
    except Exception as e:
        warn(f"Alert check skipped: {e}")

    # 7. Log file
    print("\n[7] Logs")
    log_path = ROOT / "logs" / "trading_bot.log"
    if log_path.exists():
        ok(f"Log file exists ({log_path.stat().st_size} bytes)")
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]
        for line in lines:
            print(f"      {line[:100]}")
    else:
        warn(f"No log yet at {log_path} — restart main.py from project folder")

    print("\n=== Summary ===")
    if issues == 0:
        print("All critical checks passed.\n")
        return 0
    print(f"{issues} issue(s) need attention.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
