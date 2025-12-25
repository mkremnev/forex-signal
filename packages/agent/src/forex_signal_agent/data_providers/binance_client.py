"""Binance data provider for cryptocurrency markets.

Uses CCXT library for unified exchange API. Symbols are expected in
Binance format (e.g., "BTCUSDT", "ETHUSDT") directly from dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

try:
    import ccxt.async_support as ccxt
except ImportError:
    ccxt = None  # type: ignore

from .base import BaseDataProvider, Timeframe, normalize_timeframe

logger = logging.getLogger(__name__)

# CCXT timeframe mapping
TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}


class BinanceProvider(BaseDataProvider):
    """Binance cryptocurrency data provider.

    Uses CCXT async library to fetch OHLCV data from Binance.
    Symbols should be provided in Binance format directly
    (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").

    Example:
        provider = BinanceProvider()
        df = await provider.get_candles("BTCUSDT", "1h", bars=100)
        await provider.close()
    """

    def __init__(
        self,
        rate_limit_per_second: float = 10.0,
        sandbox: bool = False,
    ):
        """Initialize Binance provider.

        Args:
            rate_limit_per_second: Rate limit for API calls
            sandbox: Use Binance testnet if True
        """
        super().__init__(rate_limit_per_second)

        if ccxt is None:
            raise ImportError(
                "ccxt is required for BinanceProvider. "
                "Install it with: pip install ccxt"
            )

        self._sandbox = sandbox
        self._exchange: Any | None = None
        self._exchange_lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "binance"

    async def _get_exchange(self) -> Any:
        """Lazily initialize and return the exchange instance.

        Returns:
            CCXT Binance exchange instance
        """
        async with self._exchange_lock:
            if self._exchange is None:
                self._exchange = ccxt.binance({
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot",
                    },
                })
                if self._sandbox:
                    self._exchange.set_sandbox_mode(True)
                    logger.info("Binance provider initialized in sandbox mode")
                else:
                    logger.info("Binance provider initialized")

            return self._exchange

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data from Binance.

        Args:
            symbol: Trading symbol in Binance format (e.g., "BTCUSDT")
            timeframe: Candle timeframe
            bars: Number of bars to fetch

        Returns:
            DataFrame with datetime index and columns: open, high, low, close, volume
        """
        await self._rate_limit_wait()

        tf_str = normalize_timeframe(timeframe)
        ccxt_timeframe = TIMEFRAME_MAP.get(tf_str, "1h")

        # Convert symbol format if needed (BTCUSDT -> BTC/USDT)
        ccxt_symbol = self._to_ccxt_symbol(symbol)

        try:
            exchange = await self._get_exchange()

            # Fetch OHLCV data
            # CCXT returns: [[timestamp, open, high, low, close, volume], ...]
            ohlcv = await exchange.fetch_ohlcv(
                symbol=ccxt_symbol,
                timeframe=ccxt_timeframe,
                limit=bars,
            )

            if not ohlcv:
                logger.warning(f"No data returned for {symbol}")
                return self._empty_dataframe()

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            # Convert timestamp to datetime
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.set_index("datetime", inplace=True)
            df.drop(columns=["timestamp"], inplace=True)

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Sort by datetime
            df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}")
            return self._empty_dataframe()

    async def get_latest_price(self, symbol: str) -> float | None:
        """Get the latest price for a symbol.

        Args:
            symbol: Trading symbol in Binance format

        Returns:
            Latest price or None if unavailable
        """
        await self._rate_limit_wait()

        ccxt_symbol = self._to_ccxt_symbol(symbol)

        try:
            exchange = await self._get_exchange()
            ticker = await exchange.fetch_ticker(ccxt_symbol)

            if ticker and "last" in ticker:
                price = ticker["last"]
                if price is not None:
                    return float(price)

            return None

        except Exception as e:
            logger.error(f"Error getting latest price for {symbol}: {e}")
            return None

    async def get_multiple(
        self,
        symbols: list[str],
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> dict[str, pd.DataFrame]:
        """Fetch candles for multiple symbols concurrently.

        Optimized for Binance API with concurrent fetching.

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

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)

        async def fetch_with_semaphore(symbol: str) -> tuple[str, pd.DataFrame]:
            async with semaphore:
                return await fetch_one(symbol)

        tasks = [fetch_with_semaphore(s) for s in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Error in batch fetch: {result}")
                continue
            symbol, df = result
            results[symbol] = df

        return results

    async def close(self) -> None:
        """Close the exchange connection."""
        async with self._exchange_lock:
            if self._exchange is not None:
                try:
                    await self._exchange.close()
                    logger.info("Binance provider closed")
                except Exception as e:
                    logger.error(f"Error closing Binance provider: {e}")
                finally:
                    self._exchange = None

    def _to_ccxt_symbol(self, symbol: str) -> str:
        """Convert Binance symbol to CCXT format.

        Args:
            symbol: Symbol in Binance format (e.g., "BTCUSDT")

        Returns:
            Symbol in CCXT format (e.g., "BTC/USDT")
        """
        # If already in CCXT format, return as-is
        if "/" in symbol:
            return symbol

        # Common quote currencies
        quote_currencies = ["USDT", "BUSD", "USDC", "BTC", "ETH", "BNB"]

        for quote in quote_currencies:
            if symbol.endswith(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"

        # Fallback: assume USDT as quote
        logger.warning(f"Could not parse symbol {symbol}, assuming USDT quote")
        return symbol

    def _empty_dataframe(self) -> pd.DataFrame:
        """Create an empty DataFrame with proper structure.

        Returns:
            Empty DataFrame with datetime index and OHLCV columns
        """
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        ).set_index(pd.DatetimeIndex([], name="datetime", tz="UTC"))
