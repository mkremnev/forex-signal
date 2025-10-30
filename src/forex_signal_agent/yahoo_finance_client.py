from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple
import logging

import asyncio
import pandas as pd
import yfinance as yf

from .exceptions import DataProviderException

YAHOO_TIMEFRAME_MAP = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "60m",
    "1h": "60m",
    "4h": "60m",  # resample client-side
    "D": "1d",
}

logger = logging.getLogger(__name__)


def _yahoo_symbol(symbol: str) -> str:
    # Convert formats like "EUR_USD" or "EUR_USD" or "EUR/USD" -> "EURUSD=X"
    return symbol.replace('_', '').replace(':X', '=X').replace(':F', '=F')


class YahooFinanceClient:
    def __init__(self) -> None:
        # yfinance is synchronous; we'll run in thread pool via asyncio.to_thread
        pass

    async def close(self):
        # Nothing to close for yfinance
        return

    @staticmethod
    def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
        """Optimized version of 4-hour resampling"""
        if df.empty:
            return df

        # Only resample if we have more than 4 hours of data
        if len(df) < 4:
            return df
        
        o = df["o"].resample("4h").first()
        h = df["h"].resample("4h").max()
        l = df["l"].resample("4h").min()
        c = df["c"].resample("4h").last()
        v = df["v"].resample("4h").sum()
        out = pd.concat([o, h, l, c, v], axis=1)
        out.columns = ["o", "h", "l", "c", "v"]
        return out.dropna()

    async def get_forex_candles(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> pd.DataFrame:
        """Fetch forex candles with improved error handling"""
        ticker = _yahoo_symbol(symbol)
        interval = resolution  # already mapped by caller using YAHOO_TIMEFRAME_MAP
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

        def _download():
            try:
                # Выбор стратегии загрузки: период внутридневного использования, начало/конец ежедневного использования
                intraday_intervals = {"1m", "5m", "15m", "30m", "60m"}
                is_intraday = interval in intraday_intervals

                if is_intraday:
                    # Определить период, соблюдая лимиты Yahoo
                    total_seconds = max(1, int((end_dt - start_dt).total_seconds()))
                    days = (total_seconds + 86399) // 86400  # ceil to days
                    max_days = 7 if interval == "1m" else 60
                    days = max(1, min(days, max_days))
                    period = f"{days}d"
                    df = yf.download(
                        tickers=ticker,
                        interval=interval,
                        period=period,
                        progress=False,
                        auto_adjust=True,
                        group_by="column",
                    )
                else:
                    # Daily
                    df = yf.download(
                        tickers=ticker,
                        interval="1d",
                        start=start_dt,
                        end=end_dt,
                        progress=False,
                        auto_adjust=True,
                        group_by="column",
                    )

                if df is None or len(df) == 0:
                    logger.warning(f"No data returned for {ticker} with interval {interval}")
                    return pd.DataFrame(columns=["o", "h", "l", "c", "v"]).set_index(pd.DatetimeIndex([], name="datetime"))

                # Normalize columns: handle MultiIndex of various shapes
                if isinstance(df.columns, pd.MultiIndex):
                    # Identify levels
                    nlvls = df.columns.nlevels
                    field_names = {"open", "high", "low", "close", "adj close", "volume"}
                    field_level = None
                    for i in range(nlvls):
                        try:
                            vals = [str(v).lower() for v in df.columns.get_level_values(i)]
                        except Exception:
                            vals = []
                        if any(v in field_names for v in vals):
                            field_level = i
                            break
                    # Try to slice by ticker level if present
                    ticker_level = None
                    for i in range(nlvls):
                        vals = [str(v) for v in df.columns.get_level_values(i)]
                        if ticker in vals:
                            ticker_level = i
                            break
                    if ticker_level is not None:
                        try:
                            df = df.xs(ticker, axis=1, level=ticker_level, drop_level=True)
                        except Exception:
                            pass
                    # If still MultiIndex and we know which level has fields, group by that
                    if isinstance(df.columns, pd.MultiIndex) and field_level is not None:
                        try:
                            df = df.T.groupby(by=field_level).first()
                        except Exception:
                            df.columns = [str(c[-1]) for c in df.columns]
                    # If still MultiIndex, flatten by last level
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [str(c[-1]) for c in df.columns]

                # Build case-insensitive column map
                colmap = {str(c).lower(): c for c in df.columns}
                # Allow Adj Close as Close if Close missing
                if "close" not in colmap and "adj close" in colmap:
                    colmap["close"] = colmap["adj close"]

                def _pick(name: str):
                    key = colmap.get(name.lower())
                    if key is None:
                        return pd.Series(index=df.index, dtype="float64")
                    return pd.to_numeric(df[key])

                o = _pick("Open")
                h = _pick("High")
                l = _pick("Low")
                c = _pick("Close")
                v = _pick("Volume")

                out = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": v})

                # Ensure tz-aware UTC index
                if out.index.tz is None:
                    out.index = out.index.tz_localize("UTC")
                else:
                    out.index = out.index.tz_convert("UTC")
                out.index.name = "datetime"
                # Drop rows where O/H/L/C are missing
                return out.dropna(subset=["o", "h", "l", "c"])
            except Exception as e:
                logger.error(f"Error downloading data for {ticker}: {e}")
                # Return empty DataFrame in case of error
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"]).set_index(pd.DatetimeIndex([], name="datetime"))

        try:
            df: pd.DataFrame = await asyncio.to_thread(_download)
            if df.empty:
                logger.warning(f"Empty result for {symbol} with interval {resolution}")
            return df
        except Exception as e:
            logger.error(f"DataProviderException in get_forex_candles for {symbol} with resolution {resolution}: {e}")
            raise DataProviderException(f"Failed to fetch candles for {symbol}: {e}") from e

    async def get_latest_quote(self, symbol: str) -> Optional[Tuple[datetime, float]]:
        """Get the latest quote with improved error handling"""
        ticker = _yahoo_symbol(symbol)

        def _last():
            try:
                t = yf.Ticker(ticker)
                # Try fast_info first
                price = None
                try:
                    fi = t.fast_info
                    price = getattr(fi, "last_price", None) or fi.get("last_price")
                except Exception:
                    logger.warning(f"Could not get fast_info for {ticker}")
                    price = None
                if price is not None and not pd.isna(price):
                    # yfinance doesn't always provide timestamp alongside fast_info; approximate with now UTC
                    return datetime.now(tz=timezone.utc), float(price)
                
                # Fallback to history if fast_info fails
                hist = t.history(period="1d", interval="1m")
                if hist is not None and len(hist) > 0:
                    last_row = hist.iloc[-1]
                    # yfinance uses tz-aware index
                    dt = hist.index[-1].to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    close_price = last_row.get("Close")
                    if close_price is not None and not pd.isna(close_price):
                        return dt, float(close_price)
                return None
            except Exception as e:
                logger.error(f"Error getting latest quote for {ticker}: {e}")
                return None

        try:
            result = await asyncio.to_thread(_last)
            return result
        except Exception as e:
            logger.error(f"DataProviderException in get_latest_quote for {symbol}: {e}")
            raise DataProviderException(f"Failed to get latest quote for {symbol}: {e}") from e
