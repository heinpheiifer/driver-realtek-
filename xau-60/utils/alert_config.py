"""
Merge Telegram/Discord settings from .env and config/settings.yaml.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _env_is_set(key: str) -> bool:
    value = os.getenv(key)
    return value is not None and value.strip() != ""


def merge_alert_settings(settings_yaml: Optional[dict] = None) -> Dict[str, Any]:
    """
    Build alert config from environment variables with YAML fallback.

    Env vars take precedence when explicitly set in .env.
    """
    from utils.config import load_config

    cfg = load_config()
    yaml_alerts = (settings_yaml or {}).get("alerts", {})
    tg_yaml = yaml_alerts.get("telegram", {}) or {}
    dc_yaml = yaml_alerts.get("discord", {}) or {}

    telegram_enabled = cfg.telegram.enabled
    if not _env_is_set("TELEGRAM_ENABLED"):
        telegram_enabled = bool(tg_yaml.get("enabled", telegram_enabled))

    discord_enabled = cfg.discord.enabled
    if not _env_is_set("DISCORD_ENABLED"):
        discord_enabled = bool(dc_yaml.get("enabled", discord_enabled))

    token = cfg.telegram.token or tg_yaml.get("token", "")
    chat_id = str(cfg.telegram.chat_id or tg_yaml.get("chat_id", ""))

    webhook = cfg.discord.webhook_url or dc_yaml.get("webhook_url", "")

    return {
        "telegram": {
            "enabled": telegram_enabled,
            "token": token,
            "chat_id": chat_id,
        },
        "discord": {
            "enabled": discord_enabled,
            "webhook_url": webhook,
        },
    }


def save_alert_env(alerts: dict) -> None:
    """Persist alert settings to .env (used by main.py and UI)."""
    from utils.env_file import update_env_file

    tg = alerts.get("telegram", {}) or {}
    dc = alerts.get("discord", {}) or {}

    update_env_file("TELEGRAM_ENABLED", "true" if tg.get("enabled") else "false", reload=True)
    if tg.get("token"):
        update_env_file("TELEGRAM_BOT_TOKEN", str(tg["token"]), reload=True)
    if tg.get("chat_id"):
        update_env_file("TELEGRAM_CHAT_ID", str(tg["chat_id"]), reload=True)

    update_env_file("DISCORD_ENABLED", "true" if dc.get("enabled") else "false", reload=True)
    if dc.get("webhook_url"):
        update_env_file("DISCORD_WEBHOOK_URL", str(dc["webhook_url"]), reload=True)
