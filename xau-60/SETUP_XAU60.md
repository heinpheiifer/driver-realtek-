# XAU-60 Setup Guide (Standalone app on port 8020)

This repo ([lordgaruda/XAU-60](https://github.com/lordgaruda/XAU-60)) is **MT5 Trading Bot Pro** with the **SMC Scalper** strategy for **XAUUSD** (gold) on **M15**.

The web dashboard runs on **port 8020** so it does not conflict with **Tradenator on 8010**.

---

## Quick install

### Linux Mint / Ubuntu

```bash
cd xau-60
chmod +x scripts/*.sh
./scripts/install-linux.sh
./scripts/start.sh
```

Open: **http://localhost:8020**

### Windows (required for live MT5 trading)

```powershell
cd xau-60
.\scripts\install-windows.ps1
.\scripts\start-windows.ps1
```

Open: **http://localhost:8020**

---

## MT5 terminal setup (Windows)

1. Install [MetaTrader 5](https://www.metatrader5.com/) from your broker.
2. Log into a **demo** account first.
3. In MT5: **Tools → Options → Expert Advisors**
   - Allow algorithmic trading
   - Allow DLL imports (if prompted)
4. Keep MT5 **open and logged in** while the bot runs.
5. Ensure **XAUUSD** (or your broker’s gold symbol, e.g. `XAUUSD.a`) is in Market Watch.

---

## Configure credentials

Edit `.env` in the project folder:

```bash
MT5_LOGIN=12345678
MT5_PASSWORD=your_demo_password
MT5_SERVER=YourBroker-Demo
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe   # Windows only

MAX_RISK_PER_TRADE=2.0
MAX_DAILY_LOSS=5.0
DEFAULT_LOT_SIZE=0.01
```

Test connection (Windows, MT5 open):

```bash
python main.py --dry-run
```

---

## SMC Scalper (XAU-60 strategy)

Configured in `config/strategies/smc_scalper.yaml`:

| Setting | Default |
|---------|---------|
| Symbol | XAUUSD |
| Timeframe | M15 |
| Magic number | 789123 |
| Risk per trade | 2% |
| Session | 08:00–18:00, no Friday |
| Trailing stop | 50 pips |

Enable/disable in the **Strategies** page in the dashboard.

---

## Run modes

| Command | Purpose |
|---------|---------|
| `./scripts/start.sh` | Web UI on **port 8020** |
| `python main.py --dry-run` | Test MT5 + strategies without orders |
| `python main.py` | CLI live trading loop |
| `python main.py --ui` | Same as start script |

---

## Linux Mint note

The Python `MetaTrader5` package is **Windows-only**. On Mint you have two options:

### Option A — MT5 bridge (recommended for Linux dashboard)

Run the UI on Mint but connect to **real BlackBull balance** via a Windows PC on your LAN:

1. **On Windows** (where MT5 + BlackBull are installed):
   ```powershell
   cd xau-60
   .\scripts\start-bridge.ps1
   ```
   Keep MetaTrader 5 open. Note your Windows LAN IP (e.g. `192.168.1.50`).

2. **On Linux Mint**, edit `xau-60/.env`:
   ```bash
   MT5_BRIDGE_URL=http://192.168.1.50:8021
   MT5_BRIDGE_TOKEN=choose-a-secret-token   # same token on Windows if set
   ```

3. Test and start:
   ```bash
   python scripts/check-bridge.py
   python scripts/check-balance.py
   ./scripts/start.sh
   ```

4. Allow **port 8021** through Windows Firewall for your LAN.

The dashboard will show **Live data via MT5 bridge** and your real balance.

### Option B — UI preview only (no bridge)

- Dashboard, backtests, and strategy editing work with **mock data**.
- No real balance or live orders until you use the bridge or run on Windows.

### Option C — Run everything on Windows

Run the bot on a **Windows PC/VPS** where MT5 is installed; open the dashboard from Mint:

```bash
# On Windows machine, then from Mint:
http://WINDOWS_LOCAL_IP:8020
```

---

## systemd service (optional, Linux)

```ini
# /etc/systemd/system/xau60.service
[Unit]
Description=XAU-60 MT5 Trading Bot UI
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/xau-60
ExecStart=/home/YOUR_USER/xau-60/.venv/bin/streamlit run ui/app.py --server.port=8020 --server.address=127.0.0.1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now xau60
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8020 in use | Change port in `.streamlit/config.toml` and `scripts/start.sh` |
| Tradenator on 8010 | Leave 8010 alone — XAU-60 uses 8020 by default |
| MT5 connect failed | MT5 must be open; check login/server in `.env` |
| No XAUUSD data | Add symbol to Market Watch; check broker symbol name |
| No trades | Check session hours, strategy enabled, demo account has margin |
| Linux “mock MT5” | Set `MT5_BRIDGE_URL` in `.env` and run `start-bridge.ps1` on Windows |
| Bridge unreachable | Windows firewall port 8021; MT5 open; correct IP in `.env` |

---

## Risk warning

Trading gold (XAUUSD) is high risk. Use **demo first**, keep risk at **1–2%** per trade, and never trade money you cannot afford to lose.
