from __future__ import annotations

import pandas as pd
import numpy as np
import talib


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects df with columns: o,h,l,c,v and DatetimeIndex (UTC).
    Returns df with added columns: ema20, ema50, adx, macd, macd_signal, macd_hist, rsi
    """
    if df.empty:
        return df.copy()
    
    # Ensure data is in float64 format for TA-Lib compatibility
    out = df.copy()
    close = out["c"].values.astype(float)
    high = out["h"].values.astype(float)
    low = out["l"].values.astype(float)

    out["ema20"] = talib.EMA(close, timeperiod=20)
    out["ema50"] = talib.EMA(close, timeperiod=50)
    out["adx"] = talib.ADX(high, low, close, timeperiod=14)
    macd, macds, macdh = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    out["macd"] = macd
    out["macd_signal"] = macds
    out["macd_hist"] = macdh
    out["rsi"] = talib.RSI(close, timeperiod=14)
    return out
