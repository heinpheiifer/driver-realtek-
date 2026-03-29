# Victron Cerbo GX Storm Watch Controller

This repository now includes **two implementations**:

1. **Python daemon for Venus OS** (recommended for always-on control)
2. **Node-RED flows**:
   - headless controller flow
   - full dashboard flow (map + settings + manual override)

Both options do the same core job:

- Poll CAP weather alerts (default MetService NZ),
- match alerts to your installation location (GPS or fixed home lat/lon),
- when you are in an affected zone:
  - set ESS `ForceCharge = 1`
  - raise `MinimumSocLimit` to storm reserve,
- when alerts pass (and hold timer expires):
  - set `ForceCharge = 0`
  - restore normal `MinimumSocLimit`.

---

## Included files

### Python (Venus OS service)

- `stormwatch-python/stormwatchd.py` - main daemon
- `stormwatch-python/config.example.json` - editable config
- `stormwatch-python/install.sh` - installs to `/data/stormwatch` + autostart hook
- `stormwatch-python/start-stormwatch.sh` - runner script

### Node-RED

- `nodered/victron-storm-watch-flow.json` - controller-only flow
- `nodered/victron-storm-watch-dashboard-flow.json` - dashboard flow

---

## Requirements

- Victron Cerbo GX / Venus OS
- Local MQTT enabled
- ESS configured on MultiPlus/Quattro
- Internet access for CAP feed

For dashboard flow:

- Node-RED dashboard packages compatible with your Node-RED install.
- For map display, install `node-red-contrib-web-worldmap`.

---

## Option A: Python daemon on Venus OS (recommended)

### Install

Copy `stormwatch-python` to Cerbo and run:

```sh
cd /path/to/stormwatch-python
sh install.sh
```

This installs to:

- `/data/stormwatch/stormwatchd.py`
- `/data/stormwatch/config.json` (created from example on first install)
- `/data/stormwatch/start-stormwatch.sh`
- `/data/rc.local.d/stormwatch.sh` (autostart hook)

### Configure

Edit:

```sh
/data/stormwatch/config.json
```

Important keys:

- `capFeedUrl`
- `home.lat`, `home.lon`
- `useVictronGps`
- `leadMinutes`, `clearHoldMinutes`
- `normalMinSoc`, `stormMinSoc`
- `acceptedSeverities`, `stormKeywords`
- `stateTopicBase` (status publish root)
- `commandTopic` (manual command input topic)

### Start now

```sh
/data/stormwatch/start-stormwatch.sh
```

### Optional runtime commands (MQTT)

Publish JSON to `commandTopic`:

- Force on:
  - `{"action":"forceProtect","enabled":true}`
- Force off:
  - `{"action":"forceProtect","enabled":false}`
- Back to auto:
  - `{"action":"clearManualOverride"}`
- Trigger immediate evaluation:
  - `{"action":"runNow"}`

Status is retained under `stateTopicBase` (for dashboards/monitoring).

---

## Option B: Node-RED dashboard flow

Import:

- `nodered/victron-storm-watch-dashboard-flow.json`

Dashboard includes:

- Status text and active/hold state
- Home GPS display
- Last alert summary
- Manual override buttons (AUTO, FORCE ON, FORCE OFF)
- Runtime settings controls:
  - Normal Min SOC
  - Storm Min SOC
  - Lead minutes
  - Hold minutes
- Map payload output for worldmap node (`msg.payload.markers` and `msg.payload.polygons`)

Notes:

- Map requires worldmap node installed.
- Settings panel updates runtime config in flow context.

---

## Option C: Node-RED headless controller flow

Import:

- `nodered/victron-storm-watch-flow.json`

This is lighter and uses debug output only.

---

## Victron ESS control topics used

Writes:

- `W/<portalId>/settings/0/Settings/CGwacs/BatteryLife/MinimumSocLimit`
- `W/<portalId>/settings/0/Settings/CGwacs/BatteryLife/ForceCharge`

`<portalId>` is auto-discovered from `N/<portalId>/...` telemetry where possible.

Telemetry listeners used:

- `N/+/battery/+/Soc`
- `N/+/system/0/Gps/#`
- `N/+/gps/+/#`

---

## Safety notes

- Validate topic paths on your Venus OS version before production use.
- Test with manual override and simulated CAP conditions first.
- Keep a fallback procedure for critical power systems.
- This logic writes settings on state transitions to avoid command spam.

