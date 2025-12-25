"""Base classes and protocols for data providers.

This module defines the unified interface for all market data providers,
allowing seamless switching between Yahoo Finance, Binance, and future providers.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

import pandas as pd


class Timeframe(str, Enum):
    """Supported timeframes for OHLCV data."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class InstrumentType(str, Enum):
    """Type of financial instrument."""

    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"


@dataclass
class OHLCV:
    """Standard candlestick data structure.

    Attributes:
        datetime: Timestamp of the candle
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume (may be 0 for forex)
    """

    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            "datetime": self.datetime,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class Instrument:
    """Instrument definition with provider-specific symbols.

    Attributes:
        name: Human-readable name (e.g., "EUR/USD")
        instrument_type: Type of instrument (forex, crypto, etc.)
        yahoo_symbol: Symbol for Yahoo Finance (e.g., "EURUSD=X")
        binance_symbol: Symbol for Binance (e.g., "BTCUSDT")
    """

    name: str
    instrument_type: InstrumentType
    yahoo_symbol: str | None = None
    binance_symbol: str | None = None

    def get_symbol(self, provider: str) -> str | None:
        """Get symbol for specific provider."""
        if provider == "yahoo":
            return self.yahoo_symbol
        elif provider == "binance":
            return self.binance_symbol
        return None


@runtime_checkable
class DataProviderProtocol(Protocol):
    """Protocol defining the interface for all data providers.

    All data providers must implement these methods to ensure
    consistent behavior across different data sources.
    """

    @property
    def name(self) -> str:
        """Provider name identifier."""
        ...

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data.

        Args:
            symbol: Trading symbol in provider's format
            timeframe: Candle timeframe
            bars: Number of bars to fetch

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
            Index should be datetime
        """
        ...

    async def get_latest_price(self, symbol: str) -> float | None:
        """Get the latest price for a symbol.

        Args:
            symbol: Trading symbol in provider's format

        Returns:
            Latest price or None if unavailable
        """
        ...

    async def close(self) -> None:
        """Clean up provider resources."""
        ...


class BaseDataProvider(ABC):
    """Abstract base class for data providers with common functionality.

    Provides default implementations for rate limiting and batch operations.
    """

    def __init__(
        self,
        rate_limit_per_second: float = 2.0,
    ):
        """Initialize base provider.

        Args:
            rate_limit_per_second: Maximum requests per second
        """
        self._rate_limit = rate_limit_per_second
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    async def _rate_limit_wait(self) -> None:
        """Wait if necessary to respect rate limits."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            min_interval = 1.0 / self._rate_limit
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data."""
        ...

    async def get_latest_price(self, symbol: str) -> float | None:
        """Get the latest price for a symbol.

        Default implementation uses get_candles with bars=1.
        """
        df = await self.get_candles(symbol, Timeframe.M1, bars=1)
        if df.empty:
            return None
        return float(df["close"].iloc[-1])

    async def get_multiple(
        self,
        symbols: list[str],
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> dict[str, pd.DataFrame]:
        """Fetch candles for multiple symbols concurrently.

        Default implementation fetches sequentially with rate limiting.
        Override for optimized batch fetching.

        Args:
            symbols: List of trading symbols
            timeframe: Candle timeframe
            bars: Number of bars per symbol

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        results: dict[str, pd.DataFrame] = {}

        async def fetch_one(symbol: str) -> tuple[str, pd.DataFrame]:
            df = await self.get_candles(symbol, timeframe, bars)
            return symbol, df

        tasks = [fetch_one(s) for s in symbols]
        for coro in asyncio.as_completed(tasks):
            symbol, df = await coro
            results[symbol] = df

        return results

    async def close(self) -> None:
        """Clean up provider resources. Override if needed."""
        pass


def ohlcv_list_to_dataframe(candles: list[OHLCV]) -> pd.DataFrame:
    """Convert list of OHLCV objects to DataFrame.

    Args:
        candles: List of OHLCV dataclass instances

    Returns:
        DataFrame with datetime index and OHLCV columns
    """
    if not candles:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

    data = [c.to_dict() for c in candles]
    df = pd.DataFrame(data)
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df


def normalize_timeframe(timeframe: Timeframe | str) -> str:
    """Normalize timeframe to string format.

    Args:
        timeframe: Timeframe enum or string

    Returns:
        Normalized timeframe string (e.g., "1h", "4h", "1d")
    """
    if isinstance(timeframe, Timeframe):
        return timeframe.value
    return str(timeframe).lower()
