"""Tests for Yahoo Finance data provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from forex_signal_agent.data_providers.yahoo_client import (
    TIMEFRAME_MAP,
    YahooFinanceProvider,
)


@pytest.fixture
def provider() -> YahooFinanceProvider:
    """Create a Yahoo Finance provider instance."""
    return YahooFinanceProvider(rate_limit_per_second=10.0)


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Create a sample OHLCV DataFrame."""
    dates = pd.date_range(
        start="2024-01-01",
        periods=10,
        freq="1h",
        tz="UTC",
    )
    return pd.DataFrame(
        {
            "Open": [1.0800 + i * 0.001 for i in range(10)],
            "High": [1.0850 + i * 0.001 for i in range(10)],
            "Low": [1.0750 + i * 0.001 for i in range(10)],
            "Close": [1.0820 + i * 0.001 for i in range(10)],
            "Volume": [1000 + i * 100 for i in range(10)],
        },
        index=dates,
    )


class TestYahooFinanceProvider:
    """Tests for YahooFinanceProvider class."""

    def test_provider_name(self, provider: YahooFinanceProvider) -> None:
        """Test provider name property."""
        assert provider.name == "yahoo"

    def test_timeframe_mapping(self) -> None:
        """Test timeframe mapping is complete."""
        expected_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        for tf in expected_timeframes:
            assert tf in TIMEFRAME_MAP

    @pytest.mark.asyncio
    async def test_get_candles_success(
        self,
        provider: YahooFinanceProvider,
        sample_ohlcv_df: pd.DataFrame,
    ) -> None:
        """Test successful candle fetching."""
        with patch("yfinance.download") as mock_download:
            mock_download.return_value = sample_ohlcv_df

            df = await provider.get_candles("EURUSD=X", "1h", bars=5)

            assert not df.empty
            assert len(df) == 5
            assert list(df.columns) == ["open", "high", "low", "close", "volume"]
            assert df.index.name == "datetime"

    @pytest.mark.asyncio
    async def test_get_candles_empty_response(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test handling of empty response."""
        with patch("yfinance.download") as mock_download:
            mock_download.return_value = pd.DataFrame()

            df = await provider.get_candles("INVALID=X", "1h", bars=10)

            assert df.empty
            assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    @pytest.mark.asyncio
    async def test_get_candles_4h_resample(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test 4-hour timeframe resampling."""
        # Create 8 hours of 1h data
        dates = pd.date_range(
            start="2024-01-01 00:00:00",
            periods=8,
            freq="1h",
            tz="UTC",
        )
        hourly_df = pd.DataFrame(
            {
                "Open": [1.08, 1.09, 1.10, 1.11, 1.12, 1.13, 1.14, 1.15],
                "High": [1.09, 1.10, 1.11, 1.12, 1.13, 1.14, 1.15, 1.16],
                "Low": [1.07, 1.08, 1.09, 1.10, 1.11, 1.12, 1.13, 1.14],
                "Close": [1.085, 1.095, 1.105, 1.115, 1.125, 1.135, 1.145, 1.155],
                "Volume": [100, 200, 300, 400, 500, 600, 700, 800],
            },
            index=dates,
        )

        with patch("yfinance.download") as mock_download:
            mock_download.return_value = hourly_df

            df = await provider.get_candles("EURUSD=X", "4h", bars=2)

            # Should have 2 4-hour candles
            assert len(df) == 2
            # First 4h candle should have open from first hour
            assert df["open"].iloc[0] == 1.08
            # And close from 4th hour
            assert df["close"].iloc[0] == 1.115

    @pytest.mark.asyncio
    async def test_get_latest_price_success(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test getting latest price."""
        mock_ticker = MagicMock()
        mock_ticker.fast_info = MagicMock(last_price=1.0850)

        with patch("yfinance.Ticker", return_value=mock_ticker):
            price = await provider.get_latest_price("EURUSD=X")

            assert price == 1.0850

    @pytest.mark.asyncio
    async def test_get_latest_price_fallback_to_history(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test fallback to history when fast_info fails."""
        mock_ticker = MagicMock()
        mock_ticker.fast_info = MagicMock(last_price=None)

        dates = pd.date_range(start="2024-01-01", periods=1, freq="1min", tz="UTC")
        mock_ticker.history.return_value = pd.DataFrame(
            {"Close": [1.0900]},
            index=dates,
        )

        with patch("yfinance.Ticker", return_value=mock_ticker):
            price = await provider.get_latest_price("EURUSD=X")

            assert price == 1.0900

    @pytest.mark.asyncio
    async def test_get_latest_price_error(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test error handling for latest price."""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.side_effect = Exception("API Error")

            price = await provider.get_latest_price("EURUSD=X")

            assert price is None

    def test_calculate_period_intraday(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test period calculation for intraday intervals."""
        # 1m interval, 100 bars -> ~2 hours, rounded up to 1 day
        period = provider._calculate_period("1m", 100)
        assert "d" in period

        # 60m interval, 24 bars -> 1 day
        period = provider._calculate_period("60m", 24)
        assert "d" in period

    def test_calculate_period_daily(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test period calculation for daily intervals."""
        period = provider._calculate_period("1d", 30)
        assert "d" in period

    def test_normalize_columns_multiindex(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test column normalization with MultiIndex."""
        dates = pd.date_range(start="2024-01-01", periods=5, freq="1h", tz="UTC")
        df = pd.DataFrame(
            {
                ("EURUSD=X", "Open"): [1.08] * 5,
                ("EURUSD=X", "High"): [1.09] * 5,
                ("EURUSD=X", "Low"): [1.07] * 5,
                ("EURUSD=X", "Close"): [1.085] * 5,
                ("EURUSD=X", "Volume"): [100] * 5,
            },
            index=dates,
        )

        result = provider._normalize_columns(df, "EURUSD=X")

        assert not result.empty
        assert "open" in result.columns

    def test_resample_to_4h(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test 4-hour resampling logic."""
        dates = pd.date_range(
            start="2024-01-01 00:00:00",
            periods=8,
            freq="1h",
            tz="UTC",
        )
        df = pd.DataFrame(
            {
                "open": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7],
                "high": [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8],
                "low": [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6],
                "close": [1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65, 1.75],
                "volume": [100, 200, 300, 400, 500, 600, 700, 800],
            },
            index=dates,
        )

        result = provider._resample_to_4h(df)

        assert len(result) == 2
        # First 4h candle: open=1.0, high=max(1.1,1.2,1.3,1.4)=1.4
        assert result["open"].iloc[0] == 1.0
        assert result["high"].iloc[0] == 1.4
        assert result["low"].iloc[0] == 0.9
        assert result["close"].iloc[0] == 1.35
        assert result["volume"].iloc[0] == 1000  # 100+200+300+400

    def test_empty_dataframe_structure(
        self,
        provider: YahooFinanceProvider,
    ) -> None:
        """Test empty DataFrame has correct structure."""
        df = provider._empty_dataframe()

        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "datetime"
        assert df.index.tz is not None
