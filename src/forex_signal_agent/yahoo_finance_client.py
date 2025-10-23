from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

import asyncio
import pandas as pd
import yfinance as yf


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


def _oanda_to_yahoo_symbol(symbol: str) -> str:
    # Convert formats like "OANDA:EUR_USD" or "EUR_USD" or "EUR/USD" -> "EURUSD=X"
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]
    symbol = symbol.replace("/", "_")
    if "_" in symbol:
        base, quote = symbol.split("_", 1)
    else:
        # attempt 3+3 split as fallback
        base, quote = symbol[:3], symbol[3:]
    return f"{base}{quote}=X"


class YahooFinanceClient:
    def __init__(self) -> None:
        # yfinance is synchronous; we'll run in thread pool via asyncio.to_thread
        pass

    async def close(self):
        # Nothing to close for yfinance
        return

    @staticmethod
    def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        o = df["o"].resample("4H").first()
        h = df["h"].resample("4H").max()
        l = df["l"].resample("4H").min()
        c = df["c"].resample("4H").last()
        v = df["v"].resample("4H").sum()
        out = pd.concat([o, h, l, c, v], axis=1)
        out.columns = ["o", "h", "l", "c", "v"]
        return out.dropna()

    async def get_forex_candles(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> pd.DataFrame:
        ticker = _oanda_to_yahoo_symbol(symbol)
        interval = resolution  # already mapped by caller using YAHOO_TIMEFRAME_MAP
        start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

        def _download():
            df = yf.download(tickers=ticker, interval=interval, start=start_dt, end=end_dt, progress=False, group_by="ticker")
            if df is None or len(df) == 0:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"]).set_index(pd.DatetimeIndex([], name="datetime"))
            # yfinance returns columns: Open, High, Low, Close, Adj Close, Volume
            # Ensure tz-aware UTC index
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
            out = pd.DataFrame({
                "o": pd.to_numeric(df["Open"], errors="coerce"),
                "h": pd.to_numeric(df["High"], errors="coerce"),
                "l": pd.to_numeric(df["Low"], errors="coerce"),
                "c": pd.to_numeric(df["Close"], errors="coerce"),
                "v": pd.to_numeric(df.get("Volume", 0), errors="coerce"),
            })
            out.index.name = "datetime"
            return out.dropna()

        df: pd.DataFrame = await asyncio.to_thread(_download)
        return df

    async def get_latest_quote(self, symbol: str) -> Optional[Tuple[datetime, float]]:
        ticker = _oanda_to_yahoo_symbol(symbol)

        def _last():
            t = yf.Ticker(ticker)
            # Try fast_info first
            price = None
            try:
                fi = t.fast_info
                price = getattr(fi, "last_price", None) or fi.get("last_price")
            except Exception:
                price = None
            if price is None:
                hist = t.history(period="1d", interval="1m")
                if hist is not None and len(hist) > 0:
                    last_row = hist.iloc[-1]
                    # yfinance uses tz-aware index
                    dt = hist.index[-1].to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt, float(last_row["Close"]) if "Close" in last_row else float("nan")
                return None
            # yfinance doesn't always provide timestamp alongside fast_info; approximate with now UTC
            return datetime.now(tz=timezone.utc), float(price)

        result = await asyncio.to_thread(_last)
        return result
