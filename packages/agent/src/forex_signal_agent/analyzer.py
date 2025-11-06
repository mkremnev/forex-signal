from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import pandas as pd

from .indicators import compute_indicators
from .pivots import classical_pivots

# Constants
PIVOT_PROXIMITY_THRESHOLD = 0.0005  # 0.05% proximity threshold for pivot levels
MIN_DAILY_BARS_FOR_PIVOTS = 2
TREND_IMPORTANCE = 1
TREND_IMPORTANCE_STRENGTH = 2
SIGNAL_IMPORTANCE = 1
MAJOR_PIVOT_IMPORTANCE = 2
MINOR_PIVOT_IMPORTANCE = 1

TrendDirection = Literal["up", "down"]
PivotLevel = Literal["S3", "S2", "S1", "P", "R1", "R2", "R3"]


@dataclass
class Event:
    """Represents a trading signal or market event."""
    kind: str
    message: str
    importance: int = 1  # 1=info, 2=important


def _detect_ema_trend(last_bar: pd.Series) -> Optional[TrendDirection]:
    """
    Detect trend direction based on EMA20 and EMA50 relationship.

    Args:
        last_bar: The most recent indicator bar

    Returns:
        "up" if EMA20 > EMA50, "down" if EMA20 < EMA50, None otherwise
    """
    if pd.notna(last_bar.get("ema20")) and pd.notna(last_bar.get("ema50")):
        if last_bar["ema20"] > last_bar["ema50"]:
            return "up"
        elif last_bar["ema20"] < last_bar["ema50"]:
            return "down"
    return None


def _is_adx_strong(last_bar: pd.Series, adx_threshold: float) -> bool:
    """
    Check if ADX indicates a strong trend.

    Args:
        last_bar: The most recent indicator bar
        adx_threshold: Minimum ADX value for strong trend

    Returns:
        True if ADX is above threshold, False otherwise
    """
    return pd.notna(last_bar.get("adx")) and last_bar["adx"] >= adx_threshold


def _analyze_trend(
    last_bar: pd.Series,
    symbol: str,
    adx_threshold: float
) -> List[Event]:
    """
    Analyze trend using EMA and ADX indicators.

    Args:
        last_bar: The most recent indicator bar
        symbol: Trading pair symbol
        adx_threshold: Minimum ADX value for strong trend

    Returns:
        List of trend events
    """
    events: List[Event] = []
    ema_trend = _detect_ema_trend(last_bar)
    adx_strong = _is_adx_strong(last_bar, adx_threshold)

    # Only trigger trend messages when there's a clear change in trend direction
    # and the trend is sufficiently strong
    if ema_trend == "up" and adx_strong:
        # Only send message for new uptrend (not continuation)
        events.append(Event(
            kind="trend_up",
            message=f"📈 {symbol}: Восходящий тренд (EMA20>EMA50, ADX≥{adx_threshold:.0f}).",
            importance=TREND_IMPORTANCE,
        ))
    elif ema_trend == "down" and adx_strong:
        # Only send message for new downtrend (not continuation)
        events.append(Event(
            kind="trend_down",
            message=f"📉 {symbol}: Нисходящий тренд (EMA20<EMA50, ADX≥{adx_threshold:.0f}).",
            importance=TREND_IMPORTANCE,
        ))

    return events


def _analyze_trend_continuation(
    indicators: pd.DataFrame,
    last_bar: pd.Series,
    symbol: str,
    adx_threshold: float
) -> List[Event]:
    """
    Analyze trend continuation - detect when a trend is strengthening or continuing.

    Args:
        indicators: DataFrame with all indicators
        last_bar: The most recent indicator bar
        symbol: Trading pair symbol
        adx_threshold: Minimum ADX value for strong trend

    Returns:
        List of trend continuation events
    """
    events: List[Event] = []
    
    if len(indicators) < 2:
        return events
        
    prev_bar = indicators.iloc[-2]
    ema_trend = _detect_ema_trend(last_bar)
    prev_ema_trend = _detect_ema_trend(prev_bar)
    adx_strong = _is_adx_strong(last_bar, adx_threshold)
    prev_adx_strong = _is_adx_strong(prev_bar, adx_threshold)
    
    # Detect strengthening trend (ADX increasing and above threshold)
    if (ema_trend is not None and ema_trend == prev_ema_trend and 
        adx_strong and prev_adx_strong and
        pd.notna(last_bar.get("adx")) and pd.notna(prev_bar.get("adx")) and
        last_bar["adx"] > prev_bar["adx"]):
        
        trend_direction = "восходящий" if ema_trend == "up" else "нисходящий"
        events.append(Event(
            kind="trend_strength",
            message=f"💪 {symbol}: Укрепление {trend_direction} тренда (ADX↑ {prev_bar['adx']:.1f}→{last_bar['adx']:.1f}).",
            importance=TREND_IMPORTANCE_STRENGTH
        ))

    return events


def _analyze_macd_cross(
    indicators: pd.DataFrame,
    last_bar: pd.Series,
    symbol: str
) -> List[Event]:
    """
    Detect MACD line crosses with signal line.

    Args:
        indicators: DataFrame with all indicators
        last_bar: The most recent indicator bar
        symbol: Trading pair symbol

    Returns:
        List of MACD cross events
    """
    events: List[Event] = []

    if not pd.notna(last_bar.get("macd")) or not pd.notna(last_bar.get("macd_signal")):
        return events

    if len(indicators) < 2:
        return events

    prev_bar = indicators.iloc[-2]
    if not pd.notna(prev_bar.get("macd")) or not pd.notna(prev_bar.get("macd_signal")):
        return events

    # Bullish cross: MACD crosses above signal line
    if prev_bar["macd"] < prev_bar["macd_signal"] and last_bar["macd"] > last_bar["macd_signal"]:
        events.append(Event(
            kind="macd_bull",
            message=f"🟢 {symbol}: бычий перескок MACD выше сигнальной.",
            importance=SIGNAL_IMPORTANCE
        ))

    # Bearish cross: MACD crosses below signal line
    if prev_bar["macd"] > prev_bar["macd_signal"] and last_bar["macd"] < last_bar["macd_signal"]:
        events.append(Event(
            kind="macd_bear",
            message=f"🔴 {symbol}: медвежий перескок MACD ниже сигнальной.",
            importance=SIGNAL_IMPORTANCE
        ))

    return events


def _analyze_rsi(
    last_bar: pd.Series,
    symbol: str,
    rsi_overbought: float,
    rsi_oversold: float
) -> List[Event]:
    """
    Check RSI for overbought/oversold conditions.

    Args:
        last_bar: The most recent indicator bar
        symbol: Trading pair symbol
        rsi_overbought: RSI threshold for overbought condition
        rsi_oversold: RSI threshold for oversold condition

    Returns:
        List of RSI events
    """
    events: List[Event] = []

    if not pd.notna(last_bar.get("rsi")):
        return events

    rsi_value = last_bar["rsi"]

    if rsi_value >= rsi_overbought:
        events.append(Event(
            kind="rsi_overbought",
            message=f"⚠️ {symbol}: RSI={rsi_value:.1f} — перекупленность.",
            importance=SIGNAL_IMPORTANCE
        ))
    elif rsi_value <= rsi_oversold:
        events.append(Event(
            kind="rsi_oversold",
            message=f"⚠️ {symbol}: RSI={rsi_value:.1f} — перепроданность.",
            importance=SIGNAL_IMPORTANCE
        ))

    return events


def _get_pivot_emoji(level_name: PivotLevel) -> str:
    """
    Get emoji for pivot level.

    Args:
        level_name: Pivot level name (S3, S2, S1, P, R1, R2, R3)

    Returns:
        Emoji string for the level
    """
    if level_name == "P":
        return "🟨"
    elif level_name.startswith("R"):
        return "🟩"
    else:
        return "🟥"


def _get_pivot_importance(level_name: PivotLevel) -> int:
    """
    Get importance level for pivot level.

    Args:
        level_name: Pivot level name

    Returns:
        Importance value (1 or 2)
    """
    return MAJOR_PIVOT_IMPORTANCE if level_name in ("R2", "S2", "R3", "S3") else MINOR_PIVOT_IMPORTANCE


def _analyze_pivot_levels(
    daily_df: pd.DataFrame,
    last_bar: pd.Series,
    symbol: str
) -> List[Event]:
    """
    Check if price is near classical pivot levels from previous day.

    Args:
        daily_df: Daily timeframe DataFrame
        last_bar: The most recent indicator bar
        symbol: Trading pair symbol

    Returns:
        List of pivot level events
    """
    events: List[Event] = []

    daily = daily_df.dropna()
    if daily.empty or len(daily) < MIN_DAILY_BARS_FOR_PIVOTS:
        return events

    # Calculate pivots from previous day
    pivots = classical_pivots(daily.iloc[-2])
    if not pivots:
        return events

    current_price = float(last_bar["c"]) if pd.notna(last_bar.get("c")) else None
    if current_price is None:
        return events

    # Check proximity to each pivot level
    pivot_levels: List[PivotLevel] = ["S3", "S2", "S1", "P", "R1", "R2", "R3"]
    for level_name in pivot_levels:
        level_value = pivots[level_name]

        if level_value is None:
            continue

        # Check if price is within threshold of pivot level
        price_distance_pct = abs(current_price - level_value) / level_value
        if price_distance_pct <= PIVOT_PROXIMITY_THRESHOLD:
            emoji = _get_pivot_emoji(level_name)
            importance = _get_pivot_importance(level_name)

            events.append(Event(
                kind=f"pivot_touch_{level_name}",
                message=f"{emoji} {symbol}: Цена у уровня {level_name} ({level_value:.5f}).",
                importance=importance,
            ))
            break  # Only report one pivot level per analysis

    return events


def analyze_pair(
    df: pd.DataFrame,
    daily_df: pd.DataFrame,
    symbol: str,
    adx_threshold: float,
    rsi_overbought: float,
    rsi_oversold: float
) -> List[Event]:
    """
    Analyze a trading pair for signals and events.

    Args:
        df: Main timeframe DataFrame with OHLCV data
        daily_df: Daily timeframe DataFrame for pivot calculation
        symbol: Trading pair symbol
        adx_threshold: Minimum ADX value for trend confirmation
        rsi_overbought: RSI threshold for overbought condition
        rsi_oversold: RSI threshold for oversold condition

    Returns:
        List of detected events and signals
    """
    events: List[Event] = []

    if df.empty:
        return events

    # Compute technical indicators
    indicators = compute_indicators(df)
    last_bar = indicators.iloc[-1]

    # Run all analysis modules
    events.extend(_analyze_trend(last_bar, symbol, adx_threshold))
    events.extend(_analyze_trend_continuation(indicators, last_bar, symbol, adx_threshold))
    events.extend(_analyze_macd_cross(indicators, last_bar, symbol))
    events.extend(_analyze_rsi(last_bar, symbol, rsi_overbought, rsi_oversold))
    events.extend(_analyze_pivot_levels(daily_df, last_bar, symbol))

    return events
