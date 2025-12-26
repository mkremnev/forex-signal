"""Tests for backtest engine."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from forex_signal_agent.analysis import Direction, ProbabilisticAnalyzer
from forex_signal_agent.backtest import (
    BacktestConfig,
    BacktestEngine,
    Trade,
    TradeDirection,
    TradeStatus,
)


@pytest.fixture
def sample_data() -> dict[str, pd.DataFrame]:
    """Create sample OHLCV data."""
    dates = pd.date_range(
        start="2024-01-01",
        periods=50,
        freq="4h",
        tz="UTC",
    )

    # Create upward trending data
    base_price = 1.1000
    data = {
        "open": [base_price + i * 0.001 for i in range(50)],
        "high": [base_price + i * 0.001 + 0.002 for i in range(50)],
        "low": [base_price + i * 0.001 - 0.001 for i in range(50)],
        "close": [base_price + i * 0.001 + 0.0005 for i in range(50)],
        "volume": [1000] * 50,
    }

    return {"EUR/USD": pd.DataFrame(data, index=dates)}


@pytest.fixture
def config() -> BacktestConfig:
    """Create test config."""
    return BacktestConfig(
        initial_capital=10000.0,
        position_size_pct=0.02,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_open_trades=3,
        slippage_pct=0.001,
        commission_pct=0.001,
    )


class TestTrade:
    """Tests for Trade class."""

    def test_trade_creation(self) -> None:
        """Test creating a trade."""
        trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.LONG,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=1000,
        )

        assert trade.symbol == "EUR/USD"
        assert trade.direction == TradeDirection.LONG
        assert trade.is_open
        assert not trade.is_winner

    def test_trade_close_long_profit(self) -> None:
        """Test closing a profitable long trade."""
        trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.LONG,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=1000,
        )

        trade.close(
            exit_price=1.1100,
            exit_time=datetime.now(timezone.utc),
            status=TradeStatus.CLOSED_TP,
            slippage=0.0,
            commission=0.0,
        )

        assert not trade.is_open
        assert trade.is_winner
        assert trade.pnl > 0
        assert trade.status == TradeStatus.CLOSED_TP

    def test_trade_close_short_profit(self) -> None:
        """Test closing a profitable short trade."""
        trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.SHORT,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=1000,
        )

        trade.close(
            exit_price=1.0900,
            exit_time=datetime.now(timezone.utc),
            status=TradeStatus.CLOSED_TP,
            slippage=0.0,
            commission=0.0,
        )

        assert trade.is_winner
        assert trade.pnl > 0

    def test_trade_close_with_commission(self) -> None:
        """Test closing with commission applied."""
        trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.LONG,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=1000,
        )

        trade.close(
            exit_price=1.1010,
            exit_time=datetime.now(timezone.utc),
            status=TradeStatus.CLOSED_TP,
            slippage=0.0,
            commission=0.001,  # 0.1%
        )

        # P&L should be reduced by commission
        raw_pnl = (1.1010 - 1.1000) * 1000  # 1.0
        commission_cost = 1.1000 * 1000 * 0.001 * 2  # 2.2
        expected_pnl = raw_pnl - commission_cost

        assert abs(trade.pnl - expected_pnl) < 0.01


class TestBacktestConfig:
    """Tests for BacktestConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = BacktestConfig()

        assert config.initial_capital == 10000.0
        assert config.position_size_pct == 0.02
        assert config.stop_loss_pct == 0.02
        assert config.take_profit_pct == 0.04
        assert config.max_open_trades == 3

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = BacktestConfig(
            initial_capital=50000.0,
            position_size_pct=0.05,
            max_open_trades=5,
        )

        assert config.initial_capital == 50000.0
        assert config.position_size_pct == 0.05
        assert config.max_open_trades == 5


class TestBacktestEngine:
    """Tests for BacktestEngine."""

    def test_engine_creation(self, config: BacktestConfig) -> None:
        """Test creating engine."""
        engine = BacktestEngine(config)

        assert engine.config == config

    def test_empty_data_returns_empty_result(self, config: BacktestConfig) -> None:
        """Test running with empty data."""
        engine = BacktestEngine(config)
        analyzer = MagicMock(spec=ProbabilisticAnalyzer)

        result = engine.run({}, analyzer, "4h")

        assert result.total_trades == 0
        assert result.total_pnl == 0.0
        assert result.win_rate == 0.0

    def test_run_with_no_signals(
        self,
        config: BacktestConfig,
        sample_data: dict[str, pd.DataFrame],
    ) -> None:
        """Test running when analyzer produces no actionable signals."""
        engine = BacktestEngine(config)

        # Mock analyzer that returns non-actionable results
        analyzer = MagicMock(spec=ProbabilisticAnalyzer)
        analyzer.update_correlations.return_value = pd.DataFrame()

        mock_result = MagicMock()
        mock_result.probability = MagicMock()
        mock_result.probability.is_actionable = False

        analyzer.analyze_batch.return_value = {"EUR/USD": mock_result}

        result = engine.run(sample_data, analyzer, "4h")

        assert result.total_trades == 0

    def test_aligned_timestamps(
        self,
        config: BacktestConfig,
    ) -> None:
        """Test timestamp alignment."""
        engine = BacktestEngine(config)

        dates1 = pd.date_range("2024-01-01", periods=10, freq="4h", tz="UTC")
        dates2 = pd.date_range("2024-01-01 04:00", periods=8, freq="4h", tz="UTC")

        data = {
            "SYM1": pd.DataFrame({"close": [1.0] * 10}, index=dates1),
            "SYM2": pd.DataFrame({"close": [1.0] * 8}, index=dates2),
        }

        timestamps = engine._get_aligned_timestamps(data)

        # Should have intersection of timestamps
        assert len(timestamps) == 8

    def test_metrics_calculation(self, config: BacktestConfig) -> None:
        """Test metrics are calculated correctly."""
        engine = BacktestEngine(config)

        # Manually add trades
        winning_trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.LONG,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=100,
        )
        winning_trade.close(
            exit_price=1.1100,
            exit_time=datetime.now(timezone.utc),
            status=TradeStatus.CLOSED_TP,
            slippage=0.0,
            commission=0.0,
        )

        losing_trade = Trade(
            symbol="GBP/USD",
            direction=TradeDirection.LONG,
            entry_price=1.2000,
            entry_time=datetime.now(timezone.utc),
            position_size=100,
        )
        losing_trade.close(
            exit_price=1.1900,
            exit_time=datetime.now(timezone.utc),
            status=TradeStatus.CLOSED_SL,
            slippage=0.0,
            commission=0.0,
        )

        engine._trades = [winning_trade, losing_trade]
        engine._equity_curve = [10000, 10010, 10000, 10005]

        result = engine._compute_results()

        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert result.win_rate == 0.5
        assert result.profit_factor > 0
        assert result.total_pnl == winning_trade.pnl + losing_trade.pnl


class TestBacktestMetrics:
    """Tests for metric calculations."""

    def test_max_drawdown_calculation(self, config: BacktestConfig) -> None:
        """Test max drawdown calculation."""
        engine = BacktestEngine(config)

        # Equity: 100 -> 120 -> 90 -> 110
        # Peak: 100, 120, 120, 120
        # DD: 0%, 0%, 25%, 8.3%
        engine._equity_curve = [100, 120, 90, 110]

        max_dd = engine._calculate_max_drawdown()

        # Max DD should be (120 - 90) / 120 = 25%
        assert abs(max_dd - 0.25) < 0.01

    def test_sharpe_ratio_calculation(self, config: BacktestConfig) -> None:
        """Test Sharpe ratio calculation."""
        engine = BacktestEngine(config)

        # Steady growth
        engine._equity_curve = [10000 + i * 100 for i in range(20)]

        sharpe = engine._calculate_sharpe_ratio()

        # Should be positive for steady growth
        assert sharpe > 0

    def test_sharpe_ratio_zero_volatility(self, config: BacktestConfig) -> None:
        """Test Sharpe ratio with no volatility."""
        engine = BacktestEngine(config)

        # Flat equity
        engine._equity_curve = [10000] * 20

        sharpe = engine._calculate_sharpe_ratio()

        # Should be 0 when no volatility
        assert sharpe == 0.0

    def test_profit_factor_no_losses(self, config: BacktestConfig) -> None:
        """Test profit factor with no losing trades."""
        engine = BacktestEngine(config)

        winning_trade = Trade(
            symbol="EUR/USD",
            direction=TradeDirection.LONG,
            entry_price=1.1000,
            entry_time=datetime.now(timezone.utc),
            position_size=100,
        )
        winning_trade.pnl = 100.0
        winning_trade.status = TradeStatus.CLOSED_TP

        engine._trades = [winning_trade]
        engine._equity_curve = [10000, 10100]

        result = engine._compute_results()

        assert result.profit_factor == float("inf")
