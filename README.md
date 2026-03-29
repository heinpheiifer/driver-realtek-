# Victron Cerbo GX Storm Watch Controller (Node-RED)

This project provides a Node-RED flow for **Victron Cerbo GX / Venus OS** that:

1. Polls a CAP (Common Alerting Protocol) weather-alert feed (default: MetService NZ),
2. Matches alerts against your installation location (GPS or configured home lat/lon),
3. If your location is in an affected zone, automatically:
   - enables ESS force charging, and
   - raises ESS Minimum SOC,
4. Keeps protection active until alerts clear (plus hold timer),
5. Restores normal ESS settings when storm risk has passed.

---

## What is included

- `nodered/victron-storm-watch-flow.json`  
  Import this flow into Node-RED on Cerbo GX.

---

## Requirements

- Victron Cerbo GX (or another GX device) running Venus OS with Node-RED available.
- Local MQTT enabled on GX device.
- ESS configured on MultiPlus/Quattro (for `MinimumSocLimit` and `ForceCharge` settings).
- Internet access from GX to fetch CAP feed.

---

## Install and import

1. Open Node-RED on the Cerbo GX.
2. Menu -> **Import** -> paste the content of:
   - `nodered/victron-storm-watch-flow.json`
3. Deploy the flow.
4. Confirm MQTT broker node points to local broker:
   - Host: `127.0.0.1`
   - Port: `1883`

---

## Configuration (important)

Open function node **`Evaluate CAP alerts + geofence`** and edit `CONFIG`:

- `capFeedUrl`  
  Default is `https://alerts.metservice.com/cap/rss`
- `home.lat` / `home.lon`  
  Set your fixed home coordinates (recommended fallback).
- `useVictronGps`  
  `true` to prefer live GX GPS values if available.
- `homeAreaKeywords`  
  Optional area-name fallback match if CAP geometry is absent.
- `leadMinutes`  
  Start protection before onset/effective by this many minutes.
- `clearHoldMinutes`  
  Keep protection active after alert expiry.
- `normalMinSoc` and `stormMinSoc`  
  SOC values (rounded to nearest 5%).
- `acceptedSeverities` and `stormKeywords`  
  Filter which alerts trigger protection.

---

## How it controls Victron ESS

On storm activation, the flow publishes MQTT writes to:

- `W/<portalId>/settings/0/Settings/CGwacs/BatteryLife/MinimumSocLimit` = `stormMinSoc`
- `W/<portalId>/settings/0/Settings/CGwacs/BatteryLife/ForceCharge` = `1`

On storm clear, it restores:

- `ForceCharge` = `0`
- `MinimumSocLimit` = `normalMinSoc`

`<portalId>` is auto-discovered from incoming Victron telemetry topic `N/<portalId>/...`.

---

## GPS and telemetry topics used

The flow listens for:

- Battery SoC: `N/+/battery/+/Soc`
- GPS candidates:
  - `N/+/system/0/Gps/#`
  - `N/+/gps/+/#`

If live GPS is not found, the flow uses configured `home.lat/lon`.

---

## Notes and safety

- Test in a controlled setting before relying on unattended operation.
- Verify your exact firmware/topic paths; some Venus OS versions differ.
- The flow only writes settings on **state changes** (normal -> protect, protect -> normal).
- Keep a local/remote fallback plan for critical power systems.

