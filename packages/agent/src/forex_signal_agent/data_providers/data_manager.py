"""Data manager for routing and caching market data.

Provides a unified interface for fetching market data from multiple providers
with automatic routing based on instrument type and built-in caching.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .base import (
    BaseDataProvider,
    Instrument,
    InstrumentType,
    Timeframe,
    normalize_timeframe,
)
from .binance_client import BinanceProvider
from .yahoo_client import YahooFinanceProvider

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for OHLCV data.

    Attributes:
        data: Cached DataFrame
        timestamp: When the data was cached
        timeframe: Timeframe of the cached data
    """

    data: pd.DataFrame
    timestamp: datetime
    timeframe: str


class DataManager:
    """Central data manager for all market data operations.

    Provides:
    - Automatic routing to appropriate provider based on instrument type
    - OHLCV caching with configurable TTL
    - Concurrent fetching for multiple instruments
    - Unified interface for all data operations

    Example:
        manager = DataManager()

        # Define instruments
        instruments = [
            Instrument("EUR/USD", InstrumentType.FOREX, yahoo_symbol="EURUSD=X"),
            Instrument("BTC/USDT", InstrumentType.CRYPTO, binance_symbol="BTCUSDT"),
        ]

        # Fetch data
        data = await manager.get_all_instruments(instruments, "1h", bars=100)

        # Cleanup
        await manager.close()
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 300,  # 5 minutes default
        binance_sandbox: bool = False,
    ):
        """Initialize data manager.

        Args:
            cache_ttl_seconds: Cache time-to-live in seconds
            binance_sandbox: Use Binance testnet
        """
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = asyncio.Lock()

        # Initialize providers lazily
        self._yahoo: YahooFinanceProvider | None = None
        self._binance: BinanceProvider | None = None
        self._binance_sandbox = binance_sandbox

        # Provider initialization locks
        self._yahoo_lock = asyncio.Lock()
        self._binance_lock = asyncio.Lock()

    async def _get_yahoo(self) -> YahooFinanceProvider:
        """Get or create Yahoo Finance provider."""
        async with self._yahoo_lock:
            if self._yahoo is None:
                self._yahoo = YahooFinanceProvider()
                logger.info("Yahoo Finance provider initialized")
            return self._yahoo

    async def _get_binance(self) -> BinanceProvider:
        """Get or create Binance provider."""
        async with self._binance_lock:
            if self._binance is None:
                self._binance = BinanceProvider(sandbox=self._binance_sandbox)
                logger.info("Binance provider initialized")
            return self._binance

    def _get_provider_for_instrument(
        self, instrument: Instrument
    ) -> tuple[str, str | None]:
        """Determine provider and symbol for an instrument.

        Args:
            instrument: Instrument definition

        Returns:
            Tuple of (provider_name, symbol) or (provider_name, None) if no symbol
        """
        if instrument.instrument_type == InstrumentType.CRYPTO:
            return "binance", instrument.binance_symbol
        else:
            # Forex, commodity, index -> Yahoo
            return "yahoo", instrument.yahoo_symbol

    def _cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key for a symbol and timeframe."""
        return f"{symbol}:{timeframe}"

    async def _get_from_cache(
        self, symbol: str, timeframe: str
    ) -> pd.DataFrame | None:
        """Get data from cache if valid.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe

        Returns:
            Cached DataFrame or None if not cached or expired
        """
        key = self._cache_key(symbol, timeframe)

        async with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            now = datetime.now(timezone.utc)
            if now - entry.timestamp > self._cache_ttl:
                # Expired
                del self._cache[key]
                return None

            return entry.data.copy()

    async def _set_cache(
        self, symbol: str, timeframe: str, data: pd.DataFrame
    ) -> None:
        """Store data in cache.

        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            data: OHLCV DataFrame to cache
        """
        key = self._cache_key(symbol, timeframe)

        async with self._cache_lock:
            self._cache[key] = CacheEntry(
                data=data.copy(),
                timestamp=datetime.now(timezone.utc),
                timeframe=timeframe,
            )

    async def get_candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe | str,
        bars: int = 100,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for an instrument.

        Automatically routes to the appropriate provider based on
        instrument type and caches the result.

        Args:
            instrument: Instrument definition
            timeframe: Candle timeframe
            bars: Number of bars to fetch
            use_cache: Whether to use/update cache

        Returns:
            DataFrame with datetime index and OHLCV columns
        """
        tf_str = normalize_timeframe(timeframe)
        provider_name, symbol = self._get_provider_for_instrument(instrument)

        if symbol is None:
            logger.warning(
                f"No symbol configured for {instrument.name} "
                f"with provider {provider_name}"
            )
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            ).set_index(pd.DatetimeIndex([], name="datetime", tz="UTC"))

        # Check cache first
        if use_cache:
            cached = await self._get_from_cache(symbol, tf_str)
            if cached is not None and len(cached) >= bars:
                logger.debug(f"Cache hit for {symbol}:{tf_str}")
                return cached.iloc[-bars:]

        # Fetch from provider
        try:
            if provider_name == "yahoo":
                provider = await self._get_yahoo()
            else:
                provider = await self._get_binance()

            df = await provider.get_candles(symbol, timeframe, bars)

            # Update cache
            if use_cache and not df.empty:
                await self._set_cache(symbol, tf_str, df)

            return df

        except Exception as e:
            logger.error(f"Error fetching {instrument.name}: {e}")
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"]
            ).set_index(pd.DatetimeIndex([], name="datetime", tz="UTC"))

    async def get_latest_price(self, instrument: Instrument) -> float | None:
        """Get the latest price for an instrument.

        Args:
            instrument: Instrument definition

        Returns:
            Latest price or None if unavailable
        """
        provider_name, symbol = self._get_provider_for_instrument(instrument)

        if symbol is None:
            logger.warning(f"No symbol configured for {instrument.name}")
            return None

        try:
            if provider_name == "yahoo":
                provider = await self._get_yahoo()
            else:
                provider = await self._get_binance()

            return await provider.get_latest_price(symbol)

        except Exception as e:
            logger.error(f"Error getting price for {instrument.name}: {e}")
            return None

    async def get_all_instruments(
        self,
        instruments: list[Instrument],
        timeframe: Timeframe | str,
        bars: int = 100,
        use_cache: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Fetch data for all instruments concurrently.

        Args:
            instruments: List of instrument definitions
            timeframe: Candle timeframe
            bars: Number of bars per instrument
            use_cache: Whether to use/update cache

        Returns:
            Dictionary mapping instrument name to DataFrame
        """
        results: dict[str, pd.DataFrame] = {}

        async def fetch_one(
            instrument: Instrument,
        ) -> tuple[str, pd.DataFrame]:
            df = await self.get_candles(instrument, timeframe, bars, use_cache)
            return instrument.name, df

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(10)

        async def fetch_with_semaphore(
            instrument: Instrument,
        ) -> tuple[str, pd.DataFrame]:
            async with semaphore:
                return await fetch_one(instrument)

        tasks = [fetch_with_semaphore(i) for i in instruments]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Error in batch fetch: {result}")
                continue
            name, df = result
            results[name] = df

        return results

    async def clear_cache(self) -> None:
        """Clear all cached data."""
        async with self._cache_lock:
            self._cache.clear()
            logger.info("Data cache cleared")

    async def close(self) -> None:
        """Close all providers and clean up resources."""
        tasks = []

        if self._yahoo is not None:
            tasks.append(self._yahoo.close())

        if self._binance is not None:
            tasks.append(self._binance.close())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._yahoo = None
        self._binance = None
        await self.clear_cache()

        logger.info("Data manager closed")


def create_instruments_from_config(
    forex_pairs: list[dict[str, Any]],
    crypto_pairs: list[dict[str, Any]] | None = None,
) -> list[Instrument]:
    """Create Instrument list from configuration dictionaries.

    Expected format for forex:
        {"name": "EUR/USD", "yahoo_symbol": "EURUSD=X"}

    Expected format for crypto:
        {"name": "BTC/USDT", "binance_symbol": "BTCUSDT"}

    Args:
        forex_pairs: List of forex pair configurations
        crypto_pairs: List of crypto pair configurations

    Returns:
        List of Instrument objects
    """
    instruments: list[Instrument] = []

    for pair in forex_pairs:
        name = pair.get("name", "")
        yahoo_symbol = pair.get("yahoo_symbol")
        instrument_type_str = pair.get("instrument_type", "forex").lower()

        if instrument_type_str == "commodity":
            instrument_type = InstrumentType.COMMODITY
        elif instrument_type_str == "index":
            instrument_type = InstrumentType.INDEX
        else:
            instrument_type = InstrumentType.FOREX

        instruments.append(
            Instrument(
                name=name,
                instrument_type=instrument_type,
                yahoo_symbol=yahoo_symbol,
            )
        )

    if crypto_pairs:
        for pair in crypto_pairs:
            name = pair.get("name", "")
            binance_symbol = pair.get("binance_symbol")

            instruments.append(
                Instrument(
                    name=name,
                    instrument_type=InstrumentType.CRYPTO,
                    binance_symbol=binance_symbol,
                )
            )

    return instruments
