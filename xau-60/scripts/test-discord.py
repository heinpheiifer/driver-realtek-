#!/usr/bin/env python3
"""Send a test Discord alert using .env / settings.yaml config."""
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
    dc = alerts.get("discord", {})

    print("Discord config:")
    print(f"  enabled: {dc.get('enabled')}")
    print(f"  webhook: {'set' if dc.get('webhook_url') else 'MISSING'}")
    print()

    if not dc.get("enabled"):
        print("Enable Discord: set DISCORD_ENABLED=true in .env or toggle in UI → Settings → Alerts")
        return 1

    svc = AlertService.from_config({"alerts": alerts})
    ok, err = svc.send_test_discord()
    if ok:
        print("Test message sent — check your Discord channel.")
        return 0

    print(f"Failed: {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
