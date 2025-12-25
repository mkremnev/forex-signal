"""Tests for DataManager."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from forex_signal_agent.data_providers import (
    DataManager,
    Instrument,
    InstrumentType,
    create_instruments_from_config,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample OHLCV DataFrame."""
    dates = pd.date_range(
        start="2024-01-01",
        periods=10,
        freq="1h",
        tz="UTC",
    )
    return pd.DataFrame(
        {
            "open": [1.08 + i * 0.001 for i in range(10)],
            "high": [1.085 + i * 0.001 for i in range(10)],
            "low": [1.075 + i * 0.001 for i in range(10)],
            "close": [1.082 + i * 0.001 for i in range(10)],
            "volume": [1000 + i * 100 for i in range(10)],
        },
        index=dates,
    )


@pytest.fixture
def forex_instrument() -> Instrument:
    """Create a forex instrument."""
    return Instrument(
        name="EUR/USD",
        instrument_type=InstrumentType.FOREX,
        yahoo_symbol="EURUSD=X",
    )


@pytest.fixture
def crypto_instrument() -> Instrument:
    """Create a crypto instrument."""
    return Instrument(
        name="BTC/USDT",
        instrument_type=InstrumentType.CRYPTO,
        binance_symbol="BTCUSDT",
    )


class TestDataManager:
    """Tests for DataManager class."""

    @pytest.mark.asyncio
    async def test_get_candles_forex_uses_yahoo(
        self,
        forex_instrument: Instrument,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test that forex instruments use Yahoo provider."""
        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            df = await manager.get_candles(forex_instrument, "1h", bars=10)

            assert not df.empty
            mock_yahoo.get_candles.assert_called_once_with("EURUSD=X", "1h", 10)

        await manager.close()

    @pytest.mark.asyncio
    async def test_get_candles_crypto_uses_binance(
        self,
        crypto_instrument: Instrument,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test that crypto instruments use Binance provider."""
        manager = DataManager()

        mock_binance = AsyncMock()
        mock_binance.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_binance", return_value=mock_binance):
            df = await manager.get_candles(crypto_instrument, "1h", bars=10)

            assert not df.empty
            mock_binance.get_candles.assert_called_once_with("BTCUSDT", "1h", 10)

        await manager.close()

    @pytest.mark.asyncio
    async def test_caching_returns_cached_data(
        self,
        forex_instrument: Instrument,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test that cached data is returned on second request."""
        manager = DataManager(cache_ttl_seconds=300)

        mock_yahoo = AsyncMock()
        mock_yahoo.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            # First request
            df1 = await manager.get_candles(forex_instrument, "1h", bars=10)

            # Second request should use cache
            df2 = await manager.get_candles(forex_instrument, "1h", bars=10)

            # Provider should only be called once
            assert mock_yahoo.get_candles.call_count == 1
            assert len(df1) == len(df2)

        await manager.close()

    @pytest.mark.asyncio
    async def test_cache_disabled(
        self,
        forex_instrument: Instrument,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test that caching can be disabled."""
        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            # First request without cache
            await manager.get_candles(forex_instrument, "1h", bars=10, use_cache=False)

            # Second request without cache
            await manager.get_candles(forex_instrument, "1h", bars=10, use_cache=False)

            # Provider should be called twice
            assert mock_yahoo.get_candles.call_count == 2

        await manager.close()

    @pytest.mark.asyncio
    async def test_get_latest_price_forex(
        self,
        forex_instrument: Instrument,
    ) -> None:
        """Test getting latest price for forex."""
        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.get_latest_price = AsyncMock(return_value=1.0850)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            price = await manager.get_latest_price(forex_instrument)

            assert price == 1.0850

        await manager.close()

    @pytest.mark.asyncio
    async def test_get_latest_price_crypto(
        self,
        crypto_instrument: Instrument,
    ) -> None:
        """Test getting latest price for crypto."""
        manager = DataManager()

        mock_binance = AsyncMock()
        mock_binance.get_latest_price = AsyncMock(return_value=42000.50)

        with patch.object(manager, "_get_binance", return_value=mock_binance):
            price = await manager.get_latest_price(crypto_instrument)

            assert price == 42000.50

        await manager.close()

    @pytest.mark.asyncio
    async def test_get_all_instruments(
        self,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test fetching all instruments concurrently."""
        instruments = [
            Instrument("EUR/USD", InstrumentType.FOREX, yahoo_symbol="EURUSD=X"),
            Instrument("GBP/USD", InstrumentType.FOREX, yahoo_symbol="GBPUSD=X"),
            Instrument("BTC/USDT", InstrumentType.CRYPTO, binance_symbol="BTCUSDT"),
        ]

        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.get_candles = AsyncMock(return_value=sample_df)

        mock_binance = AsyncMock()
        mock_binance.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            with patch.object(manager, "_get_binance", return_value=mock_binance):
                results = await manager.get_all_instruments(
                    instruments,
                    "1h",
                    bars=10,
                )

                assert len(results) == 3
                assert "EUR/USD" in results
                assert "GBP/USD" in results
                assert "BTC/USDT" in results

        await manager.close()

    @pytest.mark.asyncio
    async def test_clear_cache(
        self,
        forex_instrument: Instrument,
        sample_df: pd.DataFrame,
    ) -> None:
        """Test cache clearing."""
        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.get_candles = AsyncMock(return_value=sample_df)

        with patch.object(manager, "_get_yahoo", return_value=mock_yahoo):
            # First request
            await manager.get_candles(forex_instrument, "1h", bars=10)

            # Clear cache
            await manager.clear_cache()

            # Second request should hit provider again
            await manager.get_candles(forex_instrument, "1h", bars=10)

            assert mock_yahoo.get_candles.call_count == 2

        await manager.close()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self) -> None:
        """Test that close cleans up resources."""
        manager = DataManager()

        mock_yahoo = AsyncMock()
        mock_yahoo.close = AsyncMock()

        mock_binance = AsyncMock()
        mock_binance.close = AsyncMock()

        manager._yahoo = mock_yahoo
        manager._binance = mock_binance

        await manager.close()

        mock_yahoo.close.assert_called_once()
        mock_binance.close.assert_called_once()
        assert manager._yahoo is None
        assert manager._binance is None

    @pytest.mark.asyncio
    async def test_missing_symbol_returns_empty(self) -> None:
        """Test that missing symbol returns empty DataFrame."""
        instrument = Instrument(
            name="Unknown",
            instrument_type=InstrumentType.FOREX,
            yahoo_symbol=None,  # No symbol
        )

        manager = DataManager()

        df = await manager.get_candles(instrument, "1h", bars=10)

        assert df.empty

        await manager.close()


class TestInstrumentHelpers:
    """Tests for Instrument helper functions."""

    def test_create_instruments_from_config_forex(self) -> None:
        """Test creating instruments from forex config."""
        forex_pairs = [
            {"name": "EUR/USD", "yahoo_symbol": "EURUSD=X"},
            {"name": "GBP/USD", "yahoo_symbol": "GBPUSD=X"},
        ]

        instruments = create_instruments_from_config(forex_pairs)

        assert len(instruments) == 2
        assert instruments[0].name == "EUR/USD"
        assert instruments[0].yahoo_symbol == "EURUSD=X"
        assert instruments[0].instrument_type == InstrumentType.FOREX

    def test_create_instruments_from_config_crypto(self) -> None:
        """Test creating instruments from crypto config."""
        forex_pairs: list = []
        crypto_pairs = [
            {"name": "BTC/USDT", "binance_symbol": "BTCUSDT"},
            {"name": "ETH/USDT", "binance_symbol": "ETHUSDT"},
        ]

        instruments = create_instruments_from_config(forex_pairs, crypto_pairs)

        assert len(instruments) == 2
        assert instruments[0].name == "BTC/USDT"
        assert instruments[0].binance_symbol == "BTCUSDT"
        assert instruments[0].instrument_type == InstrumentType.CRYPTO

    def test_create_instruments_from_config_mixed(self) -> None:
        """Test creating instruments from mixed config."""
        forex_pairs = [
            {"name": "EUR/USD", "yahoo_symbol": "EURUSD=X"},
        ]
        crypto_pairs = [
            {"name": "BTC/USDT", "binance_symbol": "BTCUSDT"},
        ]

        instruments = create_instruments_from_config(forex_pairs, crypto_pairs)

        assert len(instruments) == 2

        forex = [i for i in instruments if i.instrument_type == InstrumentType.FOREX]
        crypto = [i for i in instruments if i.instrument_type == InstrumentType.CRYPTO]

        assert len(forex) == 1
        assert len(crypto) == 1

    def test_create_instruments_from_config_commodity(self) -> None:
        """Test creating commodity instruments."""
        forex_pairs = [
            {"name": "Gold", "yahoo_symbol": "GC=F", "instrument_type": "commodity"},
        ]

        instruments = create_instruments_from_config(forex_pairs)

        assert len(instruments) == 1
        assert instruments[0].instrument_type == InstrumentType.COMMODITY


class TestInstrument:
    """Tests for Instrument class."""

    def test_get_symbol_yahoo(self) -> None:
        """Test getting Yahoo symbol."""
        instrument = Instrument(
            name="EUR/USD",
            instrument_type=InstrumentType.FOREX,
            yahoo_symbol="EURUSD=X",
            binance_symbol=None,
        )

        assert instrument.get_symbol("yahoo") == "EURUSD=X"
        assert instrument.get_symbol("binance") is None

    def test_get_symbol_binance(self) -> None:
        """Test getting Binance symbol."""
        instrument = Instrument(
            name="BTC/USDT",
            instrument_type=InstrumentType.CRYPTO,
            yahoo_symbol=None,
            binance_symbol="BTCUSDT",
        )

        assert instrument.get_symbol("yahoo") is None
        assert instrument.get_symbol("binance") == "BTCUSDT"

    def test_get_symbol_unknown_provider(self) -> None:
        """Test getting symbol for unknown provider."""
        instrument = Instrument(
            name="EUR/USD",
            instrument_type=InstrumentType.FOREX,
            yahoo_symbol="EURUSD=X",
        )

        assert instrument.get_symbol("unknown") is None
