#!/usr/bin/env python3
"""
Find your Telegram Chat ID using your bot token.

How to use:
  1. Create a bot with @BotFather and copy the token into .env (or pass --token)
  2. Open Telegram, find YOUR bot, send it any message (e.g. /start)
  3. Run:  .venv/bin/python scripts/get-telegram-chat-id.py

The script reads recent messages sent TO your bot and prints the numeric chat ID.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fetch_chat_ids(token: str) -> list[dict]:
    import requests

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url, timeout=20)
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(data.get("description", response.text))

    seen: set[int] = set()
    chats: list[dict] = []

    for update in data.get("result", []):
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None or chat_id in seen:
            continue
        seen.add(chat_id)
        chats.append({
            "id": chat_id,
            "type": chat.get("type", "?"),
            "title": chat.get("title") or chat.get("first_name") or chat.get("username") or "?",
            "username": chat.get("username"),
        })

    return chats


def main() -> int:
    parser = argparse.ArgumentParser(description="Find Telegram chat ID from bot messages")
    parser.add_argument("--token", help="Bot token (default: from .env / settings)")
    args = parser.parse_args()

    token = args.token
    if not token:
        import yaml
        from utils.alert_config import merge_alert_settings

        settings_path = ROOT / "config" / "settings.yaml"
        settings_yaml = {}
        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings_yaml = yaml.safe_load(f) or {}
        token = merge_alert_settings(settings_yaml).get("telegram", {}).get("token", "")

    token = str(token or "").strip()
    _invalid = (
        not token
        or token == "your_telegram_bot_token"
        or "paste" in token.lower()
        or "your_token" in token.lower()
        or ":" not in token
        or len(token) < 20
    )
    if _invalid:
        print("No valid bot token found.")
        print()
        print("You must paste your REAL token from @BotFather, for example:")
        print('  .venv/bin/python scripts/get-telegram-chat-id.py --token "7123456789:AAHabc123..."')
        print()
        print("Get it: Telegram → @BotFather → /mybots → @Hein123bot → API Token")
        return 1

    print("Looking for messages sent to your bot...")
    print("(If nothing shows up, open Telegram → your bot → send /start → run this again)\n")

    try:
        chats = fetch_chat_ids(token)
    except Exception as e:
        print(f"Error: {e}")
        if "Unauthorized" in str(e):
            print("→ Token is wrong. Copy a fresh one from @BotFather.")
        return 1

    if not chats:
        print("No messages found yet.\n")
        print("Do this:")
        print("  1. Open Telegram on your phone or desktop")
        print("  2. Search for the bot you created with @BotFather")
        print("  3. Tap START (or send /start)")
        print("  4. Run this script again")
        print()
        print("Your Chat ID is the number shown here — NOT the bot name (e.g. not 'Qwen Agent').")
        return 1

    print("Found chat(s):\n")
    for chat in chats:
        label = chat["title"]
        if chat.get("username"):
            label += f" (@{chat['username']})"
        print(f"  Chat ID: {chat['id']}")
        print(f"  Name:    {label}")
        print(f"  Type:    {chat['type']}")
        print()

    if len(chats) == 1:
        print(f"→ Use this in Settings → Alerts → Chat ID:  {chats[0]['id']}")
    else:
        print("→ For personal alerts, use the chat with type 'private' (your own account).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
