"""Integration tests for full 24h analysis cycle."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from forex_signal_agent.analysis import (
    AnalysisEvent,
    Direction,
    EventType,
    ProbabilisticAnalyzer,
    ProbabilityResult,
    VolatilityRegime,
    VolatilityResult,
)
from forex_signal_agent.config import AppConfig, load_config
from forex_signal_agent.data_providers import (
    DataManager,
    Instrument,
    InstrumentType,
    create_instruments_from_config,
)
from forex_signal_agent.message_types import (
    CorrelationMatrixPayload,
    ProbabilitySignalPayload,
)


@pytest.fixture
def sample_ohlcv_data() -> dict[str, pd.DataFrame]:
    """Create sample OHLCV data for multiple symbols."""
    dates = pd.date_range(
        start="2024-01-01",
        periods=48,
        freq="1h",
        tz="UTC",
    )

    def make_df(base_price: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [base_price + i * 0.001 for i in range(48)],
                "high": [base_price + i * 0.001 + 0.002 for i in range(48)],
                "low": [base_price + i * 0.001 - 0.001 for i in range(48)],
                "close": [base_price + i * 0.001 + 0.0005 for i in range(48)],
                "volume": [1000] * 48,
            },
            index=dates,
        )

    return {
        "EUR/USD": make_df(1.1000),
        "GBP/USD": make_df(1.2500),
        "USD/JPY": make_df(150.00),
    }


@pytest.fixture
def instruments() -> list[Instrument]:
    """Create test instruments."""
    return [
        Instrument("EUR/USD", InstrumentType.FOREX, yahoo_symbol="EURUSD=X"),
        Instrument("GBP/USD", InstrumentType.FOREX, yahoo_symbol="GBPUSD=X"),
        Instrument("USD/JPY", InstrumentType.FOREX, yahoo_symbol="USDJPY=X"),
    ]


class TestProbabilisticAnalyzerIntegration:
    """Integration tests for ProbabilisticAnalyzer."""

    def test_full_analysis_cycle(
        self,
        sample_ohlcv_data: dict[str, pd.DataFrame],
    ) -> None:
        """Test complete analysis cycle with correlation update and batch analysis."""
        analyzer = ProbabilisticAnalyzer()

        # Update correlations
        corr_matrix = analyzer.update_correlations(sample_ohlcv_data)

        assert not corr_matrix.empty
        assert len(corr_matrix) == 3

        # Analyze all symbols
        results = analyzer.analyze_batch(sample_ohlcv_data, "1h")

        assert len(results) == 3
        assert "EUR/USD" in results
        assert "GBP/USD" in results
        assert "USD/JPY" in results

        # Check result structure
        for symbol, result in results.items():
            assert result.symbol == symbol
            assert result.timeframe == "1h"
            assert result.probability is not None or result.volatility is not None

    def test_event_generation(
        self,
        sample_ohlcv_data: dict[str, pd.DataFrame],
    ) -> None:
        """Test that events are generated correctly."""
        analyzer = ProbabilisticAnalyzer()
        analyzer.update_correlations(sample_ohlcv_data)

        results = analyzer.analyze_batch(sample_ohlcv_data, "4h")

        # Collect all events
        all_events: list[AnalysisEvent] = []
        for result in results.values():
            all_events.extend(result.events)

        # Events should have correct structure
        for event in all_events:
            assert event.event_type in (
                EventType.PROBABILITY_SIGNAL,
                EventType.VOLATILITY_ALERT,
            )
            assert event.symbol in sample_ohlcv_data
            assert event.timeframe == "4h"
            assert event.importance in (1, 2)

    def test_actionable_signal_filtering(
        self,
        sample_ohlcv_data: dict[str, pd.DataFrame],
    ) -> None:
        """Test filtering for actionable signals."""
        analyzer = ProbabilisticAnalyzer()
        analyzer.update_correlations(sample_ohlcv_data)

        results = analyzer.analyze_batch(sample_ohlcv_data, "1h")

        actionable = analyzer.get_actionable_signals(results)

        # All actionable signals should have is_actionable=True
        for event in actionable:
            assert event.data.get("is_actionable", False)


class TestDataManagerIntegration:
    """Integration tests for DataManager."""

    @pytest.mark.asyncio
    async def test_get_all_instruments(
        self,
        instruments: list[Instrument],
        sample_ohlcv_data: dict[str, pd.DataFrame],
    ) -> None:
        """Test fetching all instruments."""
        manager = DataManager(cache_ttl_seconds=60)

        # Mock the Yahoo provider
        mock_yahoo = AsyncMock()

        async def mock_get_candles(symbol: str, tf, bars: int) -> pd.DataFrame:
            # Map Yahoo symbols to our test data
            symbol_map = {
                "EURUSD=X": "EUR/USD",
                "GBPUSD=X": "GBP/USD",
                "USDJPY=X": "USD/JPY",
            }
            name = symbol_map.get(symbol, symbol)
            return sample_ohlcv_data.get(name, pd.DataFrame())

        mock_yahoo.get_candles = mock_get_candles

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            results = await manager.get_all_instruments(
                instruments,
                "1h",
                bars=48,
            )

            assert len(results) == 3
            for name, df in results.items():
                assert not df.empty
                assert len(df) == 48

        await manager.close()


class TestMessagePayloads:
    """Tests for message payload creation."""

    def test_probability_signal_payload(self) -> None:
        """Test creating probability signal payload."""
        payload = ProbabilitySignalPayload(
            symbol="EUR/USD",
            timeframe="4h",
            direction="upward",
            probabilities={
                "upward": 0.55,
                "downward": 0.30,
                "consolidation": 0.15,
            },
            confidence=0.25,
            is_actionable=False,
            importance=1,
            factors={
                "roc": 0.5,
                "volatility": 0.8,
                "volume": 1.2,
                "correlation": 0.4,
            },
            volatility_regime="normal",
            atr_percent=0.75,
        )

        assert payload.symbol == "EUR/USD"
        assert payload.direction == "upward"
        assert payload.probabilities["upward"] == 0.55
        assert not payload.is_actionable

    def test_correlation_matrix_payload(self) -> None:
        """Test creating correlation matrix payload."""
        payload = CorrelationMatrixPayload(
            symbols=["EUR/USD", "GBP/USD", "USD/JPY"],
            matrix={
                "EUR/USD": {"EUR/USD": 1.0, "GBP/USD": 0.85, "USD/JPY": -0.45},
                "GBP/USD": {"EUR/USD": 0.85, "GBP/USD": 1.0, "USD/JPY": -0.30},
                "USD/JPY": {"EUR/USD": -0.45, "GBP/USD": -0.30, "USD/JPY": 1.0},
            },
            high_correlations=[
                {"pair": ("EUR/USD", "GBP/USD"), "correlation": 0.85}
            ],
        )

        assert len(payload.symbols) == 3
        assert payload.matrix["EUR/USD"]["GBP/USD"] == 0.85


class TestConfigIntegration:
    """Tests for configuration integration."""

    def test_config_has_probability_settings(self) -> None:
        """Test that config includes probability settings."""
        config = AppConfig()

        assert hasattr(config, "probability")
        assert config.probability.confidence_threshold == 0.4
        assert config.probability.high_confidence_threshold == 0.6

    def test_config_has_correlation_settings(self) -> None:
        """Test that config includes correlation settings."""
        config = AppConfig()

        assert hasattr(config, "correlation")
        assert config.correlation.lookback_hours == 24
        assert config.correlation.min_data_points == 20

    def test_config_has_crypto_settings(self) -> None:
        """Test that config includes crypto settings."""
        config = AppConfig()

        assert hasattr(config, "crypto")
        assert config.crypto.enabled is False


class TestFullCycleFlow:
    """Tests for full 24h cycle flow simulation."""

    @pytest.mark.asyncio
    async def test_24h_cycle_simulation(
        self,
        sample_ohlcv_data: dict[str, pd.DataFrame],
    ) -> None:
        """Simulate a complete 24h analysis cycle."""
        # Setup
        analyzer = ProbabilisticAnalyzer()
        manager = DataManager()

        # Mock data fetching
        mock_yahoo = AsyncMock()

        async def mock_get_candles(symbol: str, tf, bars: int) -> pd.DataFrame:
            symbol_map = {
                "EURUSD=X": "EUR/USD",
                "GBPUSD=X": "GBP/USD",
                "USDJPY=X": "USD/JPY",
            }
            name = symbol_map.get(symbol, symbol)
            return sample_ohlcv_data.get(name, pd.DataFrame())

        mock_yahoo.get_candles = mock_get_candles

        instruments = [
            Instrument("EUR/USD", InstrumentType.FOREX, yahoo_symbol="EURUSD=X"),
            Instrument("GBP/USD", InstrumentType.FOREX, yahoo_symbol="GBPUSD=X"),
        ]

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            # Step 1: Fetch data for all instruments
            data = await manager.get_all_instruments(instruments, "1h", bars=48)

            assert len(data) == 2

            # Step 2: Update correlations
            corr_matrix = analyzer.update_correlations(data)

            # Step 3: Analyze batch
            results = analyzer.analyze_batch(data, "24h")

            assert len(results) == 2

            # Step 4: Process events
            events_to_send: list[AnalysisEvent] = []
            for result in results.values():
                for event in result.events:
                    if event.event_type == EventType.PROBABILITY_SIGNAL:
                        if event.data.get("confidence", 0) >= 0.4:
                            events_to_send.append(event)

            # All probability signals above threshold should be collected
            for event in events_to_send:
                assert event.data["confidence"] >= 0.4

        await manager.close()
