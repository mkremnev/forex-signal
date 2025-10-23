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
            # Yahoo intraday data has lookback caps. Prefer period for intraday intervals.
            is_daily = interval == "1d"
            kwargs = {
                "tickers": ticker,
                "interval": interval,
                "progress": False,
                "auto_adjust": True,
                "group_by": "column",
            }
            if is_daily:
                kwargs.update({"start": start_dt, "end": end_dt})
            else:
                # Compute requested duration (days) and cap by Yahoo limits
                requested_days = max(1, int((end_dt - start_dt).total_seconds() // 86400) + 1)
                if interval == "1m":
                    cap_days = 7
                else:
                    # 2m/5m/15m/30m/60m typically allow up to ~60 days
                    cap_days = 60
                period_days = max(1, min(requested_days, cap_days))
                kwargs.update({"period": f"{period_days}d"})
            df = yf.download(**kwargs)

            if df is None or len(df) == 0:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"]).set_index(pd.DatetimeIndex([], name="datetime"))

            # Если MultiIndex (может случиться с некоторыми версиями yfinance), свернуть до уровня тикера
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    if ticker in df.columns.get_level_values(0):
                        df = df.xs(ticker, axis=1, level=0, drop_level=True)
                    else:
                        first = df.columns.get_level_values(0)[0]
                        df = df.xs(first, axis=1, level=0, drop_level=True)
                except Exception:
                    # В качестве запасного варианта попробует сделать выравнивание, взяв имена второго уровня.
                    df.columns = [str(c[-1]) for c in df.columns]

            # Build case-insensitive column map
            colmap = {str(c).lower(): c for c in df.columns}

            def _pick(name: str):
                key = colmap.get(name.lower())
                if key is None:
                    return pd.Series(index=df.index, dtype="float64")
                return pd.to_numeric(df[key], errors="coerce")

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
