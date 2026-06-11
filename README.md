# Victron Cerbo GX Storm Watch (Node-RED)

This repository contains a ready-to-import Node-RED flow that:

- polls a CAP weather alert feed (for example MetService CAP),
- determines your home installation location from Victron GPS (with fixed GPS fallback),
- checks whether your location is inside any active alert polygon,
- forces a storm battery policy on Victron ESS (raise Min SoC + Keep Batteries Charged),
- restores normal settings once alerts are no longer active.

It is designed for Victron Cerbo GX systems running Venus OS Large with Node-RED enabled.

## Files

- `flows/victron-storm-watch-flow.json` - import this into Node-RED.
- `trading/` - swarm scalping research toolkit with paper backtesting, walk-forward validation, and continuous optimization loops (volume profile + smart money model components).
- `opentrade/` - web app for strategy editing, backtesting, and AI optimization (paper/live modes).

## OpenTrade quick start

```bash
pip install -r requirements.txt
python3 -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
python3 -m uvicorn opentrade.main:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080` to edit strategies, run backtests, and start the optimizer.

## What the flow controls

When a matching storm alert is active for your location:

- writes ESS Min SoC to configured storm value (default `80`)
- writes ESS mode to Keep Batteries Charged (`Hub4Mode = 3`)

When no relevant storm alert remains:

- restores ESS Min SoC and Hub4 mode to baseline values (captured from Victron settings topics if available), or configured defaults.

## Victron MQTT topics used

### Read (subscribe)

- `N/+/gps/+/Position/Latitude`
- `N/+/gps/+/Position/Longitude`
- `N/+/settings/0/Settings/CGwacs/BatteryLife/MinimumSocLimit`
- `N/+/settings/0/Settings/CGwacs/Hub4Mode`

### Write (publish)

- `W/<portalId>/settings/0/Settings/CGwacs/BatteryLife/MinimumSocLimit`
- `W/<portalId>/settings/0/Settings/CGwacs/Hub4Mode`

Payload format used for writes:

```json
{"value": 80}
```

## Install on Cerbo GX

1. Ensure Venus OS Large is installed and Node-RED is enabled.
2. Open Node-RED (`http://<cerbo-ip>:1880`).
3. Import `flows/victron-storm-watch-flow.json`.
4. Deploy.
5. Open the **Init storm config** function node and adjust settings:
   - `capFeedUrl`
   - `watchEvents`
   - `minSeverity`
   - `stormMinSoc`
   - optional fixed fallback `homeLat` / `homeLon`
6. Trigger **Init storm config** inject once after edits, then deploy again.

## Important notes

- CAP feeds vary by country/provider. The parser in this flow is intentionally tolerant of namespace/shape differences, but you should validate with your target feed.
- If GPS topics are unavailable, set `homeLat` and `homeLon` in config.
- This flow assumes ESS paths used by Victron systems:
  - `/Settings/CGwacs/BatteryLife/MinimumSocLimit`
  - `/Settings/CGwacs/Hub4Mode`
- If your system maps ESS control differently, update the topic paths in the **Evaluate storm state & create commands** function.

## Suggested commissioning test

1. Temporarily set `homeLat`/`homeLon` to coordinates inside a currently active alert polygon.
2. Verify debug output shows `storm_enter`.
3. Verify Victron settings are written.
4. Set coordinates outside all polygons.
5. Verify debug output shows `storm_exit` and settings are restored.

