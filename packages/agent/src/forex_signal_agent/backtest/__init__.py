"""Backtest module for strategy validation.

Contains:
- BacktestEngine: Trade simulation engine
- BacktestConfig: Configuration for backtest runs
- BacktestResult: Metrics and trade history
"""

from .engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    Trade,
    TradeDirection,
    TradeStatus,
)

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "Trade",
    "TradeDirection",
    "TradeStatus",
]
