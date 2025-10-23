from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
import pandas as pd


ALPHA_TIMEFRAME_MAP = {
    # Alpha Vantage supports: 1min, 5min, 15min, 30min, 60min for intraday; daily via separate endpoint
    "1": "1min",
    "5": "5min",
    "15": "15min",
    "30": "30min",
    "60": "60min",
    "1h": "60min",
    "4h": "60min",  # will resample client-side
    "D": "D",  # special case handled via FX_DAILY
}


def _parse_symbol(symbol: str) -> Tuple[str, str]:
    # Expect formats like "OANDA:EUR_USD" or "EUR_USD"
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]
    if "/" in symbol:
        left, right = symbol.split("/", 1)
    elif "_" in symbol:
        left, right = symbol.split("_", 1)
    else:
        # fallback, not expected; try 3+3 split
        left, right = symbol[:3], symbol[3:]
    return left, right


class AlphaVantageClient:
    def __init__(self, api_key: str, base_url: str = "https://www.alphavantage.co") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        await self._client.aclose()

    async def get_forex_candles(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> pd.DataFrame:
        from_sym, to_sym = _parse_symbol(symbol)
        if resolution == "D":
            # Use FX_DAILY
            params = {
                "function": "FX_DAILY",
                "from_symbol": from_sym,
                "to_symbol": to_sym,
                "outputsize": "full",
                "apikey": self.api_key,
                "datatype": "json",
            }
            r = await self._client.get("/query", params=params)
            r.raise_for_status()
            data = r.json()
            ts_key = next((k for k in data.keys() if k.startswith("Time Series FX")), None)
            if not ts_key:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"])  # Alpha Vantage FX daily has no volume
            ts = data.get(ts_key, {})
            records = []
            for t_str, vals in ts.items():
                try:
                    dt = pd.to_datetime(t_str, utc=True)
                except Exception:
                    continue
                ts_sec = int(dt.timestamp())
                if ts_sec < start_ts or ts_sec > end_ts:
                    continue
                o = float(vals.get("1. open"))
                h = float(vals.get("2. high"))
                l = float(vals.get("3. low"))
                c = float(vals.get("4. close"))
                records.append((dt, o, h, l, c, 0.0))
            if not records:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"])  # empty
            df = pd.DataFrame(records, columns=["dt", "o", "h", "l", "c", "v"]).sort_values("dt")
        else:
            # Intraday via FX_INTRADAY
            params = {
                "function": "FX_INTRADAY",
                "from_symbol": from_sym,
                "to_symbol": to_sym,
                "interval": resolution,  # e.g., 5min
                "outputsize": "full",
                "apikey": self.api_key,
                "datatype": "json",
            }
            r = await self._client.get("/query", params=params)
            r.raise_for_status()
            data = r.json()
            ts_key = next((k for k in data.keys() if k.startswith("Time Series FX")), None)
            if not ts_key:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"])  # empty
            ts = data.get(ts_key, {})
            records = []
            for t_str, vals in ts.items():
                try:
                    dt = pd.to_datetime(t_str, utc=True)
                except Exception:
                    continue
                ts_sec = int(dt.timestamp())
                if ts_sec < start_ts or ts_sec > end_ts:
                    continue
                o = float(vals.get("1. open"))
                h = float(vals.get("2. high"))
                l = float(vals.get("3. low"))
                c = float(vals.get("4. close"))
                v = float(vals.get("5. volume", 0.0))
                records.append((dt, o, h, l, c, v))
            if not records:
                return pd.DataFrame(columns=["o", "h", "l", "c", "v"])  # empty
            df = pd.DataFrame(records, columns=["dt", "o", "h", "l", "c", "v"]).sort_values("dt")

        df.set_index("dt", inplace=True)
        df.index.name = "datetime"
        # Ensure numeric types
        for col in ["o", "h", "l", "c", "v"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()
        return df

    async def get_latest_quote(self, symbol: str) -> Optional[Tuple[datetime, float]]:
        from_sym, to_sym = _parse_symbol(symbol)
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_sym,
            "to_currency": to_sym,
            "apikey": self.api_key,
        }
        r = await self._client.get("/query", params=params)
        r.raise_for_status()
        data = r.json()
        quote = data.get("Realtime Currency Exchange Rate")
        if not quote:
            return None
        rate_str = quote.get("5. Exchange Rate")
        ts_str = quote.get("6. Last Refreshed")
        if not rate_str or not ts_str:
            return None
        # Alpha Vantage returns time possibly without timezone; treat as UTC
        dt = pd.to_datetime(ts_str, utc=True).to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, float(rate_str)

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
