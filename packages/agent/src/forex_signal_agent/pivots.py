from __future__ import annotations

import pandas as pd


def classical_pivots(prev_period: pd.DataFrame) -> dict:
    """
    prev_period: single-row DataFrame or Series with columns h,l,c (previous day candle)
    Returns dict with P, R1, R2, R3, S1, S2, S3
    """
    if isinstance(prev_period, pd.DataFrame):
        if prev_period.empty:
            return {}
        row = prev_period.iloc[-1]
    else:
        row = prev_period
    h, l, c = float(row["h"]), float(row["l"]), float(row["c"])
    P = (h + l + c) / 3
    R1 = 2 * P - l
    S1 = 2 * P - h
    R2 = P + (h - l)
    S2 = P - (h - l)
    R3 = h + 2 * (P - l)
    S3 = l - 2 * (h - P)
    return {"P": P, "R1": R1, "S1": S1, "R2": R2, "S2": S2, "R3": R3, "S3": S3}
