#!/usr/bin/env python3
"""
Storm Watch daemon for Victron Venus OS.

Improvements included:
- Multi-feed CAP failover + merge/dedupe
- Data staleness/fail-safe policies
- Severity-tiered reserve control with optional ramping
- Manual override with timeout
- VRM-friendly alarm/status topic bridge
- Health/heartbeat publishing
- Config validation and normalization
- Simulation mode + dry-run control writes
- Geofence buffer support
"""

from __future__ import annotations

import json
import logging
import math
import signal
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt


CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
ATOM_NS = "{http://www.w3.org/2005/Atom}"
SEVERITY_RANK_DEFAULT = {"unknown": 0, "minor": 1, "moderate": 2, "severe": 3, "extreme": 4}


@dataclass
class AlertMatch:
    identifier: str
    title: str
    event: str
    severity: str
    severity_rank: int
    area: str
    zone_type: str
    starts_at: Optional[int]
    expires_at: Optional[int]
    target_min_soc: int
    source: str


def now_ms() -> int:
    return int(time.time() * 1000)


def utc_iso(ts_ms: Optional[int]) -> Optional[str]:
    if not ts_ms:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def parse_time_ms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(text)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def to_num(value: Any) -> Optional[float]:
    try:
        n = float(value)
        if math.isfinite(n):
            return n
        return None
    except Exception:
        return None


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def clamp_soc_step5(value: Any, fallback: int) -> int:
    n = to_num(value)
    base = n if n is not None else fallback
    clipped = max(0.0, min(100.0, base))
    return int(round(clipped / 5.0) * 5)


def normalize_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [x.strip() for x in values.split(",") if x.strip()]
    if isinstance(values, list):
        out: List[str] = []
        for v in values:
            s = str(v).strip()
            if s:
                out.append(s)
        return out
    return []


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lon: float, points: List[Tuple[float, float]]) -> bool:
    inside = False
    x = lon
    y = lat
    j = len(points) - 1
    for i in range(len(points)):
        yi, xi = points[i]
        yj, xj = points[j]
        intersects = (yi > y) != (yj > y) and (
            x < ((xj - xi) * (y - yi)) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _xy_km(lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
    x = lon * 111.320 * math.cos(math.radians(ref_lat))
    y = lat * 110.574
    return x, y


def point_segment_distance_km(
    p_lat: float, p_lon: float, a_lat: float, a_lon: float, b_lat: float, b_lon: float
) -> float:
    ref_lat = (p_lat + a_lat + b_lat) / 3.0
    px, py = _xy_km(p_lat, p_lon, ref_lat)
    ax, ay = _xy_km(a_lat, a_lon, ref_lat)
    bx, by = _xy_km(b_lat, b_lon, ref_lat)

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    ab2 = abx * abx + aby * aby
    if ab2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(px - cx, py - cy)


def point_near_polygon(lat: float, lon: float, points: List[Tuple[float, float]], buffer_km: float) -> bool:
    if len(points) < 2 or buffer_km <= 0:
        return False
    for i in range(len(points)):
        a_lat, a_lon = points[i]
        b_lat, b_lon = points[(i + 1) % len(points)]
        if point_segment_distance_km(lat, lon, a_lat, a_lon, b_lat, b_lon) <= buffer_km:
            return True
    return False


class StormWatchDaemon:
    def __init__(self, config_path: Path) -> None:
        self.log = logging.getLogger("stormwatchd")
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.stop_event = threading.Event()
        self.state_lock = threading.Lock()

        self.started_ms = now_ms()
        self.portal_id: Optional[str] = self.config.get("portalId") or None
        self.gps_lat: Optional[float] = None
        self.gps_lon: Optional[float] = None
        self.last_eval: Dict[str, Any] = {}
        self.protect_active: bool = False
        self.storm_hold_until_ms: int = 0
        self.last_applied_min_soc: Optional[int] = None
        self.force_manual: Optional[bool] = None
        self.force_manual_until_ms: int = 0
        self.last_cap_success_ms: int = 0
        self.last_cap_sources: List[str] = []
        self.consecutive_cap_failures: int = 0
        self.last_poll_duration_ms: int = 0
        self.last_notification_sent_ms: Dict[str, int] = {}
        self.last_notification_state_key: str = ""

        mqtt_cfg = self.config["mqtt"]
        self.mqtt_client = mqtt.Client(
            client_id=mqtt_cfg.get("clientId", "stormwatchd"),
            clean_session=True,
        )
        if mqtt_cfg.get("username"):
            self.mqtt_client.username_pw_set(
                mqtt_cfg.get("username"), mqtt_cfg.get("password")
            )
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect

    def _load_config(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)

        alias = {
            "cap_feed_url": "capFeedUrl",
            "cap_feed_urls": "capFeedUrls",
            "portal_id": "portalId",
            "use_victron_gps": "useVictronGps",
            "home_area_keywords": "homeAreaKeywords",
            "match_all_without_geometry": "matchAllWithoutGeometry",
            "lead_minutes": "leadMinutes",
            "clear_hold_minutes": "clearHoldMinutes",
            "poll_interval_seconds": "pollSeconds",
            "normal_min_soc": "normalMinSoc",
            "storm_min_soc": "stormMinSoc",
            "accepted_severities": "acceptedSeverities",
            "storm_keywords": "stormKeywords",
            "status_topic": "stateTopicBase",
            "command_topic": "commandTopic",
            "max_stale_minutes": "maxStaleMinutes",
            "stale_policy": "stalePolicy",
            "severity_min_soc": "severityMinSoc",
            "storm_soc_ramp_per_poll": "stormSocRampPerPoll",
            "default_manual_override_minutes": "defaultManualOverrideMinutes",
            "vrm_topic_base": "vrmTopicBase",
            "heartbeat_topic": "heartbeatTopic",
            "simulate_mode": "simulateMode",
            "simulation_file": "simulationFile",
            "dry_run": "dryRun",
            "geofence_buffer_km": "geofenceBufferKm",
            "log_level": "logLevel",
            "notification_cooldown_seconds": "notificationCooldownSeconds",
        }
        for old_key, new_key in alias.items():
            if old_key in cfg and new_key not in cfg:
                cfg[new_key] = cfg[old_key]

        if "capFeedUrls" not in cfg and "capFeedUrl" in cfg:
            cfg["capFeedUrls"] = [cfg["capFeedUrl"]]

        cfg.setdefault("capFeedUrls", ["https://alerts.metservice.com/cap/rss"])
        cfg.setdefault("capFetchTimeoutSeconds", 20)
        cfg.setdefault("portalId", "")
        cfg.setdefault("home", {"lat": None, "lon": None, "name": "Home"})
        cfg.setdefault("useVictronGps", True)
        cfg.setdefault("homeAreaKeywords", [])
        cfg.setdefault("matchAllWithoutGeometry", False)
        cfg.setdefault("geofenceBufferKm", 0.0)
        cfg.setdefault("leadMinutes", 30)
        cfg.setdefault("clearHoldMinutes", 60)
        cfg.setdefault("pollSeconds", 300)
        cfg.setdefault("normalMinSoc", 20)
        cfg.setdefault("stormMinSoc", 80)
        cfg.setdefault("acceptedSeverities", ["Moderate", "Severe", "Extreme"])
        cfg.setdefault(
            "stormKeywords",
            [
                "storm",
                "thunderstorm",
                "severe weather",
                "heavy rain",
                "flood",
                "wind",
                "gale",
                "squall",
                "cyclone",
                "tornado",
                "hail",
                "snow",
                "ice",
            ],
        )
        cfg.setdefault("severityRank", dict(SEVERITY_RANK_DEFAULT))
        cfg.setdefault("severityMinSoc", {"Moderate": 60, "Severe": 80, "Extreme": 90})
        cfg.setdefault("stormSocRampPerPoll", 10)
        cfg.setdefault("maxStaleMinutes", 60)
        cfg.setdefault("stalePolicy", "hold_last")  # hold_last | force_protect | force_normal
        cfg.setdefault("defaultManualOverrideMinutes", 0)
        cfg.setdefault("stateTopicBase", "N/custom/stormwatch")
        cfg.setdefault("commandTopic", "R/custom/stormwatch/command")
        cfg.setdefault("vrmTopicBase", f'{cfg["stateTopicBase"].rstrip("/")}/vrm')
        cfg.setdefault("heartbeatTopic", f'{cfg["stateTopicBase"].rstrip("/")}/heartbeat')
        cfg.setdefault("simulateMode", False)
        cfg.setdefault("simulationFile", "")
        cfg.setdefault("dryRun", False)
        cfg.setdefault("logLevel", "INFO")
        cfg.setdefault("notificationCooldownSeconds", 300)
        cfg.setdefault(
            "notifications",
            {
                "enabled": False,
                "notifyOnStateChange": True,
                "notifyOnStale": True,
                "notifyOnError": True,
                "email": {
                    "enabled": False,
                    "from": "",
                    "to": [],
                    "subjectPrefix": "[StormWatch]",
                    "smtpHost": "",
                    "smtpPort": 587,
                    "username": "",
                    "password": "",
                    "useTls": True,
                    "useSsl": False,
                    "timeoutSeconds": 20,
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "timeoutSeconds": 10,
                },
            },
        )
        cfg.setdefault(
            "mqtt",
            {"host": "127.0.0.1", "port": 1883, "qos": 1, "clientId": "stormwatchd"},
        )

        if "home" in cfg and isinstance(cfg["home"], dict):
            if "latitude" in cfg["home"] and "lat" not in cfg["home"]:
                cfg["home"]["lat"] = cfg["home"]["latitude"]
            if "longitude" in cfg["home"] and "lon" not in cfg["home"]:
                cfg["home"]["lon"] = cfg["home"]["longitude"]

        self._validate_config(cfg)
        return cfg

    def _validate_config(self, cfg: Dict[str, Any]) -> None:
        urls = normalize_list(cfg.get("capFeedUrls"))
        cfg["capFeedUrls"] = urls if urls else ["https://alerts.metservice.com/cap/rss"]
        cfg["acceptedSeverities"] = normalize_list(cfg.get("acceptedSeverities"))
        cfg["stormKeywords"] = normalize_list(cfg.get("stormKeywords"))
        cfg["homeAreaKeywords"] = normalize_list(cfg.get("homeAreaKeywords"))

        cfg["pollSeconds"] = max(30, int(to_num(cfg.get("pollSeconds")) or 300))
        cfg["capFetchTimeoutSeconds"] = max(3, int(to_num(cfg.get("capFetchTimeoutSeconds")) or 20))
        cfg["notificationCooldownSeconds"] = max(
            0, int(to_num(cfg.get("notificationCooldownSeconds")) or 300)
        )
        cfg["leadMinutes"] = max(0, int(to_num(cfg.get("leadMinutes")) or 30))
        cfg["clearHoldMinutes"] = max(0, int(to_num(cfg.get("clearHoldMinutes")) or 60))
        cfg["maxStaleMinutes"] = max(1, int(to_num(cfg.get("maxStaleMinutes")) or 60))
        cfg["stormSocRampPerPoll"] = max(0, int(to_num(cfg.get("stormSocRampPerPoll")) or 10))
        cfg["defaultManualOverrideMinutes"] = max(
            0, int(to_num(cfg.get("defaultManualOverrideMinutes")) or 0)
        )
        cfg["geofenceBufferKm"] = max(0.0, float(to_num(cfg.get("geofenceBufferKm")) or 0.0))

        cfg["normalMinSoc"] = clamp_soc_step5(cfg.get("normalMinSoc"), 20)
        cfg["stormMinSoc"] = clamp_soc_step5(cfg.get("stormMinSoc"), 80)
        if cfg["stormMinSoc"] < cfg["normalMinSoc"]:
            self.log.warning("stormMinSoc < normalMinSoc, auto-correcting stormMinSoc")
            cfg["stormMinSoc"] = cfg["normalMinSoc"]

        stp = str(cfg.get("stalePolicy", "hold_last")).strip().lower()
        if stp not in {"hold_last", "force_protect", "force_normal"}:
            self.log.warning("Unknown stalePolicy=%r, using hold_last", stp)
            stp = "hold_last"
        cfg["stalePolicy"] = stp

        cfg["useVictronGps"] = to_bool(cfg.get("useVictronGps"), True)
        cfg["matchAllWithoutGeometry"] = to_bool(cfg.get("matchAllWithoutGeometry"), False)
        cfg["simulateMode"] = to_bool(cfg.get("simulateMode"), False)
        cfg["dryRun"] = to_bool(cfg.get("dryRun"), False)

        home = cfg.get("home", {})
        if not isinstance(home, dict):
            home = {"lat": None, "lon": None, "name": "Home"}
        lat = to_num(home.get("lat"))
        lon = to_num(home.get("lon"))
        if lat is not None and (lat < -90 or lat > 90):
            self.log.warning("Invalid home.lat=%s, clearing", lat)
            lat = None
        if lon is not None and (lon < -180 or lon > 180):
            self.log.warning("Invalid home.lon=%s, clearing", lon)
            lon = None
        home["lat"] = lat
        home["lon"] = lon
        home.setdefault("name", "Home")
        cfg["home"] = home

        rank_map = cfg.get("severityRank", {})
        if not isinstance(rank_map, dict):
            rank_map = {}
        norm_rank: Dict[str, int] = dict(SEVERITY_RANK_DEFAULT)
        for k, v in rank_map.items():
            kk = str(k).strip().lower()
            vv = int(to_num(v) or 0)
            norm_rank[kk] = vv
        cfg["severityRank"] = norm_rank

        tier_map = cfg.get("severityMinSoc", {})
        if not isinstance(tier_map, dict):
            tier_map = {}
        norm_tier: Dict[str, int] = {}
        for k, v in tier_map.items():
            kk = str(k).strip().lower()
            norm_tier[kk] = clamp_soc_step5(v, cfg["stormMinSoc"])
        for req in ["moderate", "severe", "extreme"]:
            norm_tier.setdefault(req, cfg["stormMinSoc"])
        cfg["severityMinSoc"] = norm_tier

        mqtt_cfg = cfg.get("mqtt", {})
        if not isinstance(mqtt_cfg, dict):
            mqtt_cfg = {}
        mqtt_cfg.setdefault("host", "127.0.0.1")
        mqtt_cfg["port"] = int(to_num(mqtt_cfg.get("port")) or 1883)
        mqtt_cfg["qos"] = max(0, min(2, int(to_num(mqtt_cfg.get("qos")) or 1)))
        mqtt_cfg.setdefault("clientId", "stormwatchd")
        cfg["mqtt"] = mqtt_cfg

        notifications = cfg.get("notifications", {})
        if not isinstance(notifications, dict):
            notifications = {}
        notifications["enabled"] = to_bool(notifications.get("enabled"), False)
        notifications["notifyOnStateChange"] = to_bool(
            notifications.get("notifyOnStateChange"), True
        )
        notifications["notifyOnStale"] = to_bool(notifications.get("notifyOnStale"), True)
        notifications["notifyOnError"] = to_bool(notifications.get("notifyOnError"), True)

        email_cfg = notifications.get("email", {})
        if not isinstance(email_cfg, dict):
            email_cfg = {}
        email_cfg["enabled"] = to_bool(email_cfg.get("enabled"), False)
        email_cfg["from"] = str(email_cfg.get("from", "")).strip()
        email_cfg["to"] = normalize_list(email_cfg.get("to"))
        email_cfg["subjectPrefix"] = str(email_cfg.get("subjectPrefix", "[StormWatch]")).strip()
        email_cfg["smtpHost"] = str(email_cfg.get("smtpHost", "")).strip()
        email_cfg["smtpPort"] = int(to_num(email_cfg.get("smtpPort")) or 587)
        email_cfg["username"] = str(email_cfg.get("username", "")).strip()
        email_cfg["password"] = str(email_cfg.get("password", ""))
        email_cfg["useTls"] = to_bool(email_cfg.get("useTls"), True)
        email_cfg["useSsl"] = to_bool(email_cfg.get("useSsl"), False)
        email_cfg["timeoutSeconds"] = max(3, int(to_num(email_cfg.get("timeoutSeconds")) or 20))
        notifications["email"] = email_cfg

        webhook_cfg = notifications.get("webhook", {})
        if not isinstance(webhook_cfg, dict):
            webhook_cfg = {}
        webhook_cfg["enabled"] = to_bool(webhook_cfg.get("enabled"), False)
        webhook_cfg["url"] = str(webhook_cfg.get("url", "")).strip()
        webhook_cfg["timeoutSeconds"] = max(3, int(to_num(webhook_cfg.get("timeoutSeconds")) or 10))
        webhook_cfg["method"] = str(webhook_cfg.get("method", "POST")).strip().upper() or "POST"
        notifications["webhook"] = webhook_cfg
        cfg["notifications"] = notifications

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int):
        if rc != 0:
            self.log.error("MQTT connect failed rc=%s", rc)
            return
        self.log.info("MQTT connected")
        qos = int(self.config["mqtt"].get("qos", 1))
        client.subscribe("N/+/battery/+/Soc", qos=qos)
        client.subscribe("N/+/system/0/Gps/#", qos=qos)
        client.subscribe("N/+/gps/+/#", qos=qos)
        client.subscribe(self.config["commandTopic"], qos=qos)

    def on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int):
        self.log.warning("MQTT disconnected rc=%s", rc)

    def _extract_payload_value(self, payload: bytes) -> Any:
        try:
            text = payload.decode("utf-8", errors="ignore")
            data = json.loads(text)
            if isinstance(data, dict) and "value" in data:
                return data["value"]
            return data
        except Exception:
            return payload.decode("utf-8", errors="ignore").strip()

    def _maybe_set_portal_id(self, topic: str) -> None:
        if self.portal_id:
            return
        parts = topic.split("/")
        if len(parts) > 1 and parts[0] == "N" and parts[1]:
            self.portal_id = parts[1]
            self.log.info("Discovered portal ID: %s", self.portal_id)

    def on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage):
        topic = msg.topic
        self._maybe_set_portal_id(topic)
        value = self._extract_payload_value(msg.payload)

        if topic == self.config["commandTopic"]:
            self._handle_command(value)
            return

        tl = topic.lower()
        with self.state_lock:
            if tl.endswith("/latitude") or tl.endswith("/lat"):
                lat = to_num(value)
                if lat is not None:
                    self.gps_lat = lat
                return
            if tl.endswith("/longitude") or tl.endswith("/lon") or tl.endswith("/lng"):
                lon = to_num(value)
                if lon is not None:
                    self.gps_lon = lon
                return

            if isinstance(value, dict):
                lat = to_num(value.get("latitude", value.get("lat")))
                lon = to_num(value.get("longitude", value.get("lon", value.get("lng"))))
                if lat is not None:
                    self.gps_lat = lat
                if lon is not None:
                    self.gps_lon = lon

    def _handle_command(self, value: Any) -> None:
        cmd = value if isinstance(value, dict) else {}
        action = str(cmd.get("action", "")).strip()
        now = now_ms()

        if action == "forceProtect":
            enabled = bool(cmd.get("enabled", False))
            ttl = to_num(cmd.get("ttlMinutes"))
            ttl_minutes = int(ttl) if ttl is not None else int(self.config.get("defaultManualOverrideMinutes", 0))
            with self.state_lock:
                self.force_manual = enabled
                if ttl_minutes > 0:
                    self.force_manual_until_ms = now + ttl_minutes * 60000
                else:
                    self.force_manual_until_ms = 0
            self.log.warning(
                "Manual override forceProtect=%s ttlMinutes=%s",
                enabled,
                ttl_minutes if ttl_minutes > 0 else "none",
            )
        elif action == "clearManualOverride":
            with self.state_lock:
                self.force_manual = None
                self.force_manual_until_ms = 0
            self.log.warning("Manual override cleared")
        elif action == "runNow":
            self.log.info("Immediate poll requested")
            self.evaluate_once()
        elif action == "reloadConfig":
            self._reload_config()
        elif action == "sendTestNotification":
            self._send_test_notification(cmd)
        else:
            self.log.warning("Unknown command on %s: %r", self.config["commandTopic"], cmd)

    def _reload_config(self) -> None:
        self.log.info("Reloading config from %s", self.config_path)
        self.config = self._load_config(self.config_path)
        self.log.info("Config reloaded")

    def _fetch_text_url(self, url: str, timeout_seconds: int) -> str:
        req = urllib.request.Request(
            f'{url}{"&" if "?" in url else "?"}_ts={now_ms()}',
            headers={"User-Agent": "stormwatchd/2.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _fetch_cap_documents(self) -> Tuple[List[Tuple[str, str]], List[str]]:
        # Simulation mode can ingest a static CAP XML file.
        if to_bool(self.config.get("simulateMode"), False):
            sim_file = str(self.config.get("simulationFile", "")).strip()
            if not sim_file:
                raise RuntimeError("simulateMode=true but simulationFile is empty")
            text = Path(sim_file).read_text(encoding="utf-8")
            return [("simulation://" + sim_file, text)], []

        urls = normalize_list(self.config.get("capFeedUrls"))
        timeout_seconds = int(self.config.get("capFetchTimeoutSeconds", 20))
        documents: List[Tuple[str, str]] = []
        errors: List[str] = []
        for url in urls:
            try:
                documents.append((url, self._fetch_text_url(url, timeout_seconds)))
            except Exception as e:
                errors.append(f"{url}: {e}")
        if not documents:
            raise RuntimeError("All CAP feeds failed: " + "; ".join(errors))
        return documents, errors

    def _text(self, node: Optional[ET.Element], default: str = "") -> str:
        if node is None:
            return default
        return (node.text or "").strip()

    def _find_first_text(self, item: ET.Element, tags: List[str]) -> str:
        for tag in tags:
            found = item.find(tag, CAP_NS)
            if found is not None and (found.text or "").strip():
                return found.text.strip()
        return ""

    def _parse_polygon(self, text: str) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        for pair in text.split():
            parts = pair.split(",")
            if len(parts) != 2:
                continue
            lat = to_num(parts[0])
            lon = to_num(parts[1])
            if lat is None or lon is None:
                continue
            points.append((lat, lon))
        return points

    def _parse_circle(self, text: str) -> Optional[Tuple[float, float, float]]:
        parts = text.split()
        if len(parts) < 2:
            return None
        center = parts[0].split(",")
        if len(center) != 2:
            return None
        lat = to_num(center[0])
        lon = to_num(center[1])
        radius = to_num(parts[1])
        if lat is None or lon is None or radius is None or radius < 0:
            return None
        return (lat, lon, radius)

    def _home_position(self) -> Tuple[Optional[float], Optional[float], str]:
        with self.state_lock:
            gps_lat = self.gps_lat
            gps_lon = self.gps_lon
        cfg_lat = to_num(self.config.get("home", {}).get("lat"))
        cfg_lon = to_num(self.config.get("home", {}).get("lon"))
        use_gps = bool(self.config.get("useVictronGps", True))
        if use_gps and gps_lat is not None and gps_lon is not None:
            return gps_lat, gps_lon, "victron-gps"
        if cfg_lat is not None and cfg_lon is not None:
            return cfg_lat, cfg_lon, "config"
        return None, None, "missing"

    def _parse_items(self, xml_text: str, source_url: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        items: List[ET.Element] = []
        items.extend(root.findall("./channel/item"))
        items.extend(root.findall(f".//{ATOM_NS}entry"))

        parsed: List[Dict[str, Any]] = []
        for item in items:
            title = self._find_first_text(item, ["title", f"{ATOM_NS}title"])
            event = self._find_first_text(item, ["cap:event"]) or title
            desc = self._find_first_text(
                item,
                ["description", f"{ATOM_NS}summary", f"{ATOM_NS}content"],
            )
            severity = self._find_first_text(item, ["cap:severity"]) or "Unknown"
            area_desc = self._find_first_text(item, ["cap:areaDesc", "cap:area"])
            identifier = self._find_first_text(item, ["cap:identifier", "guid", f"{ATOM_NS}id"])
            if not identifier:
                identifier = f"{event}|{title}|{area_desc}"

            onset = parse_time_ms(self._find_first_text(item, ["cap:onset"]))
            effective = parse_time_ms(self._find_first_text(item, ["cap:effective"]))
            expires = parse_time_ms(self._find_first_text(item, ["cap:expires"]))
            if expires is None:
                expires = parse_time_ms(self._find_first_text(item, ["pubDate"]))

            polygons = [self._text(n) for n in item.findall("cap:polygon", CAP_NS)]
            circles = [self._text(n) for n in item.findall("cap:circle", CAP_NS)]

            parsed.append(
                {
                    "id": identifier,
                    "title": title,
                    "event": event,
                    "description": desc,
                    "severity": severity,
                    "area": area_desc,
                    "onset": onset,
                    "effective": effective,
                    "expires": expires,
                    "polygons": polygons,
                    "circles": circles,
                    "source": source_url,
                }
            )
        return parsed

    def _dedupe_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for a in alerts:
            key = f'{a.get("id","")}::{a.get("event","")}::{a.get("area","")}::{a.get("expires")}'
            prev = out.get(key)
            if prev is None:
                out[key] = a
                continue
            prev_exp = to_num(prev.get("expires")) or 0
            cur_exp = to_num(a.get("expires")) or 0
            if cur_exp > prev_exp:
                out[key] = a
        return list(out.values())

    def _alert_target_soc(self, severity_text: str) -> int:
        sev = str(severity_text or "unknown").strip().lower()
        tier = self.config.get("severityMinSoc", {})
        default_soc = int(self.config.get("stormMinSoc", 80))
        return clamp_soc_step5(tier.get(sev, default_soc), default_soc)

    def _severity_rank(self, severity_text: str) -> int:
        sev = str(severity_text or "unknown").strip().lower()
        rank_map = self.config.get("severityRank", SEVERITY_RANK_DEFAULT)
        return int(to_num(rank_map.get(sev)) or 0)

    def _matches(self, alerts: List[Dict[str, Any]]) -> List[AlertMatch]:
        now = now_ms()
        lead_ms = int(max(0, int(self.config.get("leadMinutes", 30))) * 60000)
        accepted = {
            str(s).strip().lower()
            for s in self.config.get("acceptedSeverities", [])
            if str(s).strip()
        }
        keywords = [
            str(k).strip().lower()
            for k in self.config.get("stormKeywords", [])
            if str(k).strip()
        ]
        area_keywords = [
            str(k).strip().lower()
            for k in self.config.get("homeAreaKeywords", [])
            if str(k).strip()
        ]
        buffer_km = float(self.config.get("geofenceBufferKm", 0.0))
        home_lat, home_lon, _ = self._home_position()
        has_home = home_lat is not None and home_lon is not None

        out: List[AlertMatch] = []
        for a in alerts:
            searchable = f'{a.get("event","")} {a.get("title","")} {a.get("description","")}'.lower()
            if keywords and not any(k in searchable for k in keywords):
                continue

            severity_text = str(a.get("severity", "")).strip()
            sev_norm = severity_text.lower()
            if accepted and sev_norm not in accepted:
                continue

            starts = a.get("onset") or a.get("effective") or now
            expires = a.get("expires")
            if starts - lead_ms > now:
                continue
            if expires is not None and expires < now:
                continue

            in_zone = False
            zone_type = "none"
            if has_home:
                for p in a.get("polygons", []):
                    pts = self._parse_polygon(p)
                    if len(pts) < 3:
                        continue
                    if point_in_polygon(home_lat, home_lon, pts):
                        in_zone = True
                        zone_type = "polygon"
                        break
                    if point_near_polygon(home_lat, home_lon, pts, buffer_km):
                        in_zone = True
                        zone_type = "polygon-buffer"
                        break
                if not in_zone:
                    for c in a.get("circles", []):
                        parsed = self._parse_circle(c)
                        if not parsed:
                            continue
                        clat, clon, rkm = parsed
                        if haversine_km(home_lat, home_lon, clat, clon) <= (rkm + buffer_km):
                            in_zone = True
                            zone_type = "circle-buffer" if buffer_km > 0 else "circle"
                            break

            if not in_zone and area_keywords:
                area_norm = str(a.get("area", "")).lower()
                if any(k in area_norm for k in area_keywords):
                    in_zone = True
                    zone_type = "area-keyword"

            if (
                not in_zone
                and bool(self.config.get("matchAllWithoutGeometry", False))
                and not a.get("polygons")
                and not a.get("circles")
            ):
                in_zone = True
                zone_type = "no-geometry-fallback"

            if not in_zone:
                continue

            out.append(
                AlertMatch(
                    identifier=str(a.get("id", "")),
                    title=str(a.get("title", "")),
                    event=str(a.get("event", "")),
                    severity=severity_text or "Unknown",
                    severity_rank=self._severity_rank(severity_text),
                    area=str(a.get("area", "")),
                    zone_type=zone_type,
                    starts_at=starts,
                    expires_at=expires,
                    target_min_soc=self._alert_target_soc(severity_text),
                    source=str(a.get("source", "")),
                )
            )
        return out

    def _is_stale(self, now: int) -> bool:
        if self.last_cap_success_ms <= 0:
            return True
        max_stale_ms = int(self.config.get("maxStaleMinutes", 60)) * 60000
        return (now - self.last_cap_success_ms) > max_stale_ms

    def _publish(self, topic: str, payload: Any, retain: bool = True) -> None:
        qos = int(self.config["mqtt"].get("qos", 1))
        data = payload if isinstance(payload, str) else json.dumps(payload)
        self.mqtt_client.publish(topic, data, qos=qos, retain=retain)

    def _publish_state(self, payload: Dict[str, Any]) -> None:
        base = self.config["stateTopicBase"].rstrip("/")
        self._publish(f"{base}/json", payload, retain=True)
        self._publish(f"{base}/active", "1" if payload.get("shouldProtect") else "0", retain=True)
        self._publish(f"{base}/reason", str(payload.get("reason", "")), retain=True)
        self._publish(f"{base}/matchedCount", str(payload.get("matchedCount", 0)), retain=True)
        self._publish(f"{base}/holdUntil", str(payload.get("holdUntil") or ""), retain=True)

        home = payload.get("home", {})
        self._publish(f"{base}/home/source", str(home.get("source", "missing")), retain=True)
        if home.get("lat") is not None:
            self._publish(f"{base}/home/lat", str(home.get("lat")), retain=True)
        if home.get("lon") is not None:
            self._publish(f"{base}/home/lon", str(home.get("lon")), retain=True)

        health = payload.get("health", {})
        for key in [
            "stale",
            "consecutiveFailures",
            "lastPollDurationMs",
            "lastCapSuccess",
            "uptimeSeconds",
            "sources",
            "fetchErrors",
        ]:
            if key in health:
                value = health[key]
                if isinstance(value, (dict, list)):
                    self._publish(f"{base}/health/{key}", value, retain=True)
                else:
                    self._publish(f"{base}/health/{key}", str(value), retain=True)

        # Heartbeat endpoint for external watchdogs.
        heartbeat = {
            "timestamp": payload.get("timestamp"),
            "shouldProtect": payload.get("shouldProtect"),
            "reason": payload.get("reason"),
            "portalId": payload.get("portalId"),
        }
        self._publish(self.config["heartbeatTopic"], heartbeat, retain=True)

        # VRM-friendly bridge topics.
        vrm = self.config["vrmTopicBase"].rstrip("/")
        should_protect = bool(payload.get("shouldProtect"))
        stale = bool(health.get("stale", False))
        alarm_level = 2 if should_protect else (1 if stale else 0)
        self._publish(f"{vrm}/State", str(1 if should_protect else 0), retain=True)
        self._publish(f"{vrm}/AlarmLevel", str(alarm_level), retain=True)
        self._publish(f"{vrm}/AlarmText", str(payload.get("reason", "")), retain=True)
        self._publish(f"{vrm}/MatchedCount", str(payload.get("matchedCount", 0)), retain=True)
        self._publish(f"{vrm}/LastUpdate", str(payload.get("timestamp", "")), retain=True)

    def _notification_subject(self, event: str, info: Dict[str, Any]) -> str:
        prefix = str(self.config.get("notifications", {}).get("email", {}).get("subjectPrefix", "[StormWatch]")).strip() or "[StormWatch]"
        mode = "PROTECT" if info.get("shouldProtect") else "NORMAL"
        reason = str(info.get("reason", "-")).strip()
        return f"{prefix} {event}: {mode} ({reason})"

    def _notification_body(self, event: str, info: Dict[str, Any]) -> str:
        lines = [
            f"Event: {event}",
            f"Timestamp: {info.get('timestamp')}",
            f"Mode: {'PROTECT' if info.get('shouldProtect') else 'NORMAL'}",
            f"Reason: {info.get('reason')}",
            f"Matched alerts: {info.get('matchedCount', 0)}",
            f"Hold until: {info.get('holdUntil')}",
            f"Portal ID: {info.get('portalId')}",
        ]
        home = info.get("home", {})
        lines.append(f"Home: {home.get('lat')}, {home.get('lon')} ({home.get('source')})")
        control = info.get("control", {})
        lines.append(
            f"Control: normal={control.get('normalMinSoc')} stormTarget={control.get('stormTargetMinSoc')} stormRamped={control.get('stormRampedMinSoc')}"
        )
        if info.get("error"):
            lines.append(f"Error: {info.get('error')}")
        alerts = info.get("matchedAlerts", []) or []
        if alerts:
            lines.append("")
            lines.append("Top alerts:")
            for a in alerts[:3]:
                lines.append(
                    f"- {a.get('event') or a.get('title')} | {a.get('severity')} | {a.get('zoneType')} | expires={a.get('expiresAt')}"
                )
        return "\n".join(str(x) for x in lines)

    def _send_email_notification(self, subject: str, body: str) -> bool:
        ncfg = self.config.get("notifications", {})
        email_cfg = ncfg.get("email", {}) if isinstance(ncfg, dict) else {}
        if not to_bool(email_cfg.get("enabled"), False):
            return False

        sender = str(email_cfg.get("from", "")).strip()
        recipients = normalize_list(email_cfg.get("to"))
        smtp_host = str(email_cfg.get("smtpHost", "")).strip()
        smtp_port = int(to_num(email_cfg.get("smtpPort")) or 587)
        username = str(email_cfg.get("username", "")).strip()
        password = str(email_cfg.get("password", ""))
        use_tls = to_bool(email_cfg.get("useTls"), True)
        use_ssl = to_bool(email_cfg.get("useSsl"), False)
        timeout = max(3, int(to_num(email_cfg.get("timeoutSeconds")) or 20))

        if not sender or not recipients or not smtp_host:
            self.log.warning("Email notification config incomplete; skipping")
            return False

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            if use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=context) as server:
                    if username:
                        server.login(username, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                    if use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if username:
                        server.login(username, password)
                    server.send_message(msg)
            return True
        except Exception as e:
            self.log.error("Email notification failed: %s", e)
            return False

    def _send_webhook_notification(self, payload: Dict[str, Any]) -> bool:
        ncfg = self.config.get("notifications", {})
        webhook_cfg = ncfg.get("webhook", {}) if isinstance(ncfg, dict) else {}
        if not to_bool(webhook_cfg.get("enabled"), False):
            return False

        url = str(webhook_cfg.get("url", "")).strip()
        method = str(webhook_cfg.get("method", "POST")).strip().upper() or "POST"
        timeout = max(3, int(to_num(webhook_cfg.get("timeoutSeconds")) or 10))
        if not url:
            self.log.warning("Webhook URL missing; skipping")
            return False

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "User-Agent": "stormwatchd/2.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = getattr(resp, "status", 200)
                if int(code) >= 400:
                    self.log.error("Webhook notification HTTP %s", code)
                    return False
            return True
        except Exception as e:
            self.log.error("Webhook notification failed: %s", e)
            return False

    def _notification_allowed(self, event_key: str, now: int) -> bool:
        cooldown = int(self.config.get("notificationCooldownSeconds", 300)) * 1000
        if cooldown <= 0:
            return True
        last = int(self.last_notification_sent_ms.get(event_key, 0))
        return (now - last) >= cooldown

    def _send_test_notification(self, cmd: Dict[str, Any]) -> None:
        now = now_ms()
        info: Dict[str, Any] = {
            "timestamp": utc_iso(now),
            "portalId": self.portal_id,
            "shouldProtect": bool(self.protect_active),
            "reason": "manual-test",
            "matchedCount": int(self.last_eval.get("matchedCount", 0)) if self.last_eval else 0,
            "holdUntil": self.last_eval.get("holdUntil") if self.last_eval else None,
            "home": self.last_eval.get("home", {}) if self.last_eval else {},
            "control": self.last_eval.get("control", {}) if self.last_eval else {},
            "matchedAlerts": self.last_eval.get("matchedAlerts", [])[:3] if self.last_eval else [],
        }
        custom_subject = str(cmd.get("subject", "")).strip()
        custom_body = str(cmd.get("body", "")).strip()
        subject = custom_subject or self._notification_subject("test", info)
        body = custom_body or self._notification_body("test", info)

        payload = {
            "event": "test",
            "timestamp": info.get("timestamp"),
            "subject": subject,
            "reason": "manual-test",
            "shouldProtect": info.get("shouldProtect"),
            "matchedCount": info.get("matchedCount", 0),
            "holdUntil": info.get("holdUntil"),
            "stormWatch": info,
        }

        sent_email = self._send_email_notification(subject, body)
        sent_webhook = self._send_webhook_notification(payload)
        if sent_email or sent_webhook:
            self.last_notification_sent_ms["test"] = now
            self.log.info(
                "Test notification sent (email=%s webhook=%s)",
                sent_email,
                sent_webhook,
            )
            self._publish(
                f'{self.config["stateTopicBase"].rstrip("/")}/notification/testResult',
                {
                    "timestamp": info["timestamp"],
                    "ok": True,
                    "email": sent_email,
                    "webhook": sent_webhook,
                },
                retain=True,
            )
        else:
            self.log.warning("Test notification failed or no channels enabled")
            self._publish(
                f'{self.config["stateTopicBase"].rstrip("/")}/notification/testResult',
                {
                    "timestamp": info["timestamp"],
                    "ok": False,
                    "email": sent_email,
                    "webhook": sent_webhook,
                    "message": "No notification channel succeeded. Check notifications config.",
                },
                retain=True,
            )

    def _maybe_send_notification(self, previous_should_protect: bool, previous_reason: str, info: Dict[str, Any]) -> None:
        notifications = self.config.get("notifications", {})
        if not isinstance(notifications, dict) or not to_bool(notifications.get("enabled"), False):
            return

        now = now_ms()
        reason = str(info.get("reason", ""))
        should_protect = bool(info.get("shouldProtect"))

        event = ""
        if to_bool(notifications.get("notifyOnStateChange"), True) and should_protect != previous_should_protect:
            event = "state-change"
        elif to_bool(notifications.get("notifyOnStale"), True) and str(reason).startswith("stale"):
            event = "stale"
        elif to_bool(notifications.get("notifyOnError"), True) and bool(info.get("error")):
            event = "error"

        if not event:
            return

        state_key = f"{event}:{int(should_protect)}:{reason}"
        if event == "state-change" and state_key == self.last_notification_state_key:
            return
        if not self._notification_allowed(event, now):
            return

        subject = self._notification_subject(event, info)
        body = self._notification_body(event, info)
        payload = {
            "event": event,
            "timestamp": info.get("timestamp"),
            "subject": subject,
            "reason": reason,
            "shouldProtect": should_protect,
            "matchedCount": info.get("matchedCount", 0),
            "holdUntil": info.get("holdUntil"),
            "error": info.get("error"),
            "stormWatch": info,
        }

        sent_any = False
        sent_any = self._send_email_notification(subject, body) or sent_any
        sent_any = self._send_webhook_notification(payload) or sent_any

        if sent_any:
            self.last_notification_sent_ms[event] = now
            self.last_notification_state_key = state_key
            self.log.info("Notification sent for event=%s", event)

    def _write_setting(self, path: str, value: Any) -> bool:
        if to_bool(self.config.get("dryRun"), False):
            self.log.warning("dryRun=true, skipped write %s <= %s", path, value)
            return True
        if not self.portal_id:
            self.log.warning("Cannot write %s, portalId unknown", path)
            return False
        topic = f"W/{self.portal_id}/settings/0/{path}"
        payload = json.dumps({"value": value})
        qos = int(self.config["mqtt"].get("qos", 1))
        result = self.mqtt_client.publish(topic, payload, qos=qos, retain=False)
        ok = (result.rc == mqtt.MQTT_ERR_SUCCESS)
        if ok:
            self.log.info("Write %s <= %s", topic, value)
        else:
            self.log.error("Write failed rc=%s for %s", result.rc, topic)
        return ok

    def _ramped_storm_soc(self, target_soc: int) -> int:
        target_soc = clamp_soc_step5(target_soc, int(self.config.get("stormMinSoc", 80)))
        ramp_step = int(self.config.get("stormSocRampPerPoll", 10))
        if ramp_step <= 0 or self.last_applied_min_soc is None:
            return target_soc
        if target_soc <= self.last_applied_min_soc:
            return target_soc
        return min(target_soc, self.last_applied_min_soc + ramp_step)

    def _apply_control(self, should_protect: bool, normal_soc: int, target_storm_soc: int) -> None:
        storm_soc = self._ramped_storm_soc(target_storm_soc)

        if should_protect and not self.protect_active:
            ok1 = self._write_setting("Settings/CGwacs/BatteryLife/MinimumSocLimit", storm_soc)
            ok2 = self._write_setting("Settings/CGwacs/BatteryLife/ForceCharge", 1)
            if ok1 and ok2:
                self.protect_active = True
                self.last_applied_min_soc = storm_soc
                self.log.warning("Storm protection ENABLED (%s%%)", storm_soc)
            return

        if should_protect and self.protect_active:
            if self.last_applied_min_soc != storm_soc:
                if self._write_setting("Settings/CGwacs/BatteryLife/MinimumSocLimit", storm_soc):
                    self.last_applied_min_soc = storm_soc
                    self.log.warning("Storm protection reserve adjusted to %s%%", storm_soc)
            return

        if (not should_protect) and self.protect_active:
            ok1 = self._write_setting("Settings/CGwacs/BatteryLife/ForceCharge", 0)
            ok2 = self._write_setting("Settings/CGwacs/BatteryLife/MinimumSocLimit", normal_soc)
            if ok1 and ok2:
                self.protect_active = False
                self.last_applied_min_soc = normal_soc
                self.log.warning("Storm protection DISABLED (%s%%)", normal_soc)

    def _evaluate_alerts(self) -> Tuple[List[AlertMatch], List[str], List[str]]:
        docs, fetch_errors = self._fetch_cap_documents()
        parse_errors: List[str] = []
        alerts: List[Dict[str, Any]] = []
        sources: List[str] = []

        for source_url, xml_text in docs:
            try:
                alerts.extend(self._parse_items(xml_text, source_url))
                sources.append(source_url)
            except Exception as e:
                parse_errors.append(f"{source_url}: {e}")

        if not alerts:
            errors = fetch_errors + parse_errors
            raise RuntimeError("No usable CAP alerts from any source: " + "; ".join(errors))

        deduped = self._dedupe_alerts(alerts)
        return self._matches(deduped), sources, fetch_errors + parse_errors

    def evaluate_once(self) -> None:
        start = now_ms()
        now = start
        normal_soc = clamp_soc_step5(self.config.get("normalMinSoc"), 20)
        default_storm_soc = clamp_soc_step5(self.config.get("stormMinSoc"), 80)
        hold_ms = int(max(0, int(self.config.get("clearHoldMinutes", 60))) * 60000)

        with self.state_lock:
            if self.force_manual is not None and self.force_manual_until_ms > 0 and now >= self.force_manual_until_ms:
                self.log.info("Manual override expired")
                self.force_manual = None
                self.force_manual_until_ms = 0
            manual_force = self.force_manual
            manual_until = self.force_manual_until_ms

        info: Dict[str, Any] = {
            "timestamp": utc_iso(now),
            "portalId": self.portal_id,
            "control": {
                "normalMinSoc": normal_soc,
                "stormMinSocDefault": default_storm_soc,
            },
        }
        home_lat, home_lon, home_source = self._home_position()
        info["home"] = {"lat": home_lat, "lon": home_lon, "source": home_source}
        info["manualOverride"] = {
            "mode": "force_on" if manual_force is True else ("force_off" if manual_force is False else "auto"),
            "until": utc_iso(manual_until) if manual_until else None,
        }

        should_protect = self.protect_active
        reason = "hold-last"
        target_storm_soc = default_storm_soc
        matches: List[AlertMatch] = []
        fetch_error_text = ""
        sources: List[str] = []
        health_errors: List[str] = []

        try:
            matches, sources, health_errors = self._evaluate_alerts()
            self.last_cap_success_ms = now
            self.last_cap_sources = sources
            self.consecutive_cap_failures = 0

            if matches:
                should_protect = True
                reason = "active-alert"
                target_storm_soc = max(m.target_min_soc for m in matches)
                furthest_exp = max((m.expires_at or now) for m in matches)
                self.storm_hold_until_ms = furthest_exp + hold_ms
            else:
                should_protect = False
                reason = "clear"
                if self.storm_hold_until_ms > now:
                    should_protect = True
                    reason = "hold-timer"
                else:
                    self.storm_hold_until_ms = 0
        except Exception as e:
            fetch_error_text = str(e)
            self.log.error("CAP evaluation failed: %s", e)
            self.consecutive_cap_failures += 1
            stale = self._is_stale(now)
            if stale:
                policy = str(self.config.get("stalePolicy", "hold_last"))
                if policy == "force_protect":
                    should_protect = True
                    reason = "stale-force-protect"
                elif policy == "force_normal":
                    should_protect = False
                    reason = "stale-force-normal"
                else:
                    should_protect = self.protect_active
                    reason = "stale-hold-last"
            else:
                should_protect = self.protect_active
                reason = "error-hold-last"

        if manual_force is True:
            should_protect = True
            reason = "manual-force-on"
        elif manual_force is False:
            should_protect = False
            reason = "manual-force-off"

        info["matchedCount"] = len(matches)
        info["matchedAlerts"] = [
            {
                "id": m.identifier,
                "title": m.title,
                "event": m.event,
                "severity": m.severity,
                "severityRank": m.severity_rank,
                "targetMinSoc": m.target_min_soc,
                "area": m.area,
                "zoneType": m.zone_type,
                "source": m.source,
                "startsAt": utc_iso(m.starts_at),
                "expiresAt": utc_iso(m.expires_at),
            }
            for m in matches[:10]
        ]
        info["holdUntil"] = utc_iso(self.storm_hold_until_ms) if self.storm_hold_until_ms else None
        info["reason"] = reason
        info["shouldProtect"] = should_protect
        info["sources"] = sources or self.last_cap_sources

        ramped_soc = self._ramped_storm_soc(target_storm_soc)
        info["control"]["stormTargetMinSoc"] = target_storm_soc
        info["control"]["stormRampedMinSoc"] = ramped_soc

        self._apply_control(should_protect, normal_soc, target_storm_soc)

        self.last_poll_duration_ms = max(0, now_ms() - start)
        stale_now = self._is_stale(now_ms())
        info["health"] = {
            "stale": stale_now,
            "consecutiveFailures": self.consecutive_cap_failures,
            "lastPollDurationMs": self.last_poll_duration_ms,
            "lastCapSuccess": utc_iso(self.last_cap_success_ms) if self.last_cap_success_ms else None,
            "uptimeSeconds": int((now_ms() - self.started_ms) / 1000),
            "sources": sources or self.last_cap_sources,
            "fetchErrors": health_errors,
        }
        if fetch_error_text:
            info["error"] = fetch_error_text

        previous_should_protect = bool(self.last_eval.get("shouldProtect", self.protect_active))
        previous_reason = str(self.last_eval.get("reason", ""))
        self._maybe_send_notification(previous_should_protect, previous_reason, info)

        self._publish_state(info)
        self.last_eval = info

    def run(self) -> None:
        mqtt_cfg = self.config["mqtt"]
        self.mqtt_client.connect(
            mqtt_cfg.get("host", "127.0.0.1"),
            int(mqtt_cfg.get("port", 1883)),
            60,
        )
        self.mqtt_client.loop_start()
        self.log.info("StormWatch daemon started")

        poll_seconds = int(max(30, int(self.config.get("pollSeconds", 300))))
        while not self.stop_event.is_set():
            self.evaluate_once()
            self.stop_event.wait(poll_seconds)

        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.log.info("StormWatch daemon stopped")

    def stop(self) -> None:
        self.stop_event.set()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Victron Venus OS storm watch daemon")
    parser.add_argument(
        "--config",
        default="/data/stormwatch/config.json",
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    # Bootstrap logger so config load errors are visible.
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    daemon = StormWatchDaemon(Path(args.config))

    config_log_level = str(daemon.config.get("logLevel", "")).upper().strip()
    if config_log_level:
        logging.getLogger().setLevel(getattr(logging, config_log_level, logging.INFO))

    def _sig_handler(signum, frame):
        logging.getLogger("stormwatchd").info("Signal %s received, shutting down", signum)
        daemon.stop()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    daemon.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
