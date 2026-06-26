"""
Telegram Alert System.
Uses Telegram HTTP API directly (reliable from Streamlit / sync code).
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import requests
from loguru import logger

_PLACEHOLDER_TOKENS = frozenset({
    "",
    "your_telegram_bot_token",
    "your_bot_token",
    "changeme",
})
_PLACEHOLDER_CHAT_IDS = frozenset({
    "",
    "your_chat_id",
})


@dataclass
class TradeAlert:
    """Trade alert data."""
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    strategy: str
    timestamp: datetime


@dataclass
class CloseAlert:
    """Position close alert data."""
    symbol: str
    direction: str
    entry_price: float
    close_price: float
    profit: float
    pips: float
    duration: str
    strategy: str
    timestamp: datetime


def normalize_telegram_token(token: str) -> str:
    return str(token or "").strip()


def normalize_chat_id(chat_id: str) -> str:
    raw = str(chat_id or "").strip()
    # Allow numeric IDs and negative group IDs
    if re.fullmatch(r"-?\d+", raw):
        return raw
    return raw


def validate_telegram_credentials(token: str, chat_id: str) -> Tuple[bool, str]:
    """Return (valid, error_message)."""
    token = normalize_telegram_token(token)
    chat_id = normalize_chat_id(chat_id)

    if not token or token.lower() in _PLACEHOLDER_TOKENS:
        return False, "Bot token is missing or still the placeholder — paste your real token from @BotFather"
    if ":" not in token or len(token) < 20:
        return False, "Bot token looks invalid — it should look like 123456789:ABCdefGHI..."
    if not chat_id or chat_id.lower() in _PLACEHOLDER_CHAT_IDS:
        return False, "Chat ID is missing or still the placeholder — get your numeric ID from @userinfobot"
    if not re.fullmatch(r"-?\d+", chat_id):
        return False, f"Chat ID must be numeric (got {chat_id!r}) — use @userinfobot"
    return True, ""


class TelegramAlert:
    """
    Telegram notification system.

    Send alerts for:
    - Trade entries
    - Trade exits
    - Daily summaries
    - Error notifications
    """

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = normalize_telegram_token(token)
        self.chat_id = normalize_chat_id(chat_id)
        valid, _ = validate_telegram_credentials(self.token, self.chat_id)
        self.enabled = valid
        self._last_error = ""

        if self.enabled:
            logger.info("Telegram alerts initialized")
        elif token or chat_id:
            logger.warning("Telegram credentials incomplete or placeholder values")

    @property
    def last_error(self) -> str:
        return self._last_error

    def _api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, message: str, *, parse_mode: Optional[str] = None) -> Tuple[bool, str]:
        """
        Send a message to Telegram.

        Returns:
            (success, error_message)
        """
        if not self.enabled:
            return False, "Telegram not configured"

        payload = {"chat_id": self.chat_id, "text": message}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(self._api_url(), json=payload, timeout=20)
            data = response.json()
            if data.get("ok"):
                self._last_error = ""
                return True, ""

            desc = data.get("description", response.text)
            self._last_error = desc

            # Markdown parse failed — retry plain text
            if parse_mode and "parse" in desc.lower():
                return self.send_message(message, parse_mode=None)

            return False, desc
        except requests.RequestException as e:
            self._last_error = str(e)
            logger.error(f"Telegram HTTP error: {e}")
            return False, str(e)

    def send_message_sync(self, message: str, *, parse_mode: Optional[str] = "Markdown") -> Tuple[bool, str]:
        """Synchronous send (Streamlit-safe). Returns (success, error)."""
        return self.send_message(message, parse_mode=parse_mode)

    def send_trade_alert(self, alert: TradeAlert) -> bool:
        emoji = "🟢" if alert.direction == "BUY" else "🔴"
        sl_dist = abs(alert.entry_price - alert.stop_loss)
        rr = abs(alert.take_profit - alert.entry_price) / sl_dist if sl_dist else 0

        message = f"""
{emoji} *NEW TRADE ALERT*

📊 *Symbol:* `{alert.symbol}`
📈 *Direction:* {alert.direction}
💰 *Entry:* `{alert.entry_price:.5f}`
🛑 *Stop Loss:* `{alert.stop_loss:.5f}`
🎯 *Take Profit:* `{alert.take_profit:.5f}`
📏 *R:R Ratio:* `{rr:.2f}`
📦 *Lot Size:* `{alert.lot_size}`
🤖 *Strategy:* {alert.strategy}
⏰ *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok

    def send_close_alert(self, alert: CloseAlert) -> bool:
        emoji = "✅" if alert.profit > 0 else "❌"
        color = "🟢" if alert.profit > 0 else "🔴"

        message = f"""
{emoji} *TRADE CLOSED*

📊 *Symbol:* `{alert.symbol}`
📈 *Direction:* {alert.direction}
💰 *Entry:* `{alert.entry_price:.5f}`
💵 *Close:* `{alert.close_price:.5f}`
{color} *P&L:* `${alert.profit:.2f}` ({alert.pips:.1f} pips)
⏱ *Duration:* {alert.duration}
🤖 *Strategy:* {alert.strategy}
⏰ *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok

    def send_daily_summary(
        self,
        date: datetime,
        total_trades: int,
        winning_trades: int,
        total_profit: float,
        win_rate: float,
        best_trade: float,
        worst_trade: float,
    ) -> bool:
        emoji = "📈" if total_profit > 0 else "📉"
        message = f"""
{emoji} *DAILY SUMMARY - {date.strftime('%Y-%m-%d')}*

📊 *Total Trades:* {total_trades}
✅ *Winning Trades:* {winning_trades}
🎯 *Win Rate:* {win_rate:.1f}%
💰 *Total P&L:* `${total_profit:.2f}`
🏆 *Best Trade:* `${best_trade:.2f}`
💀 *Worst Trade:* `${worst_trade:.2f}`
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok

    def send_error_alert(self, error: str, context: str = "") -> bool:
        message = f"""
⚠️ *ERROR ALERT*

🔴 *Error:* {error}
📍 *Context:* {context if context else "N/A"}
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok

    def send_startup_message(self, strategies: list) -> bool:
        strategy_list = "\n".join([f"  • {s}" for s in strategies])
        message = f"""
🚀 *TRADING BOT STARTED*

📊 *Active Strategies:*
{strategy_list}

⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok

    def send_shutdown_message(self, reason: str = "Manual shutdown") -> bool:
        message = f"""
🛑 *TRADING BOT STOPPED*

📍 *Reason:* {reason}
⏰ *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        ok, _ = self.send_message_sync(message.strip())
        return ok
