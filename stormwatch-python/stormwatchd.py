#!/usr/bin/env python3
"""
Storm Watch daemon for Victron Venus OS.

Features:
- Poll CAP feed (RSS/Atom XML)
- Parse CAP geometry (polygon/circle)
- Match installation location (GPS from MQTT or configured fallback)
- Apply ESS controls via Victron MQTT writes:
  - Settings/CGwacs/BatteryLife/MinimumSocLimit
  - Settings/CGwacs/BatteryLife/ForceCharge
- Publish daemon state to MQTT for dashboards/monitoring
"""

from __future__ import annotations

import json
import logging
import math
import signal
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt


CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


@dataclass
class AlertMatch:
    title: str
    event: str
    severity: str
    area: str
    zone_type: str
    starts_at: Optional[int]
    expires_at: Optional[int]


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
        # datetime.fromisoformat handles offsets in Python 3.11+
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


def clamp_soc_step5(value: Any, fallback: int) -> int:
    n = to_num(value)
    base = n if n is not None else fallback
    clipped = max(0.0, min(100.0, base))
    return int(round(clipped / 5.0) * 5)


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


class StormWatchDaemon:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.log = logging.getLogger("stormwatchd")
        self.stop_event = threading.Event()
        self.state_lock = threading.Lock()

        self.portal_id: Optional[str] = self.config.get("portalId") or None
        self.gps_lat: Optional[float] = None
        self.gps_lon: Optional[float] = None
        self.last_eval: Dict[str, Any] = {}
        self.protect_active: bool = False
        self.storm_hold_until_ms: int = 0
        self.force_manual: Optional[bool] = None

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
        # Accept both snake_case and camelCase keys.
        alias = {
            "cap_feed_url": "capFeedUrl",
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
        }
        for old_key, new_key in alias.items():
            if old_key in cfg and new_key not in cfg:
                cfg[new_key] = cfg[old_key]

        cfg.setdefault("capFeedUrl", "https://alerts.metservice.com/cap/rss")
        cfg.setdefault("portalId", "")
        cfg.setdefault("home", {"lat": None, "lon": None, "name": "Home"})
        cfg.setdefault("useVictronGps", True)
        cfg.setdefault("homeAreaKeywords", [])
        cfg.setdefault("matchAllWithoutGeometry", False)
        cfg.setdefault("leadMinutes", 30)
        cfg.setdefault("clearHoldMinutes", 60)
        cfg.setdefault("pollSeconds", 300)
        cfg.setdefault("normalMinSoc", 20)
        cfg.setdefault("stormMinSoc", 80)
        if "home" in cfg and isinstance(cfg["home"], dict):
            if "latitude" in cfg["home"] and "lat" not in cfg["home"]:
                cfg["home"]["lat"] = cfg["home"]["latitude"]
            if "longitude" in cfg["home"] and "lon" not in cfg["home"]:
                cfg["home"]["lon"] = cfg["home"]["longitude"]
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
        cfg.setdefault("stateTopicBase", "N/custom/stormwatch")
        cfg.setdefault("commandTopic", "R/custom/stormwatch/command")
        cfg.setdefault(
            "mqtt", {"host": "127.0.0.1", "port": 1883, "clientId": "stormwatchd"}
        )
        return cfg

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int):
        if rc != 0:
            self.log.error("MQTT connect failed rc=%s", rc)
            return
        self.log.info("MQTT connected")
        client.subscribe("N/+/battery/+/Soc", qos=1)
        client.subscribe("N/+/system/0/Gps/#", qos=1)
        client.subscribe("N/+/gps/+/#", qos=1)
        client.subscribe(self.config["commandTopic"], qos=1)

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
            text = payload.decode("utf-8", errors="ignore").strip()
            return text

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
        # command payload examples:
        # {"action":"forceProtect","enabled":true}
        # {"action":"forceProtect","enabled":false}
        # {"action":"clearManualOverride"}
        # {"action":"runNow"}
        cmd = value if isinstance(value, dict) else {}
        action = str(cmd.get("action", "")).strip()
        if action == "forceProtect":
            enabled = bool(cmd.get("enabled", False))
            self.force_manual = enabled
            self.log.warning("Manual override forceProtect=%s", enabled)
        elif action == "clearManualOverride":
            self.force_manual = None
            self.log.warning("Manual override cleared")
        elif action == "runNow":
            self.log.info("Immediate poll requested")
            self.evaluate_once()
        else:
            self.log.warning("Unknown command on %s: %r", self.config["commandTopic"], cmd)

    def _fetch_cap_xml(self) -> str:
        url = f'{self.config["capFeedUrl"]}{"&" if "?" in self.config["capFeedUrl"] else "?"}_ts={int(time.time()*1000)}'
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "stormwatchd/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

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
        # CAP format: "lat,lon radiusKm"
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
        cfg_lat = to_num(self.config.get("home", {}).get("lat"))
        cfg_lon = to_num(self.config.get("home", {}).get("lon"))
        use_gps = bool(self.config.get("useVictronGps", True))
        if use_gps and self.gps_lat is not None and self.gps_lon is not None:
            return self.gps_lat, self.gps_lon, "victron-gps"
        if cfg_lat is not None and cfg_lon is not None:
            return cfg_lat, cfg_lon, "config"
        return None, None, "missing"

    def _parse_items(self, xml_text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        items: List[ET.Element] = []
        # RSS
        items.extend(root.findall("./channel/item"))
        # Atom fallback
        items.extend(root.findall(".//{http://www.w3.org/2005/Atom}entry"))

        parsed: List[Dict[str, Any]] = []
        for item in items:
            title = self._find_first_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
            event = self._find_first_text(item, ["cap:event"]) or title
            desc = self._find_first_text(
                item,
                ["description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"],
            )
            severity = self._find_first_text(item, ["cap:severity"])
            area_desc = self._find_first_text(item, ["cap:areaDesc", "cap:area"])
            onset = parse_time_ms(self._find_first_text(item, ["cap:onset"]))
            effective = parse_time_ms(self._find_first_text(item, ["cap:effective"]))
            expires = parse_time_ms(self._find_first_text(item, ["cap:expires"]))
            if expires is None:
                expires = parse_time_ms(self._find_first_text(item, ["pubDate"]))

            polygons = [self._text(n) for n in item.findall("cap:polygon", CAP_NS)]
            circles = [self._text(n) for n in item.findall("cap:circle", CAP_NS)]

            parsed.append(
                {
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
                }
            )
        return parsed

    def _matches(self, alerts: List[Dict[str, Any]]) -> List[AlertMatch]:
        now = int(time.time() * 1000)
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
        home_lat, home_lon, _ = self._home_position()
        has_home = home_lat is not None and home_lon is not None

        out: List[AlertMatch] = []
        for a in alerts:
            searchable = f'{a["event"]} {a["title"]} {a["description"]}'.lower()
            if keywords and not any(k in searchable for k in keywords):
                continue
            if accepted:
                if str(a.get("severity", "")).strip().lower() not in accepted:
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
                    if len(pts) >= 3 and point_in_polygon(home_lat, home_lon, pts):
                        in_zone = True
                        zone_type = "polygon"
                        break
                if not in_zone:
                    for c in a.get("circles", []):
                        parsed = self._parse_circle(c)
                        if not parsed:
                            continue
                        clat, clon, rkm = parsed
                        if haversine_km(home_lat, home_lon, clat, clon) <= rkm:
                            in_zone = True
                            zone_type = "circle"
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
                    title=a.get("title", ""),
                    event=a.get("event", ""),
                    severity=a.get("severity", "Unknown") or "Unknown",
                    area=a.get("area", ""),
                    zone_type=zone_type,
                    starts_at=starts,
                    expires_at=expires,
                )
            )
        return out

    def _publish_state(self, payload: Dict[str, Any]) -> None:
        base = self.config["stateTopicBase"].rstrip("/")
        self.mqtt_client.publish(f"{base}/json", json.dumps(payload), qos=1, retain=True)
        self.mqtt_client.publish(
            f"{base}/active", "1" if payload.get("shouldProtect") else "0", qos=1, retain=True
        )
        self.mqtt_client.publish(
            f"{base}/reason", str(payload.get("reason", "")), qos=1, retain=True
        )
        self.mqtt_client.publish(
            f"{base}/matchedCount", str(payload.get("matchedCount", 0)), qos=1, retain=True
        )
        hold = payload.get("holdUntil") or ""
        self.mqtt_client.publish(f"{base}/holdUntil", str(hold), qos=1, retain=True)
        home = payload.get("home", {})
        self.mqtt_client.publish(
            f"{base}/home/source", str(home.get("source", "missing")), qos=1, retain=True
        )
        if home.get("lat") is not None:
            self.mqtt_client.publish(f"{base}/home/lat", str(home.get("lat")), qos=1, retain=True)
        if home.get("lon") is not None:
            self.mqtt_client.publish(f"{base}/home/lon", str(home.get("lon")), qos=1, retain=True)

    def _write_setting(self, path: str, value: Any) -> None:
        if not self.portal_id:
            self.log.warning("Cannot write %s, portalId unknown", path)
            return
        topic = f"W/{self.portal_id}/settings/0/{path}"
        payload = json.dumps({"value": value})
        self.mqtt_client.publish(topic, payload, qos=1, retain=False)
        self.log.info("Write %s <= %s", topic, value)

    def _apply_control(self, should_protect: bool, normal_soc: int, storm_soc: int) -> None:
        if should_protect and not self.protect_active:
            self._write_setting("Settings/CGwacs/BatteryLife/MinimumSocLimit", storm_soc)
            self._write_setting("Settings/CGwacs/BatteryLife/ForceCharge", 1)
            self.protect_active = True
            self.log.warning("Storm protection ENABLED (%s%%)", storm_soc)
        elif (not should_protect) and self.protect_active:
            self._write_setting("Settings/CGwacs/BatteryLife/ForceCharge", 0)
            self._write_setting("Settings/CGwacs/BatteryLife/MinimumSocLimit", normal_soc)
            self.protect_active = False
            self.log.warning("Storm protection DISABLED (%s%%)", normal_soc)

    def evaluate_once(self) -> None:
        now = int(time.time() * 1000)
        normal_soc = clamp_soc_step5(self.config.get("normalMinSoc"), 20)
        storm_soc = clamp_soc_step5(self.config.get("stormMinSoc"), 80)
        hold_ms = int(max(0, int(self.config.get("clearHoldMinutes", 60))) * 60000)

        info: Dict[str, Any] = {
            "timestamp": utc_iso(now),
            "portalId": self.portal_id,
            "control": {"normalMinSoc": normal_soc, "stormMinSoc": storm_soc},
        }
        home_lat, home_lon, home_source = self._home_position()
        info["home"] = {"lat": home_lat, "lon": home_lon, "source": home_source}

        try:
            xml_text = self._fetch_cap_xml()
            parsed_alerts = self._parse_items(xml_text)
            matches = self._matches(parsed_alerts)
            info["matchedCount"] = len(matches)
            info["matchedAlerts"] = [
                {
                    "title": m.title,
                    "event": m.event,
                    "severity": m.severity,
                    "area": m.area,
                    "zoneType": m.zone_type,
                    "startsAt": utc_iso(m.starts_at),
                    "expiresAt": utc_iso(m.expires_at),
                }
                for m in matches[:10]
            ]

            should_protect = len(matches) > 0
            reason = "active-alert" if should_protect else "clear"

            if should_protect:
                furthest_exp = max((m.expires_at or now) for m in matches)
                self.storm_hold_until_ms = furthest_exp + hold_ms
            elif self.storm_hold_until_ms > now:
                should_protect = True
                reason = "hold-timer"
            else:
                self.storm_hold_until_ms = 0

            if self.force_manual is True:
                should_protect = True
                reason = "manual-force-on"
            elif self.force_manual is False:
                should_protect = False
                reason = "manual-force-off"

            info["holdUntil"] = utc_iso(self.storm_hold_until_ms) if self.storm_hold_until_ms else None
            info["reason"] = reason
            info["shouldProtect"] = should_protect

            self._apply_control(should_protect, normal_soc, storm_soc)
            self._publish_state(info)
            self.last_eval = info
        except (urllib.error.URLError, TimeoutError) as e:
            self.log.error("CAP fetch failed: %s", e)
            info["shouldProtect"] = self.protect_active
            info["reason"] = "error-fetch-cap"
            info["error"] = str(e)
            self._publish_state(info)
            self.last_eval = info
        except ET.ParseError as e:
            self.log.error("CAP parse failed: %s", e)
            info["shouldProtect"] = self.protect_active
            info["reason"] = "error-parse-cap"
            info["error"] = str(e)
            self._publish_state(info)
            self.last_eval = info
        except Exception as e:
            self.log.exception("Unhandled evaluate error: %s", e)
            info["shouldProtect"] = self.protect_active
            info["reason"] = "error-unhandled"
            info["error"] = str(e)
            self._publish_state(info)
            self.last_eval = info

    def run(self) -> None:
        mqtt_cfg = self.config["mqtt"]
        self.mqtt_client.connect(mqtt_cfg.get("host", "127.0.0.1"), int(mqtt_cfg.get("port", 1883)), 60)
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

    daemon = StormWatchDaemon(Path(args.config))
    config_log_level = str(daemon.config.get("logLevel", "")).upper().strip()
    final_log_level = config_log_level or str(args.log_level).upper()

    logging.basicConfig(
        level=getattr(logging, final_log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def _sig_handler(signum, frame):
        logging.getLogger("stormwatchd").info("Signal %s received, shutting down", signum)
        daemon.stop()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    daemon.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
