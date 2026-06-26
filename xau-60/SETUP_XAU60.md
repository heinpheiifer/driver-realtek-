# XAU-60 Setup Guide (Standalone app on port 8010)

This repo ([lordgaruda/XAU-60](https://github.com/lordgaruda/XAU-60)) is **MT5 Trading Bot Pro** with the **SMC Scalper** strategy for **XAUUSD** (gold) on **M15**.

The web dashboard runs as its **own app on port 8010**.

---

## Quick install

### Linux Mint / Ubuntu

```bash
cd xau-60
chmod +x scripts/*.sh
./scripts/install-linux.sh
./scripts/start.sh
```

Open: **http://localhost:8010**

### Windows (required for live MT5 trading)

```powershell
cd xau-60
.\scripts\install-windows.ps1
.\scripts\start-windows.ps1
```

Open: **http://localhost:8010**

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
| `./scripts/start.sh` | Web UI on **port 8010** |
| `python main.py --dry-run` | Test MT5 + strategies without orders |
| `python main.py` | CLI live trading loop |
| `python main.py --ui` | Same as start script |

---

## Linux Mint note

The Python `MetaTrader5` package is **Windows-only**. On Mint:

- Dashboard, backtests, and strategy editing work (mock data).
- **Live/paper orders require Windows** with MT5 running, or Wine (not officially supported).

Recommended: run the bot on a **Windows PC/VPS** where MT5 is installed; use Mint to open the dashboard remotely:

```bash
# On Windows machine, bind LAN in start script, then from Mint:
http://WINDOWS_LOCAL_IP:8010
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
ExecStart=/home/YOUR_USER/xau-60/.venv/bin/streamlit run ui/app.py --server.port=8010 --server.address=127.0.0.1
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
| Port 8010 in use | `ss -tlnp \| grep 8010` — stop other app or change port in `.streamlit/config.toml` |
| MT5 connect failed | MT5 must be open; check login/server in `.env` |
| No XAUUSD data | Add symbol to Market Watch; check broker symbol name |
| No trades | Check session hours, strategy enabled, demo account has margin |
| Linux “mock MT5” | Expected — use Windows for real MT5 API |

---

## Risk warning

Trading gold (XAUUSD) is high risk. Use **demo first**, keep risk at **1–2%** per trade, and never trade money you cannot afford to lose.
