#!/usr/bin/env python3
"""Send a test Telegram alert using .env / settings.yaml config."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    import yaml
    from alerts.service import AlertService
    from utils.alert_config import merge_alert_settings

    settings_path = ROOT / "config" / "settings.yaml"
    settings_yaml = {}
    if settings_path.exists():
        with open(settings_path, "r") as f:
            settings_yaml = yaml.safe_load(f) or {}

    alerts = merge_alert_settings(settings_yaml)
    tg = alerts.get("telegram", {})

    print("Telegram config:")
    print(f"  enabled: {tg.get('enabled')}")
    print(f"  token:   {'set' if tg.get('token') else 'MISSING'}")
    print(f"  chat_id: {tg.get('chat_id') or 'MISSING'}")
    print()

    if not tg.get("enabled"):
        print("Enable Telegram: set TELEGRAM_ENABLED=true in .env or toggle in UI → Settings → Alerts")
        return 1

    if not tg.get("token") or not tg.get("chat_id"):
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (Settings → Alerts → Save)")
        return 1

    svc = AlertService.from_config({"alerts": alerts})
    ok, err = svc.send_test_telegram()
    if ok:
        print("Test message sent — check your Telegram chat.")
        return 0

    print(f"Failed: {err}")
    print()
    print("Tips:")
    print("  1. Create a bot via @BotFather → /newbot → copy token")
    print("  2. Message your bot, then get chat ID from @userinfobot or @getidsbot")
    print("  3. Send /start to your bot before testing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
