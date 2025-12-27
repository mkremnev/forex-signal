"""Volatility analysis for market instruments.

Uses ATR (Average True Range) to measure market volatility
and classify instruments into volatility regimes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityRegime(str, Enum):
    """Market volatility regime classification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class VolatilityResult:
    """Result of volatility analysis.

    Attributes:
        symbol: Instrument symbol
        atr: Absolute ATR value
        atr_percent: ATR as percentage of price
        regime: Volatility regime classification
        is_consolidation: Whether market is in consolidation
        current_price: Latest closing price used
    """

    symbol: str
    atr: float
    atr_percent: float
    regime: VolatilityRegime
    is_consolidation: bool
    current_price: float


class VolatilityAnalyzer:
    """Analyzes volatility using ATR-based metrics.

    Uses Average True Range (ATR) to measure volatility and
    classify markets into different volatility regimes.

    Example:
        analyzer = VolatilityAnalyzer(atr_period=14)

        result = analyzer.analyze(df_eurusd, "EUR/USD")
        print(f"ATR%: {result.atr_percent:.2f}%")
        print(f"Regime: {result.regime}")
        print(f"Consolidation: {result.is_consolidation}")
    """

    # Default regime thresholds (ATR% values)
    DEFAULT_REGIME_THRESHOLDS = {
        "low": 0.5,      # < 0.5% is low volatility
        "normal": 1.0,   # 0.5% - 1.0% is normal
        "high": 2.0,     # 1.0% - 2.0% is high
        # > 2.0% is extreme
    }

    def __init__(
        self,
        atr_period: int = 14,
        consolidation_threshold: float = 0.01,  # 1%
        regime_thresholds: dict | None = None,
    ):
        """Initialize volatility analyzer.

        Args:
            atr_period: Period for ATR calculation
            consolidation_threshold: ATR% threshold for consolidation (default 1%)
            regime_thresholds: Dict with 'low', 'normal', 'high' ATR% thresholds
        """
        self._atr_period = atr_period
        self._consolidation_threshold = consolidation_threshold
        self._regime_thresholds = regime_thresholds or self.DEFAULT_REGIME_THRESHOLDS

    @property
    def atr_period(self) -> int:
        """Get ATR calculation period."""
        return self._atr_period

    @property
    def consolidation_threshold(self) -> float:
        """Get consolidation threshold (as decimal, e.g., 0.01 = 1%)."""
        return self._consolidation_threshold

    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str = "",
    ) -> VolatilityResult | None:
        """Analyze volatility for an instrument.

        Args:
            df: OHLCV DataFrame with high, low, close columns
            symbol: Instrument symbol (for result labeling)

        Returns:
            VolatilityResult or None if insufficient data
        """
        if df.empty:
            logger.warning(f"Empty DataFrame for {symbol}")
            return None

        required_cols = ["high", "low", "close"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.warning(f"Missing columns for {symbol}: {missing}")
            return None

        if len(df) < self._atr_period + 1:
            logger.warning(
                f"Insufficient data for {symbol}: "
                f"need {self._atr_period + 1}, got {len(df)}"
            )
            return None

        # Calculate ATR
        atr = self.calculate_atr(df)

        if atr is None or np.isnan(atr):
            logger.warning(f"Failed to calculate ATR for {symbol}")
            return None

        # Get current price
        current_price = float(df["close"].iloc[-1])

        if current_price <= 0:
            logger.warning(f"Invalid price for {symbol}: {current_price}")
            return None

        # Calculate ATR%
        atr_percent = (atr / current_price) * 100

        # Classify regime
        regime = self._classify_regime(atr_percent)

        # Check consolidation
        is_consolidation = self.is_consolidation(atr_percent)

        return VolatilityResult(
            symbol=symbol,
            atr=atr,
            atr_percent=atr_percent,
            regime=regime,
            is_consolidation=is_consolidation,
            current_price=current_price,
        )

    def calculate_atr(self, df: pd.DataFrame) -> float | None:
        """Calculate Average True Range.

        ATR is the average of True Range over the specified period.
        True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))

        Args:
            df: OHLCV DataFrame with high, low, close columns

        Returns:
            ATR value or None if calculation fails
        """
        if len(df) < self._atr_period + 1:
            return None

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Calculate True Range components
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate ATR (simple moving average of TR)
        atr_series = true_range.rolling(window=self._atr_period).mean()

        # Return the latest ATR value
        latest_atr = atr_series.iloc[-1]

        if pd.isna(latest_atr):
            return None

        return float(latest_atr)

    def calculate_atr_percent(
        self,
        df: pd.DataFrame,
    ) -> float | None:
        """Calculate ATR as percentage of current price.

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR percentage or None if calculation fails
        """
        atr = self.calculate_atr(df)

        if atr is None:
            return None

        current_price = float(df["close"].iloc[-1])

        if current_price <= 0:
            return None

        return (atr / current_price) * 100

    def is_consolidation(
        self,
        atr_percent: float,
    ) -> bool:
        """Check if market is in consolidation.

        A market is considered to be in consolidation when
        ATR% is below the consolidation threshold.

        Args:
            atr_percent: ATR as percentage (e.g., 0.5 for 0.5%)

        Returns:
            True if in consolidation (low volatility)
        """
        # Convert percentage to decimal for comparison
        # e.g., 0.5% -> 0.005, threshold 1% -> 0.01
        return (atr_percent / 100) < self._consolidation_threshold

    def _classify_regime(self, atr_percent: float) -> VolatilityRegime:
        """Classify volatility regime based on ATR%.

        Args:
            atr_percent: ATR as percentage

        Returns:
            VolatilityRegime classification
        """
        if atr_percent < self._regime_thresholds["low"]:
            return VolatilityRegime.LOW
        elif atr_percent < self._regime_thresholds["normal"]:
            return VolatilityRegime.NORMAL
        elif atr_percent < self._regime_thresholds["high"]:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    def get_volatility_score(self, atr_percent: float) -> float:
        """Get normalized volatility score (0-1).

        Normalizes ATR% to a 0-1 scale where:
        - 0 = very low volatility
        - 0.5 = normal volatility
        - 1 = extreme volatility

        Args:
            atr_percent: ATR as percentage

        Returns:
            Normalized volatility score between 0 and 1
        """
        # Cap at 3% ATR as maximum
        max_atr_percent = 3.0

        # Normalize to 0-1 scale
        score = min(atr_percent / max_atr_percent, 1.0)

        return score
