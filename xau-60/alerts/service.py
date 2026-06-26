"""
Alert service — wires Telegram/Discord to trade events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from alerts.discord_bot import CloseAlert, DiscordAlert, TradeAlert
from alerts.telegram_bot import TelegramAlert


class AlertService:
    """Send trade and bot lifecycle alerts via Telegram and/or Discord."""

    def __init__(
        self,
        telegram: Optional[TelegramAlert] = None,
        discord: Optional[DiscordAlert] = None,
    ):
        self.telegram = telegram
        self.discord = discord

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "AlertService":
        alerts = config.get("alerts", {}) or {}
        tg_cfg = alerts.get("telegram", {}) or {}
        dc_cfg = alerts.get("discord", {}) or {}

        telegram = None
        discord = None

        if tg_cfg.get("enabled") and tg_cfg.get("token") and tg_cfg.get("chat_id"):
            telegram = TelegramAlert(
                token=str(tg_cfg["token"]),
                chat_id=str(tg_cfg["chat_id"]),
            )
            if not telegram.enabled:
                logger.warning("Telegram enabled in config but failed to initialize")

        if dc_cfg.get("enabled") and dc_cfg.get("webhook_url"):
            discord = DiscordAlert(webhook_url=str(dc_cfg["webhook_url"]))

        service = cls(telegram=telegram, discord=discord)
        if service.is_active:
            logger.info("Alert service initialized")
        else:
            logger.info("Alert service inactive (no channels configured)")
        return service

    @property
    def is_active(self) -> bool:
        return bool(
            (self.telegram and self.telegram.enabled)
            or (self.discord and self.discord.enabled)
        )

    def send_test(self) -> tuple[bool, str]:
        """Send a test message. Returns (success, error_message)."""
        message = "✅ *XAU-60 test alert* — Telegram is working!"
        if not self.telegram or not self.telegram.enabled:
            return False, "Telegram not configured (enable + token + chat ID)"

        if self.telegram.send_message_sync(message):
            return True, ""
        return False, "Send failed — check token, chat ID, and that you /start the bot"

    def send_startup(self, strategies: List[str]) -> None:
        if self.telegram and self.telegram.enabled:
            self.telegram.send_startup_message(strategies)
        if self.discord and self.discord.enabled:
            self.discord.send_startup_message(strategies)

    def send_shutdown(self, reason: str = "Manual shutdown") -> None:
        if self.telegram and self.telegram.enabled:
            self.telegram.send_shutdown_message(reason)
        if self.discord and self.discord.enabled:
            self.discord.send_shutdown_message(reason)

    def send_error(self, error: str, context: str = "") -> None:
        if self.telegram and self.telegram.enabled:
            self.telegram.send_error_alert(error, context)
        if self.discord and self.discord.enabled:
            self.discord.send_error_alert(error, context)

    def on_trade_open(self, record) -> None:
        direction = record.signal.name if hasattr(record.signal, "name") else str(record.signal)
        alert = TradeAlert(
            symbol=record.symbol,
            direction=direction,
            entry_price=record.entry_price,
            stop_loss=record.stop_loss,
            take_profit=record.take_profit,
            lot_size=record.lot_size,
            strategy=record.strategy,
            timestamp=record.open_time or datetime.now(),
        )
        if self.telegram and self.telegram.enabled:
            self.telegram.send_trade_alert(alert)
        if self.discord and self.discord.enabled:
            self.discord.send_trade_alert(alert)

    def on_trade_close(self, record) -> None:
        if record.close_price is None or record.profit is None:
            return

        direction = record.signal.name if hasattr(record.signal, "name") else str(record.signal)
        duration = "N/A"
        if record.open_time and record.close_time:
            delta = record.close_time - record.open_time
            hours, rem = divmod(int(delta.total_seconds()), 3600)
            minutes = rem // 60
            duration = f"{hours}h {minutes}m"

        alert = CloseAlert(
            symbol=record.symbol,
            direction=direction,
            entry_price=record.entry_price,
            close_price=record.close_price,
            profit=record.profit,
            pips=record.pips or 0.0,
            duration=duration,
            strategy=record.strategy,
            timestamp=record.close_time or datetime.now(),
        )
        if self.telegram and self.telegram.enabled:
            self.telegram.send_close_alert(alert)
        if self.discord and self.discord.enabled:
            self.discord.send_close_alert(alert)

    def register_with_executor(self, executor) -> None:
        executor.register_trade_open_callback(self.on_trade_open)
        executor.register_trade_close_callback(self.on_trade_close)
