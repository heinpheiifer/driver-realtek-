# Swarm Scalping Toolkit (Volume Profile + Smart Money)

This module adds a lightweight research stack for your MT5 strategy design work:

- multi-agent swarm scoring engine
- volume profile mean-reversion context
- smart-money structure break context (BOS + displacement)
- liquidity sweep detection
- trend bias filter
- paper-trading backtest loop for historical candles

## Files

- `trading/swarm.py` - agents + `SwarmCoordinator`
- `trading/backtest.py` - paper-trading execution and metrics
- `trading/data.py` - OHLCV CSV loader
- `trading/run_backtest.py` - CLI runner

## CSV format

CSV must include columns (case-insensitive aliases supported):

- timestamp (`timestamp`, `time`, `date`)
- open (`open`, `o`)
- high (`high`, `h`)
- low (`low`, `l`)
- close (`close`, `c`)
- volume (`volume`, `vol`, `tick_volume`)

## Quick run

From repo root:

```bash
python -m trading.run_backtest --csv /path/to/eurusd_m1.csv --save-trades /tmp/swarm_trades.csv
```

## Notes

- This is a research-grade paper-trading harness, not broker execution code.
- It is designed to make strategy iteration fast before MT5 live EA wiring.
- Spread/slippage, ATR stops, and reward/risk are configurable from CLI.
