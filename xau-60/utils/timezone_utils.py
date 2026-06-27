"""
Timezone utilities — trading logic uses UTC; UI uses local display timezone (NZ default).
"""
from __future__ import annotations

import os
from datetime import datetime, time
from typing import Optional

import pytz

TRADING_TZ = pytz.UTC
DEFAULT_DISPLAY_TZ = "Pacific/Auckland"


def display_timezone_name() -> str:
    return os.getenv("APP_TIMEZONE", DEFAULT_DISPLAY_TZ).strip() or DEFAULT_DISPLAY_TZ


def get_display_tz():
    """Local timezone for UI labels (default: New Zealand)."""
    try:
        return pytz.timezone(display_timezone_name())
    except pytz.UnknownTimeZoneError:
        return pytz.timezone(DEFAULT_DISPLAY_TZ)


def now_utc() -> datetime:
    return datetime.now(TRADING_TZ)


def now_local() -> datetime:
    return datetime.now(get_display_tz())


def utc_to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = TRADING_TZ.localize(dt)
    return dt.astimezone(get_display_tz())


def format_local(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    return utc_to_local(dt).strftime(fmt)


def format_dual_time(dt: Optional[datetime] = None) -> str:
    """e.g. '2026-06-26 20:15 NZDT (UTC 07:15)'."""
    dt = dt or now_utc()
    if dt.tzinfo is None:
        dt = TRADING_TZ.localize(dt)
    local = dt.astimezone(get_display_tz())
    return f"{local.strftime('%Y-%m-%d %H:%M')} {local.tzname()} (UTC {dt.strftime('%H:%M')})"


def utc_hour_range_label(start_h: int, end_h: int) -> str:
    """Show UTC session window with local NZ equivalent."""
    today = now_utc().date()
    start_utc = TRADING_TZ.localize(datetime.combine(today, time(start_h, 0)))
    end_utc = TRADING_TZ.localize(datetime.combine(today, time(end_h, 0)))
    start_local = utc_to_local(start_utc)
    end_local = utc_to_local(end_utc)
    tz = start_local.tzname()
    return (
        f"{start_h:02d}:00–{end_h:02d}:00 UTC "
        f"({start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')} {tz})"
    )


def get_market_session(utc_dt: Optional[datetime] = None) -> str:
    """Current forex session name from UTC hour."""
    dt = utc_dt or now_utc()
    if dt.tzinfo is None:
        dt = TRADING_TZ.localize(dt)
    hour = dt.astimezone(TRADING_TZ).hour
    if 0 <= hour < 7:
        return "Asian"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 17:
        return "London / New York overlap"
    if 17 <= hour < 22:
        return "New York"
    return "Asian (late)"


def get_crt_killzone(utc_dt: Optional[datetime] = None) -> Optional[str]:
    """Active CRT TBS killzone from default UTC hours, or None."""
    dt = utc_dt or now_utc()
    if dt.tzinfo is None:
        dt = TRADING_TZ.localize(dt)
    t = dt.astimezone(TRADING_TZ).time()
    if time(7, 0) <= t < time(9, 0):
        return "London killzone (07–09 UTC)"
    if time(13, 0) <= t < time(15, 0):
        return "New York killzone (13–15 UTC)"
    return None


def trading_clock_summary() -> dict:
    """Dashboard payload: local time, UTC, session, CRT killzone."""
    utc = now_utc()
    local = utc_to_local(utc)
    kz = get_crt_killzone(utc)
    return {
        "local_time": local.strftime("%H:%M:%S"),
        "local_tz": local.tzname() or display_timezone_name(),
        "local_date": local.strftime("%A %d %b %Y"),
        "utc_time": utc.strftime("%H:%M UTC"),
        "session": get_market_session(utc),
        "crt_killzone": kz,
        "crt_killzone_active": kz is not None,
        "dual": format_dual_time(utc),
    }
