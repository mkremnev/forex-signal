from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .indicators import compute_indicators
from .pivots import classical_pivots


@dataclass
class Event:
    kind: str
    message: str
    importance: int = 1  # 1=info, 2=important


def analyze_pair(df: pd.DataFrame, daily_df: pd.DataFrame, symbol: str, adx_threshold: float, rsi_overbought: float, rsi_oversold: float) -> List[Event]:
    events: List[Event] = []
    if df.empty:
        return events
    ind = compute_indicators(df)
    last = ind.iloc[-1]

    # Trend detection via EMA and ADX
    ema_trend = None
    if pd.notna(last.get("ema20")) and pd.notna(last.get("ema50")):
        if last["ema20"] > last["ema50"]:
            ema_trend = "up"
        elif last["ema20"] < last["ema50"]:
            ema_trend = "down"

    adx_ok = pd.notna(last.get("adx")) and last["adx"] >= adx_threshold

    if ema_trend == "up" and adx_ok:
        events.append(Event(
            kind="trend_up",
            message=f"📈 {symbol}: Восходящий тренд (EMA20>EMA50, ADX≥{adx_threshold:.0f}).",
            importance=2,
        ))
    elif ema_trend == "down" and adx_ok:
        events.append(Event(
            kind="trend_down",
            message=f"📉 {symbol}: Нисходящий тренд (EMA20<EMA50, ADX≥{adx_threshold:.0f}).",
            importance=2,
        ))

    # MACD cross
    if pd.notna(last.get("macd")) and pd.notna(last.get("macd_signal")):
        prev = ind.iloc[-2] if len(ind) > 1 else None
        if prev is not None and pd.notna(prev.get("macd")) and pd.notna(prev.get("macd_signal")):
            if prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]:
                events.append(Event(kind="macd_bull", message=f"🟢 {symbol}: бычий перескок MACD выше сигнальной.", importance=1))
            if prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]:
                events.append(Event(kind="macd_bear", message=f"🔴 {symbol}: медвежий перескок MACD ниже сигнальной.", importance=1))

    # RSI
    if pd.notna(last.get("rsi")):
        if last["rsi"] >= rsi_overbought:
            events.append(Event(kind="rsi_overbought", message=f"⚠️ {symbol}: RSI={last['rsi']:.1f} — перекупленность.", importance=1))
        elif last["rsi"] <= rsi_oversold:
            events.append(Event(kind="rsi_oversold", message=f"⚠️ {symbol}: RSI={last['rsi']:.1f} — перепроданность.", importance=1))

    # Classical pivots from previous day
    daily = daily_df.dropna()
    if not daily.empty and len(daily) >= 2:
        piv = classical_pivots(daily.iloc[-2])  # previous day's pivots
        price = float(last["c"]) if pd.notna(last.get("c")) else None
        if price is not None and piv:
            for level_name in ["S3", "S2", "S1", "P", "R1", "R2", "R3"]:
                lvl = piv[level_name]
                # Trigger when price is within 0.05% of pivot level
                if lvl and abs(price - lvl) / lvl <= 0.0005:
                    emoji = "🟨" if level_name == "P" else ("🟩" if level_name.startswith("R") else "🟥")
                    events.append(Event(
                        kind=f"pivot_touch_{level_name}",
                        message=f"{emoji} {symbol}: Цена у уровня {level_name} ({lvl:.5f}).",
                        importance=2 if level_name in ("R2", "S2", "R3", "S3") else 1,
                    ))
                    break

    return events
