from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx
import pandas as pd


FINNHUB_TIMEFRAME_MAP = {
    # Finnhub uses: 1, 5, 15, 30, 60, D, W, M
    "1": "1",
    "5": "5",
    "15": "15",
    "30": "30",
    "60": "60",
    "1h": "60",
    "4h": "240",  # not directly supported by finnhub candle, we will resample client-side
    "D": "D",
}


class FinnhubClient:
    def __init__(self, api_key: str, base_url: str = "https://finnhub.io/api/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        await self._client.aclose()

    async def get_forex_candles(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> pd.DataFrame:
        # For Forex, Finnhub uses endpoint: /forex/candle?symbol=OANDA:EUR_USD&resolution=5&from=...&to=...
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": start_ts,
            "to": end_ts,
            "token": self.api_key,
        }
        r = await self._client.get("/forex/candle", params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("s") != "ok":
            return pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"])  # empty
        df = pd.DataFrame({
            "t": data.get("t", []),
            "o": data.get("o", []),
            "h": data.get("h", []),
            "l": data.get("l", []),
            "c": data.get("c", []),
            "v": data.get("v", []),
        })
        if df.empty:
            return df
        df["dt"] = pd.to_datetime(df["t"], unit="s", utc=True)
        df.set_index("dt", inplace=True)
        df = df[["o", "h", "l", "c", "v"]]
        df.index.name = "datetime"
        return df

    async def get_latest_quote(self, symbol: str) -> Optional[Tuple[datetime, float]]:
        # Use /forex/quote?symbol=OANDA:EUR_USD
        params = {"symbol": symbol, "token": self.api_key}
        r = await self._client.get("/forex/quote", params=params)
        r.raise_for_status()
        data = r.json()
        # "p": current price, "t": timestamp
        p = data.get("p")
        t = data.get("t")
        if p is None or t is None:
            return None
        dt = datetime.fromtimestamp(t, tz=timezone.utc)
        return dt, float(p)

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
