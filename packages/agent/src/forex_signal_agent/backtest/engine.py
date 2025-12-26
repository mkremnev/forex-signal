"""Backtest engine for strategy validation.

Simulates trades based on analyzer signals and computes
performance metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from forex_signal_agent.analysis import ProbabilisticAnalyzer

logger = logging.getLogger(__name__)


class TradeStatus(str, Enum):
    """Status of a trade."""

    OPEN = "open"
    CLOSED_TP = "closed_tp"  # Closed at take profit
    CLOSED_SL = "closed_sl"  # Closed at stop loss
    CLOSED_SIGNAL = "closed_signal"  # Closed on opposite signal
    CLOSED_END = "closed_end"  # Closed at end of cycle


class TradeDirection(str, Enum):
    """Direction of a trade."""

    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """Represents a single trade.

    Attributes:
        symbol: Instrument symbol
        direction: Trade direction (long/short)
        entry_price: Entry price
        entry_time: Entry timestamp
        position_size: Position size in units
        status: Current trade status
        exit_price: Exit price (if closed)
        exit_time: Exit timestamp (if closed)
        pnl: Profit/loss (if closed)
        stop_loss: Stop loss price
        take_profit: Take profit price
    """

    symbol: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    position_size: float
    status: TradeStatus = TradeStatus.OPEN
    exit_price: float | None = None
    exit_time: datetime | None = None
    pnl: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    def close(
        self,
        exit_price: float,
        exit_time: datetime,
        status: TradeStatus,
        slippage: float = 0.0,
        commission: float = 0.0,
    ) -> None:
        """Close the trade.

        Args:
            exit_price: Price at exit
            exit_time: Time of exit
            status: Reason for closing
            slippage: Slippage cost as decimal
            commission: Commission cost as decimal
        """
        self.exit_price = exit_price * (1 - slippage if self.direction == TradeDirection.LONG else 1 + slippage)
        self.exit_time = exit_time
        self.status = status

        # Calculate P&L
        if self.direction == TradeDirection.LONG:
            raw_pnl = (self.exit_price - self.entry_price) * self.position_size
        else:
            raw_pnl = (self.entry_price - self.exit_price) * self.position_size

        # Apply commission
        trade_value = self.entry_price * self.position_size
        commission_cost = trade_value * commission * 2  # Entry + exit

        self.pnl = raw_pnl - commission_cost

    @property
    def is_open(self) -> bool:
        """Check if trade is open."""
        return self.status == TradeStatus.OPEN

    @property
    def is_winner(self) -> bool:
        """Check if trade is a winner."""
        return self.pnl > 0


@dataclass
class BacktestConfig:
    """Configuration for backtest runs.

    Attributes:
        initial_capital: Starting capital
        position_size_pct: Position size as % of capital
        stop_loss_pct: Stop loss as % from entry
        take_profit_pct: Take profit as % from entry
        max_open_trades: Maximum concurrent open trades
        slippage_pct: Slippage as decimal (0.001 = 0.1%)
        commission_pct: Commission as decimal (0.001 = 0.1%)
    """

    initial_capital: float = 10000.0
    position_size_pct: float = 0.02  # 2% per trade
    stop_loss_pct: float = 0.02  # 2%
    take_profit_pct: float = 0.04  # 4%
    max_open_trades: int = 3
    slippage_pct: float = 0.001  # 0.1%
    commission_pct: float = 0.001  # 0.1%


@dataclass
class BacktestResult:
    """Results from a backtest run.

    Attributes:
        trades: List of all trades
        total_pnl: Total profit/loss
        win_rate: Winning trade percentage
        profit_factor: Gross profit / gross loss
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Risk-adjusted return
        total_trades: Number of trades executed
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        equity_curve: Equity over time
    """

    trades: list[Trade]
    total_pnl: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    equity_curve: list[float] = field(default_factory=list)


class BacktestEngine:
    """Engine for backtesting trading strategies.

    Simulates trades based on analyzer signals and computes
    comprehensive performance metrics.

    Example:
        engine = BacktestEngine(config)

        result = engine.run(
            historical_data=data,
            analyzer=probabilistic_analyzer,
            timeframe="4h",
        )

        print(f"Win Rate: {result.win_rate:.1%}")
        print(f"Profit Factor: {result.profit_factor:.2f}")
    """

    def __init__(self, config: BacktestConfig | None = None):
        """Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self._config = config or BacktestConfig()
        self._trades: list[Trade] = []
        self._open_trades: dict[str, Trade] = {}
        self._equity: float = self._config.initial_capital
        self._equity_curve: list[float] = []

    @property
    def config(self) -> BacktestConfig:
        """Get backtest configuration."""
        return self._config

    def run(
        self,
        historical_data: dict[str, pd.DataFrame],
        analyzer: ProbabilisticAnalyzer,
        timeframe: str = "4h",
    ) -> BacktestResult:
        """Run backtest simulation.

        Args:
            historical_data: Dictionary mapping symbol to OHLCV DataFrame
            analyzer: Probabilistic analyzer for signal generation
            timeframe: Analysis timeframe

        Returns:
            BacktestResult with trades and metrics
        """
        self._reset()

        if not historical_data:
            logger.warning("No historical data provided")
            return self._compute_results()

        # Get all timestamps
        all_timestamps = self._get_aligned_timestamps(historical_data)

        if not all_timestamps:
            logger.warning("No aligned timestamps found")
            return self._compute_results()

        logger.info(f"Running backtest with {len(all_timestamps)} bars")

        # Update correlations once with all data
        analyzer.update_correlations(historical_data)

        # Simulate bar by bar
        for i, timestamp in enumerate(all_timestamps):
            # Get data up to current bar
            current_data = self._get_data_up_to(historical_data, timestamp)

            # Check stop loss and take profit for open trades
            self._check_sl_tp(current_data, timestamp)

            # Generate signals
            signals = analyzer.analyze_batch(current_data, timeframe)

            # Process signals
            for symbol, result in signals.items():
                if result.probability and result.probability.is_actionable:
                    self._process_signal(
                        symbol=symbol,
                        direction=result.probability.direction,
                        current_data=current_data,
                        timestamp=timestamp,
                    )

            # Record equity
            self._update_equity(current_data)
            self._equity_curve.append(self._equity)

        # Close remaining trades at end
        self._close_all_trades(historical_data, all_timestamps[-1] if all_timestamps else None)

        return self._compute_results()

    def _reset(self) -> None:
        """Reset engine state for new run."""
        self._trades = []
        self._open_trades = {}
        self._equity = self._config.initial_capital
        self._equity_curve = [self._equity]

    def _get_aligned_timestamps(
        self,
        data: dict[str, pd.DataFrame],
    ) -> list[datetime]:
        """Get timestamps aligned across all symbols.

        Args:
            data: Dictionary of DataFrames

        Returns:
            Sorted list of common timestamps
        """
        if not data:
            return []

        # Get intersection of all timestamps
        common_idx = None
        for df in data.values():
            if df.empty:
                continue
            if common_idx is None:
                common_idx = set(df.index)
            else:
                common_idx &= set(df.index)

        if not common_idx:
            return []

        return sorted(common_idx)

    def _get_data_up_to(
        self,
        data: dict[str, pd.DataFrame],
        timestamp: datetime,
    ) -> dict[str, pd.DataFrame]:
        """Get data up to a specific timestamp.

        Args:
            data: Full historical data
            timestamp: Cutoff timestamp

        Returns:
            Dictionary of truncated DataFrames
        """
        result = {}
        for symbol, df in data.items():
            result[symbol] = df[df.index <= timestamp]
        return result

    def _check_sl_tp(
        self,
        current_data: dict[str, pd.DataFrame],
        timestamp: datetime,
    ) -> None:
        """Check stop loss and take profit for open trades.

        Args:
            current_data: Current market data
            timestamp: Current timestamp
        """
        trades_to_close: list[tuple[str, TradeStatus]] = []

        for symbol, trade in self._open_trades.items():
            if symbol not in current_data or current_data[symbol].empty:
                continue

            df = current_data[symbol]
            high = df["high"].iloc[-1]
            low = df["low"].iloc[-1]

            # Check stop loss
            if trade.direction == TradeDirection.LONG:
                if low <= trade.stop_loss:
                    trades_to_close.append((symbol, TradeStatus.CLOSED_SL))
                    continue
                if high >= trade.take_profit:
                    trades_to_close.append((symbol, TradeStatus.CLOSED_TP))
                    continue
            else:  # SHORT
                if high >= trade.stop_loss:
                    trades_to_close.append((symbol, TradeStatus.CLOSED_SL))
                    continue
                if low <= trade.take_profit:
                    trades_to_close.append((symbol, TradeStatus.CLOSED_TP))
                    continue

        # Close trades
        for symbol, status in trades_to_close:
            trade = self._open_trades[symbol]
            df = current_data[symbol]

            if status == TradeStatus.CLOSED_SL:
                exit_price = trade.stop_loss
            else:  # TP
                exit_price = trade.take_profit

            trade.close(
                exit_price=exit_price,
                exit_time=timestamp,
                status=status,
                slippage=self._config.slippage_pct,
                commission=self._config.commission_pct,
            )

            self._trades.append(trade)
            del self._open_trades[symbol]
            logger.debug(f"Closed {symbol} at {status.value}: PnL={trade.pnl:.2f}")

    def _process_signal(
        self,
        symbol: str,
        direction,  # Direction enum
        current_data: dict[str, pd.DataFrame],
        timestamp: datetime,
    ) -> None:
        """Process an actionable signal.

        Args:
            symbol: Instrument symbol
            direction: Signal direction
            current_data: Current market data
            timestamp: Signal timestamp
        """
        from forex_signal_agent.analysis import Direction

        # Skip consolidation signals
        if direction == Direction.CONSOLIDATION:
            return

        # Check if we have an open trade for this symbol
        if symbol in self._open_trades:
            existing_trade = self._open_trades[symbol]

            # Check if opposite signal
            is_opposite = (
                (direction == Direction.UPWARD and existing_trade.direction == TradeDirection.SHORT)
                or (direction == Direction.DOWNWARD and existing_trade.direction == TradeDirection.LONG)
            )

            if is_opposite:
                # Close on opposite signal
                df = current_data[symbol]
                exit_price = df["close"].iloc[-1]

                existing_trade.close(
                    exit_price=exit_price,
                    exit_time=timestamp,
                    status=TradeStatus.CLOSED_SIGNAL,
                    slippage=self._config.slippage_pct,
                    commission=self._config.commission_pct,
                )

                self._trades.append(existing_trade)
                del self._open_trades[symbol]
                logger.debug(f"Closed {symbol} on opposite signal: PnL={existing_trade.pnl:.2f}")
            else:
                # Same direction, keep existing trade
                return

        # Check max open trades constraint
        if len(self._open_trades) >= self._config.max_open_trades:
            return

        # Open new trade
        if symbol not in current_data or current_data[symbol].empty:
            return

        df = current_data[symbol]
        entry_price = df["close"].iloc[-1]

        trade_direction = (
            TradeDirection.LONG if direction == Direction.UPWARD else TradeDirection.SHORT
        )

        # Calculate position size
        position_value = self._equity * self._config.position_size_pct
        position_size = position_value / entry_price

        # Calculate SL/TP
        if trade_direction == TradeDirection.LONG:
            stop_loss = entry_price * (1 - self._config.stop_loss_pct)
            take_profit = entry_price * (1 + self._config.take_profit_pct)
        else:
            stop_loss = entry_price * (1 + self._config.stop_loss_pct)
            take_profit = entry_price * (1 - self._config.take_profit_pct)

        # Apply entry slippage
        slipped_entry = entry_price * (
            1 + self._config.slippage_pct if trade_direction == TradeDirection.LONG
            else 1 - self._config.slippage_pct
        )

        trade = Trade(
            symbol=symbol,
            direction=trade_direction,
            entry_price=slipped_entry,
            entry_time=timestamp,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self._open_trades[symbol] = trade
        logger.debug(f"Opened {trade_direction.value} {symbol} at {slipped_entry:.5f}")

    def _update_equity(
        self,
        current_data: dict[str, pd.DataFrame],
    ) -> None:
        """Update equity based on open positions.

        Args:
            current_data: Current market data
        """
        # Start with closed trade P&L
        closed_pnl = sum(t.pnl for t in self._trades)

        # Add unrealized P&L from open trades
        unrealized_pnl = 0.0
        for symbol, trade in self._open_trades.items():
            if symbol not in current_data or current_data[symbol].empty:
                continue

            current_price = current_data[symbol]["close"].iloc[-1]

            if trade.direction == TradeDirection.LONG:
                unrealized_pnl += (current_price - trade.entry_price) * trade.position_size
            else:
                unrealized_pnl += (trade.entry_price - current_price) * trade.position_size

        self._equity = self._config.initial_capital + closed_pnl + unrealized_pnl

    def _close_all_trades(
        self,
        data: dict[str, pd.DataFrame],
        timestamp: datetime | None,
    ) -> None:
        """Close all remaining open trades at end of cycle.

        Args:
            data: Historical data
            timestamp: Final timestamp
        """
        if not timestamp:
            return

        for symbol, trade in list(self._open_trades.items()):
            if symbol not in data or data[symbol].empty:
                continue

            exit_price = data[symbol]["close"].iloc[-1]

            trade.close(
                exit_price=exit_price,
                exit_time=timestamp,
                status=TradeStatus.CLOSED_END,
                slippage=self._config.slippage_pct,
                commission=self._config.commission_pct,
            )

            self._trades.append(trade)
            logger.debug(f"Closed {symbol} at end: PnL={trade.pnl:.2f}")

        self._open_trades.clear()

    def _compute_results(self) -> BacktestResult:
        """Compute final backtest metrics.

        Returns:
            BacktestResult with all metrics
        """
        if not self._trades:
            return BacktestResult(
                trades=[],
                total_pnl=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                equity_curve=self._equity_curve,
            )

        # Basic counts
        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.is_winner)
        losing_trades = total_trades - winning_trades

        # Win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # Total P&L
        total_pnl = sum(t.pnl for t in self._trades)

        # Profit factor
        gross_profit = sum(t.pnl for t in self._trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self._trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio()

        return BacktestResult(
            trades=self._trades,
            total_pnl=total_pnl,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            equity_curve=self._equity_curve,
        )

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve.

        Returns:
            Maximum drawdown as percentage
        """
        if len(self._equity_curve) < 2:
            return 0.0

        equity = np.array(self._equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak

        return float(np.max(drawdown))

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from returns.

        Returns:
            Annualized Sharpe ratio
        """
        if len(self._equity_curve) < 2:
            return 0.0

        equity = np.array(self._equity_curve)
        returns = np.diff(equity) / equity[:-1]

        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualize (assume 4h bars, ~6 per day, ~252 trading days)
        periods_per_year = 6 * 252
        sharpe = (mean_return / std_return) * np.sqrt(periods_per_year)

        return float(sharpe)
