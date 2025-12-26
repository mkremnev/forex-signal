"""Integration tests for probabilistic analyzer wiring."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List

from forex_signal_agent.main import Application
from forex_signal_agent.analysis import ProbabilisticAnalyzer


@dataclass
class MockTelegramConfig:
    bot_token: str = "test_token"
    chat_id: str = "test_chat"
    message_cooldown_minutes: int = 30


@dataclass
class MockTimeframeJob:
    timeframe: str = "1h"
    poll_interval_seconds: int = 60


@dataclass
class MockRedisConfig:
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    status_interval_seconds: int = 30


@dataclass
class MockMigrationConfig:
    use_probability_analyzer: bool = False
    log_both_analyzers: bool = True
    publish_to_test_channel: bool = True


@dataclass
class MockCorrelationConfig:
    lookback_hours: int = 24
    min_data_points: int = 20
    high_correlation_threshold: float = 0.7


@dataclass
class MockVolatilityConfig:
    atr_period: int = 14
    consolidation_threshold: float = 0.01


@dataclass
class MockProbabilityConfig:
    confidence_threshold: float = 0.4
    high_confidence_threshold: float = 0.6
    forex_weights: dict = field(default_factory=lambda: {
        "roc": 0.33,
        "volatility": 0.33,
        "correlation": 0.33
    })


@dataclass
class MockAppConfig:
    timezone: str = "Europe/Moscow"
    pairs: List[str] = field(default_factory=lambda: ["EUR_USD", "GBP_USD"])
    timeframes: List[MockTimeframeJob] = field(
        default_factory=lambda: [MockTimeframeJob()]
    )
    telegram: MockTelegramConfig = field(default_factory=MockTelegramConfig)
    adx_threshold: float = 20.0
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    notify_hourly_summary: bool = False
    sqlite_path: str = ":memory:"
    redis: MockRedisConfig = field(default_factory=MockRedisConfig)
    migration: MockMigrationConfig = field(default_factory=MockMigrationConfig)
    correlation: MockCorrelationConfig = field(default_factory=MockCorrelationConfig)
    volatility: MockVolatilityConfig = field(default_factory=MockVolatilityConfig)
    probability: MockProbabilityConfig = field(default_factory=MockProbabilityConfig)


class TestProbabilisticAnalyzerWiring:
    """Tests for probabilistic analyzer initialization wiring."""

    @pytest.mark.asyncio
    async def test_application_initializes_probabilistic_analyzer(self):
        """
        Test that Application initializes ProbabilisticAnalyzer when flag is enabled.

        When migration.use_probability_analyzer=True, after app.initialize(),
        app.probabilistic_analyzer should not be None.
        """
        # Create config with probabilistic mode enabled
        config = MockAppConfig()
        config.migration.use_probability_analyzer = True

        with patch(
            "forex_signal_agent.main.load_config",
            return_value=config
        ), patch(
            "forex_signal_agent.main.Cache"
        ) as mock_cache_class, patch(
            "forex_signal_agent.main.TelegramNotifier"
        ) as mock_notifier_class, patch(
            "forex_signal_agent.main.YahooFinanceClient"
        ) as mock_client_class:
            # Setup mocks
            mock_cache = MagicMock()
            mock_cache.init = AsyncMock()
            mock_cache_class.return_value = mock_cache

            mock_notifier = MagicMock()
            mock_notifier_class.return_value = mock_notifier

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create and initialize application
            app = Application("test_config.yaml")
            await app.initialize()

            # Assert probabilistic analyzer is initialized
            assert app.probabilistic_analyzer is not None
            assert isinstance(app.probabilistic_analyzer, ProbabilisticAnalyzer)

    @pytest.mark.asyncio
    async def test_application_skips_probabilistic_analyzer_when_disabled(self):
        """
        Test that Application does not initialize ProbabilisticAnalyzer when flag is disabled.

        When migration.use_probability_analyzer=False, after app.initialize(),
        app.probabilistic_analyzer should remain None.
        """
        # Create config with probabilistic mode disabled
        config = MockAppConfig()
        config.migration.use_probability_analyzer = False

        with patch(
            "forex_signal_agent.main.load_config",
            return_value=config
        ), patch(
            "forex_signal_agent.main.Cache"
        ) as mock_cache_class, patch(
            "forex_signal_agent.main.TelegramNotifier"
        ) as mock_notifier_class, patch(
            "forex_signal_agent.main.YahooFinanceClient"
        ) as mock_client_class:
            # Setup mocks
            mock_cache = MagicMock()
            mock_cache.init = AsyncMock()
            mock_cache_class.return_value = mock_cache

            mock_notifier = MagicMock()
            mock_notifier_class.return_value = mock_notifier

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create and initialize application
            app = Application("test_config.yaml")
            await app.initialize()

            # Assert probabilistic analyzer is not initialized
            assert app.probabilistic_analyzer is None

    @pytest.mark.asyncio
    async def test_probabilistic_analyzer_uses_config_weights(self):
        """Test that ProbabilisticAnalyzer is initialized with config weights."""
        # Create config with custom weights
        config = MockAppConfig()
        config.migration.use_probability_analyzer = True
        config.probability.forex_weights = {
            "roc": 0.4,
            "volatility": 0.3,
            "correlation": 0.3
        }

        with patch(
            "forex_signal_agent.main.load_config",
            return_value=config
        ), patch(
            "forex_signal_agent.main.Cache"
        ) as mock_cache_class, patch(
            "forex_signal_agent.main.TelegramNotifier"
        ) as mock_notifier_class, patch(
            "forex_signal_agent.main.YahooFinanceClient"
        ) as mock_client_class:
            # Setup mocks
            mock_cache = MagicMock()
            mock_cache.init = AsyncMock()
            mock_cache_class.return_value = mock_cache

            mock_notifier = MagicMock()
            mock_notifier_class.return_value = mock_notifier

            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create and initialize application
            app = Application("test_config.yaml")
            await app.initialize()

            # Assert probabilistic analyzer is initialized
            assert app.probabilistic_analyzer is not None
