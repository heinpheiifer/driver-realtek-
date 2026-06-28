# TradeMaster launcher

**TradeMaster** lives at `~/TradeMaster` on heinz-Predator (separate from OpenTrader / XAU-60).

| Item | Detail |
|------|--------|
| **Path** | `~/TradeMaster` |
| **Type** | Deep RL research (DeepScalper, etc.) — **not live trading** |
| **Your runner** | `scripts/auto_tune_deepscalper.py` (background tuning) |
| **UI** | Jupyter Lab — tutorials in `tutorial/` |

## Open TradeMaster

```bash
cd ~/tradenator-xau60
bash tools/trademaster/open-trademaster.sh
```

Then in your browser: **http://127.0.0.1:8888/lab**

Start with notebooks:
- `tutorial/Tutorial2_DeepScalper.ipynb` — DeepScalper intraday crypto
- `tutorial/Tutorial7_auto_tuning.ipynb` — Optuna hyperparameter tuning

## Check if auto-tune is running

```bash
pgrep -af "auto_tune_deepscalper"
```

## Docs

https://trademaster.readthedocs.io/
