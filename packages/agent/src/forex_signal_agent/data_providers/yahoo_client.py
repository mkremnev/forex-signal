"""Yahoo Finance data provider for forex and commodities.

Uses yfinance library to fetch OHLCV data. Symbols are expected in
Yahoo Finance format (e.g., "EURUSD=X", "GC=F") directly from dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .base import BaseDataProvider, Timeframe, normalize_timeframe

logger = logging.getLogger(__name__)

# Yahoo Finance timeframe mapping
TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "60m",  # Resample from 1h
    "1d": "1d",
    "1w": "1wk",
}

# Maximum history limits by interval
MAX_HISTORY: dict[str, int] = {
    "1m": 7,  # 7 days
    "5m": 60,  # 60 days
    "15m": 60,
    "30m": 60,
    "60m": 730,  # 2 years
    "1d": 10000,  # Practically unlimited
    "1wk": 10000,
}


class YahooFinanceProvider(BaseDataProvider):
    """Yahoo Finance data provider.

    Fetches forex, commodities, and index data from Yahoo Finance.
    Symbols should be provided in Yahoo Finance format directly
    (e.g., "EURUSD=X" for forex, "GC=F" for gold futures).

    Example:
        provider = YahooFinanceProvider()
        df = await provider.get_candles("EURUSD=X", "1h", bars=100)
    """

    def __init__(self, rate_limit_per_second: float = 2.0):
        """Initialize Yahoo Finance provider.

        Args:
            rate_limit_per_second: Rate limit for API calls
        """
        super().__init__(rate_limit_per_second)

    @property
    def name(self) -> str:
        return "yahoo"

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        bars: int = 100,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data from Yahoo Finance.

        Args:
            symbol: Trading symbol in Yahoo Finance format (e.g., "EURUSD=X")
            timeframe: Candle timeframe
            bars: Number of bars to fetch

        Returns:
            DataFrame with datetime index and columns: open, high, low, close, volume
        """
        await self._rate_limit_wait()

        tf_str = normalize_timeframe(timeframe)
        yf_interval = TIMEFRAME_MAP.get(tf_str)
        needs_resample = tf_str == "4h"

        if yf_interval is None:
            logger.warning(f"Unsupported timeframe {tf_str}, falling back to 1h")
            yf_interval = "60m"

        # Calculate period based on bars needed
        if needs_resample:
            # For 4h, we need 4x more 1h bars
            bars_to_fetch = bars * 4 + 10  # Extra buffer
        else:
            bars_to_fetch = bars + 10

        # Determine period string
        period = self._calculate_period(yf_interval, bars_to_fetch)

        def _download() -> pd.DataFrame:
            try:
                df = yf.download(
                    tickers=symbol,
                    interval=yf_interval,
                    period=period,
                    progress=False,
                    auto_adjust=True,
                    group_by="column",
                )

                if df is None or df.empty:
                    logger.warning(f"No data returned for {symbol}")
                    return self._empty_dataframe()

                # Normalize columns
                df = self._normalize_columns(df, symbol)
                if df.empty:
                    return self._empty_dataframe()

                # Ensure UTC timezone
                df = self._ensure_utc_index(df)

                return df

            except Exception as e:
                logger.error(f"Error downloading {symbol}: {e}")
                return self._empty_dataframe()

        try:
            df = await asyncio.to_thread(_download)

            if df.empty:
                return df

            # Resample to 4h if needed
            if needs_resample:
                df = self._resample_to_4h(df)

            # Limit to requested number of bars
            if len(df) > bars:
                df = df.iloc[-bars:]

            return df

        except Exception as e:
            logger.error(f"Failed to fetch candles for {symbol}: {e}")
            return self._empty_dataframe()

    async def get_latest_price(self, symbol: str) -> float | None:
        """Get the latest price for a symbol.

        Args:
            symbol: Trading symbol in Yahoo Finance format

        Returns:
            Latest price or None if unavailable
        """
        await self._rate_limit_wait()

        def _get_price() -> float | None:
            try:
                ticker = yf.Ticker(symbol)

                # Try fast_info first (faster)
                try:
                    fast_info = ticker.fast_info
                    price = getattr(fast_info, "last_price", None)
                    if price is not None and not pd.isna(price):
                        return float(price)
                except Exception:
                    pass

                # Fallback to history
                hist = ticker.history(period="1d", interval="1m")
                if hist is not None and not hist.empty:
                    close_col = "Close" if "Close" in hist.columns else "close"
                    if close_col in hist.columns:
                        close_price = hist[close_col].iloc[-1]
                        if not pd.isna(close_price):
                            return float(close_price)

                return None

            except Exception as e:
                logger.error(f"Error getting latest price for {symbol}: {e}")
                return None

        try:
            return await asyncio.to_thread(_get_price)
        except Exception as e:
            logger.error(f"Failed to get latest price for {symbol}: {e}")
            return None

    def _calculate_period(self, interval: str, bars: int) -> str:
        """Calculate period string for Yahoo Finance API.

        Args:
            interval: Yahoo Finance interval string
            bars: Number of bars needed

        Returns:
            Period string (e.g., "7d", "30d", "1y")
        """
        max_days = MAX_HISTORY.get(interval, 60)

        if interval == "1m":
            days = min((bars // 60) + 1, max_days)
        elif interval in ("5m", "15m", "30m"):
            minutes_per_bar = int(interval.replace("m", ""))
            days = min((bars * minutes_per_bar // 1440) + 1, max_days)
        elif interval == "60m":
            days = min((bars // 24) + 1, max_days)
        elif interval == "1d":
            days = min(bars + 5, max_days)
        elif interval == "1wk":
            days = min(bars * 7 + 7, max_days)
        else:
            days = min(bars, max_days)

        days = max(1, days)

        if days > 365:
            return f"{(days // 365) + 1}y"
        elif days > 30:
            return f"{days}d"
        else:
            return f"{days}d"

    def _normalize_columns(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Normalize DataFrame columns to standard format.

        Args:
            df: Raw DataFrame from yfinance
            symbol: Symbol for MultiIndex handling

        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df = self._flatten_multiindex(df, symbol)

        if df.empty:
            return self._empty_dataframe()

        # Build case-insensitive column map
        colmap = {str(c).lower(): c for c in df.columns}

        # Use Adj Close as Close if Close is missing
        if "close" not in colmap and "adj close" in colmap:
            colmap["close"] = colmap["adj close"]

        def _get_column(name: str) -> pd.Series:
            key = colmap.get(name.lower())
            if key is None:
                return pd.Series(index=df.index, dtype="float64")
            return pd.to_numeric(df[key], errors="coerce")

        result = pd.DataFrame({
            "open": _get_column("open"),
            "high": _get_column("high"),
            "low": _get_column("low"),
            "close": _get_column("close"),
            "volume": _get_column("volume").fillna(0),
        })

        # Drop rows with missing OHLC data
        result = result.dropna(subset=["open", "high", "low", "close"])

        return result

    def _flatten_multiindex(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Flatten MultiIndex columns from yfinance.

        Args:
            df: DataFrame with MultiIndex columns
            symbol: Symbol to extract from MultiIndex

        Returns:
            DataFrame with flat columns
        """
        if not isinstance(df.columns, pd.MultiIndex):
            return df

        nlevels = df.columns.nlevels
        field_names = {"open", "high", "low", "close", "adj close", "volume"}

        # Find ticker level
        for i in range(nlevels):
            vals = [str(v) for v in df.columns.get_level_values(i)]
            if symbol in vals:
                try:
                    df = df.xs(symbol, axis=1, level=i, drop_level=True)
                    break
                except Exception:
                    pass

        # If still MultiIndex, flatten by last level
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[-1]) for c in df.columns]

        return df

    def _ensure_utc_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure DataFrame has UTC timezone-aware datetime index.

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with UTC timezone-aware index
        """
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        df.index.name = "datetime"
        return df

    def _resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample 1-hour data to 4-hour candles.

        Args:
            df: DataFrame with 1-hour OHLCV data

        Returns:
            DataFrame with 4-hour OHLCV data
        """
        if df.empty or len(df) < 4:
            return df

        resampled = pd.DataFrame({
            "open": df["open"].resample("4h").first(),
            "high": df["high"].resample("4h").max(),
            "low": df["low"].resample("4h").min(),
            "close": df["close"].resample("4h").last(),
            "volume": df["volume"].resample("4h").sum(),
        })

        return resampled.dropna()

    def _empty_dataframe(self) -> pd.DataFrame:
        """Create an empty DataFrame with proper structure.

        Returns:
            Empty DataFrame with datetime index and OHLCV columns
        """
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        ).set_index(pd.DatetimeIndex([], name="datetime", tz="UTC"))
