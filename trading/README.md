# Swarm Scalping Toolkit (Volume Profile + Smart Money)

This module adds a lightweight research stack for your MT5 strategy design work:

- multi-agent swarm scoring engine
- volume profile mean-reversion context
- smart-money structure break context (BOS + displacement)
- liquidity sweep detection
- trend bias filter
- paper-trading backtest loop for historical candles
- parameter sweep mode for quick strategy optimization
- MT5-friendly signal export format (OPEN/CLOSE rows)

## Files

- `trading/swarm.py` - agents + `SwarmCoordinator`
- `trading/backtest.py` - paper-trading execution and metrics
- `trading/data.py` - OHLCV CSV loader
- `trading/continuous_research.py` - autonomous optimize/validate loop
- `trading/walk_forward.py` - holdout + rolling expanding walk-forward windows
- `trading/fetch_data.py` - realistic OHLCV sample generator
- `trading/export_mt5.py` - champion config to MT5 EA scaffold

## CSV format

CSV must include columns (case-insensitive aliases supported):

- timestamp (`timestamp`, `time`, `date`)
- open (`open`, `o`)
- high (`high`, `h`)
- low (`low`, `l`)
- close (`close`, `c`)
- volume (`volume`, `vol`, `tick_volume`)

## Generate sample data

If you do not have a CSV yet:

```bash
python -m trading.fetch_data --output trading_data/eurusd_m1.csv --bars 8000
```

## Quick run

From repo root:

```bash
python -m trading.run_backtest --csv /path/to/eurusd_m1.csv --save-trades /tmp/swarm_trades.csv
```

With MT5 signal export:

```bash
python -m trading.run_backtest \
  --csv /path/to/eurusd_m1.csv \
  --symbol EURUSD \
  --timeframe M1 \
  --save-mt5-signals /tmp/mt5_signals.csv
```

Run optimizer sweep:

```bash
python -m trading.run_backtest \
  --mode sweep \
  --csv /path/to/eurusd_m1.csv \
  --save-sweep /tmp/sweep_results.csv
```

Walk-forward (single config):

```bash
python -m trading.run_backtest \
  --mode single \
  --walk-forward \
  --wf-train-ratio 0.70 \
  --csv /path/to/eurusd_m1.csv \
  --save-trades /tmp/wf_trades.csv
```

Walk-forward (sweep optimize on train, validate on test):

```bash
python -m trading.run_backtest \
  --mode sweep \
  --walk-forward \
  --wf-train-ratio 0.70 \
  --csv /path/to/eurusd_m1.csv \
  --save-sweep /tmp/wf_sweep_results.csv
```

## Continuous optimize/backtest/forward-test loop

Use the autonomous runner to repeatedly optimize and validate until your profitability gate is hit:

```bash
python -m trading.continuous_research \
  --csv /path/to/eurusd_m1.csv \
  --output-dir trading_runs/continuous \
  --walk-forward \
  --wf-train-ratio 0.70 \
  --rolling-wf-folds 3 \
  --target-test-return 1.0 \
  --max-test-drawdown 8.0 \
  --min-test-win-rate 45 \
  --min-test-trades 20 \
  --interval-seconds 90
```

Run forever (do not stop on first success):

```bash
python -m trading.continuous_research \
  --csv /path/to/eurusd_m1.csv \
  --output-dir trading_runs/continuous \
  --max-iterations 0 \
  --no-stop-on-success
```

In long sessions, run it inside tmux:

```bash
tmux new -s swarm-loop
python -m trading.continuous_research --csv /path/to/eurusd_m1.csv
```

Artifacts written each iteration:

- `iteration_XXXXX.csv` full ranked parameter table
- `iteration_XXXXX.best.json` best row snapshot
- `history.csv` best-by-iteration log
- `champion_config.json` latest best config
- `SwarmChampionEA.mq5` MT5 EA scaffold from champion config
- `champion_mt5_signals.csv` forward/test segment signals
- `top_candidates.json` latest top-N list
- `champion_report.json` when profitability gate is met

## MT5 signal export columns

`--save-mt5-signals` writes CSV rows with:

- `timestamp`
- `symbol`
- `timeframe`
- `action` (`OPEN` / `CLOSE`)
- `side` (`LONG` / `SHORT`)
- `price`
- `quantity`
- `confidence`
- `score`
- `reason`
- `agents`

## Notes

- This is a research-grade paper-trading harness, not broker execution code.
- It is designed to make strategy iteration fast before MT5 live EA wiring.
- Spread/slippage, ATR stops, and reward/risk are configurable from CLI.
- Sweep mode currently optimizes over risk, stop multiple, reward/risk, confidence, and SMC/VP windows.
- Walk-forward mode uses a time-based split and avoids selecting parameters on the forward segment.
- Rolling walk-forward (`--rolling-wf-folds`) validates each candidate across multiple sequential out-of-sample folds.
- Champion mutation (`--mutate-champion`) explores neighborhoods around the prior best config each iteration.
- Profitability is never guaranteed in real markets, even when backtest and forward-test metrics improve.
