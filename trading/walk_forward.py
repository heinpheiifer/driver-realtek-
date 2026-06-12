from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train: list
    test: list


@dataclass(frozen=True)
class RollingMetrics:
    folds: int
    mean_return_pct: float
    min_return_pct: float
    max_drawdown_pct: float
    mean_win_rate_pct: float
    min_win_rate_pct: float
    total_trades: int
    per_fold: list[dict]


def split_holdout(
    items: Sequence[T],
    train_ratio: float,
    min_train: int,
    min_test: int,
) -> tuple[list[T], list[T]]:
    if not 0.50 <= train_ratio < 0.95:
        raise ValueError("train_ratio must be between 0.50 and 0.95.")
    split_idx = int(len(items) * train_ratio)
    train = list(items[:split_idx])
    test = list(items[split_idx:])
    if len(train) < min_train or len(test) < min_test:
        raise ValueError(
            "Not enough items for holdout split. "
            f"Need train>={min_train}, test>={min_test}, got train={len(train)}, test={len(test)}."
        )
    return train, test


def expanding_walk_forward_windows(
    items: Sequence[T],
    folds: int = 3,
    min_train: int = 250,
    min_test: int = 120,
) -> list[WalkForwardWindow]:
    """Build expanding train windows with sequential out-of-sample test folds."""
    if folds < 1:
        raise ValueError("folds must be >= 1.")
    total = len(items)
    if total < min_train + min_test:
        raise ValueError(
            f"Need at least {min_train + min_test} items for walk-forward, got {total}."
        )

    available_test = total - min_train
    fold_test_size = available_test // folds
    if fold_test_size < min_test:
        raise ValueError(
            f"Not enough data for {folds} folds with min_test={min_test}. "
            f"Available test span={available_test}, fold_test_size={fold_test_size}."
        )

    windows: list[WalkForwardWindow] = []
    for fold_idx in range(folds):
        test_start = min_train + fold_idx * fold_test_size
        test_end = test_start + fold_test_size if fold_idx < folds - 1 else total
        train = list(items[:test_start])
        test = list(items[test_start:test_end])
        if len(train) < min_train or len(test) < min_test:
            continue
        windows.append(WalkForwardWindow(index=fold_idx, train=train, test=test))

    if not windows:
        raise ValueError("Could not build any walk-forward windows with current constraints.")
    return windows


def aggregate_rolling_metrics(per_fold: list[dict]) -> RollingMetrics:
    if not per_fold:
        raise ValueError("per_fold must not be empty.")
    returns = [row["total_return_pct"] for row in per_fold]
    drawdowns = [row["max_drawdown_pct"] for row in per_fold]
    win_rates = [row["win_rate_pct"] for row in per_fold]
    trades = sum(row["trades"] for row in per_fold)
    return RollingMetrics(
        folds=len(per_fold),
        mean_return_pct=sum(returns) / len(returns),
        min_return_pct=min(returns),
        max_drawdown_pct=max(drawdowns),
        mean_win_rate_pct=sum(win_rates) / len(win_rates),
        min_win_rate_pct=min(win_rates),
        total_trades=trades,
        per_fold=per_fold,
    )
