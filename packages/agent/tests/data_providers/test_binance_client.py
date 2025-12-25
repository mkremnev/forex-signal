"""Tests for Binance data provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from forex_signal_agent.data_providers.binance_client import (
    TIMEFRAME_MAP,
    BinanceProvider,
)


@pytest.fixture
def provider() -> BinanceProvider:
    """Create a Binance provider instance."""
    return BinanceProvider(rate_limit_per_second=10.0, sandbox=True)


@pytest.fixture
def sample_ohlcv_list() -> list:
    """Create sample OHLCV data in CCXT format."""
    base_ts = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    return [
        [base_ts + i * 3600000, 40000 + i * 100, 40100 + i * 100, 39900 + i * 100, 40050 + i * 100, 1000 + i * 10]
        for i in range(10)
    ]


class TestBinanceProvider:
    """Tests for BinanceProvider class."""

    def test_provider_name(self, provider: BinanceProvider) -> None:
        """Test provider name property."""
        assert provider.name == "binance"

    def test_timeframe_mapping(self) -> None:
        """Test timeframe mapping is complete."""
        expected_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        for tf in expected_timeframes:
            assert tf in TIMEFRAME_MAP

    @pytest.mark.asyncio
    async def test_get_candles_success(
        self,
        provider: BinanceProvider,
        sample_ohlcv_list: list,
    ) -> None:
        """Test successful candle fetching."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_list)

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            df = await provider.get_candles("BTCUSDT", "1h", bars=10)

            assert not df.empty
            assert len(df) == 10
            assert list(df.columns) == ["open", "high", "low", "close", "volume"]
            assert df.index.name == "datetime"
            mock_exchange.fetch_ohlcv.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_candles_empty_response(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test handling of empty response."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            df = await provider.get_candles("INVALID", "1h", bars=10)

            assert df.empty

    @pytest.mark.asyncio
    async def test_get_candles_error(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test error handling."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(side_effect=Exception("API Error"))

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            df = await provider.get_candles("BTCUSDT", "1h", bars=10)

            assert df.empty

    @pytest.mark.asyncio
    async def test_get_latest_price_success(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test getting latest price."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 42000.50})

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            price = await provider.get_latest_price("BTCUSDT")

            assert price == 42000.50

    @pytest.mark.asyncio
    async def test_get_latest_price_no_price(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test handling when no price available."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock(return_value={"last": None})

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            price = await provider.get_latest_price("BTCUSDT")

            assert price is None

    @pytest.mark.asyncio
    async def test_get_latest_price_error(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test error handling for latest price."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ticker = AsyncMock(side_effect=Exception("API Error"))

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            price = await provider.get_latest_price("BTCUSDT")

            assert price is None

    @pytest.mark.asyncio
    async def test_get_multiple_success(
        self,
        provider: BinanceProvider,
        sample_ohlcv_list: list,
    ) -> None:
        """Test fetching multiple symbols."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_list)

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            results = await provider.get_multiple(
                ["BTCUSDT", "ETHUSDT"],
                "1h",
                bars=10,
            )

            assert "BTCUSDT" in results
            assert "ETHUSDT" in results
            assert not results["BTCUSDT"].empty
            assert not results["ETHUSDT"].empty

    @pytest.mark.asyncio
    async def test_close(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test closing provider."""
        mock_exchange = AsyncMock()
        mock_exchange.close = AsyncMock()

        # First, initialize the exchange
        provider._exchange = mock_exchange

        await provider.close()

        mock_exchange.close.assert_called_once()
        assert provider._exchange is None

    def test_to_ccxt_symbol_with_usdt(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test symbol conversion for USDT pairs."""
        assert provider._to_ccxt_symbol("BTCUSDT") == "BTC/USDT"
        assert provider._to_ccxt_symbol("ETHUSDT") == "ETH/USDT"
        assert provider._to_ccxt_symbol("SOLUSDT") == "SOL/USDT"

    def test_to_ccxt_symbol_with_busd(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test symbol conversion for BUSD pairs."""
        assert provider._to_ccxt_symbol("BTCBUSD") == "BTC/BUSD"
        assert provider._to_ccxt_symbol("ETHBUSD") == "ETH/BUSD"

    def test_to_ccxt_symbol_with_btc_quote(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test symbol conversion for BTC quote pairs."""
        assert provider._to_ccxt_symbol("ETHBTC") == "ETH/BTC"
        assert provider._to_ccxt_symbol("SOLBTC") == "SOL/BTC"

    def test_to_ccxt_symbol_already_formatted(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test symbol conversion when already in CCXT format."""
        assert provider._to_ccxt_symbol("BTC/USDT") == "BTC/USDT"
        assert provider._to_ccxt_symbol("ETH/USDT") == "ETH/USDT"

    def test_empty_dataframe_structure(
        self,
        provider: BinanceProvider,
    ) -> None:
        """Test empty DataFrame has correct structure."""
        df = provider._empty_dataframe()

        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "datetime"
        assert df.index.tz is not None


class TestBinanceProviderIntegration:
    """Integration-style tests for BinanceProvider.

    These tests verify the correct interaction between components
    but still use mocks to avoid real API calls.
    """

    @pytest.mark.asyncio
    async def test_lazy_exchange_initialization(self) -> None:
        """Test that exchange is lazily initialized."""
        provider = BinanceProvider(sandbox=True)

        assert provider._exchange is None

        # Mock the ccxt module
        with patch("forex_signal_agent.data_providers.binance_client.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_ccxt.binance.return_value = mock_exchange

            exchange = await provider._get_exchange()

            assert exchange is mock_exchange
            mock_ccxt.binance.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """Test that rate limiting is applied."""
        # Very low rate limit to force waiting
        provider = BinanceProvider(rate_limit_per_second=0.5)

        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])

        with patch.object(provider, "_get_exchange", return_value=mock_exchange):
            import time

            start = time.time()

            # Make two requests
            await provider.get_candles("BTCUSDT", "1h", bars=1)
            await provider.get_candles("BTCUSDT", "1h", bars=1)

            elapsed = time.time() - start

            # Should take at least 2 seconds (1/0.5 = 2 seconds between requests)
            assert elapsed >= 1.5  # Allow some margin
