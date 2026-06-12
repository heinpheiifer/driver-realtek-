from statistics import mean, stdev
from math import sqrt

from opentrade.services import BacktestService


def test_serialize_result_includes_profit_factor_and_sharpe():
    svc = BacktestService()

    class FakeTrade:
        def __init__(self, pnl):
            self.pnl = pnl
            self.side = "long"
            self.entry_time = "2024-01-01"
            self.exit_time = "2024-01-02"
            self.entry_price = 1.0
            self.exit_price = 1.01
            self.quantity = 1.0
            self.reason = "tp"
            self.entry_confidence = 0.5
            self.entry_score = 1.0
            self.entry_agents = "a"

    class FakeResult:
        initial_balance = 10000
        ending_balance = 10100
        total_return_pct = 1.0
        max_drawdown_pct = 0.5
        win_rate_pct = 60.0
        trades = [FakeTrade(10), FakeTrade(-5), FakeTrade(8), FakeTrade(-3)]
        trading_days = 4
        trades_per_day = 1.0
        equity_curve = [10000, 10010, 10005, 10013, 10010]

    out = svc._serialize_result(FakeResult())
    assert out["profit_factor"] > 0
    assert out["sharpe"] is not None
