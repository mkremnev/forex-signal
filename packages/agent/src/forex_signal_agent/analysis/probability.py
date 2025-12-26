"""Probability model for directional forecasting.

Uses multiple market factors to compute probabilities for
upward, downward, and consolidation market directions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Direction(str, Enum):
    """Market direction classification."""

    UPWARD = "upward"
    DOWNWARD = "downward"
    CONSOLIDATION = "consolidation"


@dataclass
class ProbabilityWeights:
    """Weights for probability model factors.

    Attributes:
        roc: Weight for Rate of Change factor
        volatility: Weight for volatility (ATR%) factor
        volume: Weight for volume factor
        correlation: Weight for correlation factor
    """

    roc: float = 0.25
    volatility: float = 0.25
    volume: float = 0.25
    correlation: float = 0.25

    def __post_init__(self) -> None:
        """Validate weights sum to 1.0."""
        total = self.roc + self.volatility + self.volume + self.correlation
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total}, normalizing to 1.0")
            self.roc /= total
            self.volatility /= total
            self.volume /= total
            self.correlation /= total


@dataclass
class ProbabilityResult:
    """Result of probability analysis.

    Attributes:
        symbol: Instrument symbol
        direction: Predicted direction
        probabilities: Dict mapping direction to probability
        confidence: Confidence in the prediction (margin between top 1 and 2)
        is_actionable: Whether the signal is actionable
        factors: Individual factor scores used
    """

    symbol: str
    direction: Direction
    probabilities: dict[Direction, float]
    confidence: float
    is_actionable: bool
    factors: dict[str, float] = field(default_factory=dict)

    @property
    def upward_probability(self) -> float:
        """Get probability of upward movement."""
        return self.probabilities.get(Direction.UPWARD, 0.0)

    @property
    def downward_probability(self) -> float:
        """Get probability of downward movement."""
        return self.probabilities.get(Direction.DOWNWARD, 0.0)

    @property
    def consolidation_probability(self) -> float:
        """Get probability of consolidation."""
        return self.probabilities.get(Direction.CONSOLIDATION, 0.0)


class ProbabilityModelProtocol(Protocol):
    """Protocol for probability models."""

    def predict(
        self,
        df: pd.DataFrame,
        symbol: str,
        avg_correlation: float | None = None,
    ) -> ProbabilityResult | None:
        """Predict direction probabilities.

        Args:
            df: OHLCV DataFrame
            symbol: Instrument symbol
            avg_correlation: Average correlation with other instruments

        Returns:
            ProbabilityResult or None if prediction fails
        """
        ...


class ProbabilityModel:
    """Probability model for 24h directional forecasting.

    Uses multiple factors to compute probabilities for each direction:
    - ROC (Rate of Change) over 24h
    - Volatility (ATR%)
    - Volume compared to 24h MA
    - Average correlation with other instruments

    Probabilities are normalized using softmax.

    Example:
        model = ProbabilityModel()
        result = model.predict(df_eurusd, "EUR/USD")
        print(f"Direction: {result.direction}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    # Thresholds for actionable signals
    CONFIDENCE_THRESHOLD = 0.4
    HIGH_CONFIDENCE_THRESHOLD = 0.6

    def __init__(
        self,
        weights: ProbabilityWeights | None = None,
        lookback_periods: int = 24,
    ):
        """Initialize probability model.

        Args:
            weights: Factor weights (default: equal weights 0.25)
            lookback_periods: Periods for ROC calculation
        """
        self._weights = weights or ProbabilityWeights()
        self._lookback = lookback_periods

    @property
    def weights(self) -> ProbabilityWeights:
        """Get factor weights."""
        return self._weights

    def predict(
        self,
        df: pd.DataFrame,
        symbol: str,
        avg_correlation: float | None = None,
    ) -> ProbabilityResult | None:
        """Predict direction probabilities.

        Args:
            df: OHLCV DataFrame with close, high, low, volume columns
            symbol: Instrument symbol
            avg_correlation: Average correlation with other instruments

        Returns:
            ProbabilityResult or None if prediction fails
        """
        if df.empty or len(df) < self._lookback + 1:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Calculate individual factors
        factors = self._calculate_factors(df, avg_correlation)

        if factors is None:
            logger.warning(f"Failed to calculate factors for {symbol}")
            return None

        # Calculate raw scores for each direction
        raw_scores = self._calculate_raw_scores(factors)

        # Apply softmax normalization
        probabilities = self._softmax(raw_scores)

        # Determine direction via argmax
        direction = self._classify_direction(probabilities)

        # Calculate confidence (margin between top-1 and top-2)
        confidence = self._calculate_confidence(probabilities)

        # Determine if actionable
        is_actionable = self._is_actionable(direction, confidence)

        return ProbabilityResult(
            symbol=symbol,
            direction=direction,
            probabilities=probabilities,
            confidence=confidence,
            is_actionable=is_actionable,
            factors=factors,
        )

    def _calculate_factors(
        self,
        df: pd.DataFrame,
        avg_correlation: float | None,
    ) -> dict[str, float] | None:
        """Calculate all model factors.

        Args:
            df: OHLCV DataFrame
            avg_correlation: Average correlation

        Returns:
            Dictionary of factor values or None if calculation fails
        """
        try:
            factors: dict[str, float] = {}

            # ROC (Rate of Change) over lookback period
            roc = self._calculate_roc(df)
            if roc is not None:
                factors["roc"] = roc
            else:
                factors["roc"] = 0.0

            # Volatility (ATR%)
            atr_pct = self._calculate_atr_percent(df)
            if atr_pct is not None:
                factors["volatility"] = atr_pct
            else:
                factors["volatility"] = 1.0  # Neutral default

            # Volume vs MA24
            volume_ratio = self._calculate_volume_ratio(df)
            if volume_ratio is not None:
                factors["volume"] = volume_ratio
            else:
                factors["volume"] = 1.0  # Neutral default

            # Correlation (use average or neutral)
            factors["correlation"] = avg_correlation if avg_correlation else 0.5

            return factors

        except Exception as e:
            logger.error(f"Error calculating factors: {e}")
            return None

    def _calculate_roc(self, df: pd.DataFrame) -> float | None:
        """Calculate Rate of Change over lookback period.

        Args:
            df: OHLCV DataFrame

        Returns:
            ROC as percentage or None
        """
        if len(df) < self._lookback + 1:
            return None

        close = df["close"]
        current = close.iloc[-1]
        past = close.iloc[-self._lookback - 1]

        if past <= 0:
            return None

        return ((current - past) / past) * 100

    def _calculate_atr_percent(self, df: pd.DataFrame) -> float | None:
        """Calculate ATR as percentage of price.

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR% or None
        """
        atr_period = 14

        if len(df) < atr_period + 1:
            return None

        high = df["high"]
        low = df["low"]
        close = df["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=atr_period).mean().iloc[-1]

        current_price = close.iloc[-1]

        if current_price <= 0 or pd.isna(atr):
            return None

        return (atr / current_price) * 100

    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float | None:
        """Calculate volume ratio vs 24-period MA.

        Args:
            df: OHLCV DataFrame

        Returns:
            Volume ratio or None
        """
        if "volume" not in df.columns:
            return None

        volume = df["volume"]

        if len(volume) < self._lookback:
            return None

        current_vol = volume.iloc[-1]
        ma_vol = volume.iloc[-self._lookback:].mean()

        if ma_vol <= 0 or pd.isna(ma_vol):
            return None

        return current_vol / ma_vol

    def _calculate_raw_scores(
        self,
        factors: dict[str, float],
    ) -> dict[Direction, float]:
        """Calculate raw scores for each direction.

        Args:
            factors: Dictionary of factor values

        Returns:
            Raw scores for each direction
        """
        roc = factors.get("roc", 0.0)
        volatility = factors.get("volatility", 1.0)
        volume = factors.get("volume", 1.0)
        correlation = factors.get("correlation", 0.5)

        w = self._weights

        # Higher ROC -> higher upward score
        # Lower ROC (negative) -> higher downward score
        roc_up = max(roc, 0) / 10  # Normalize to reasonable range
        roc_down = max(-roc, 0) / 10

        # Low volatility -> higher consolidation score
        volatility_consol = max(0, 2 - volatility) / 2

        # High volume with direction -> supports directional move
        volume_factor = min(volume, 2) / 2

        # Correlation effect (high correlation reduces confidence)
        corr_penalty = correlation * 0.5

        # Calculate directional scores
        upward_score = (
            w.roc * roc_up
            + w.volatility * (volatility / 3)
            + w.volume * volume_factor * (1 if roc > 0 else 0.5)
            - w.correlation * corr_penalty
        )

        downward_score = (
            w.roc * roc_down
            + w.volatility * (volatility / 3)
            + w.volume * volume_factor * (1 if roc < 0 else 0.5)
            - w.correlation * corr_penalty
        )

        consolidation_score = (
            w.roc * (1 - abs(roc) / 10)
            + w.volatility * volatility_consol
            + w.volume * (1 - volume_factor)
            + w.correlation * corr_penalty
        )

        return {
            Direction.UPWARD: upward_score,
            Direction.DOWNWARD: downward_score,
            Direction.CONSOLIDATION: consolidation_score,
        }

    def _softmax(
        self,
        scores: dict[Direction, float],
    ) -> dict[Direction, float]:
        """Apply softmax normalization to scores.

        Args:
            scores: Raw scores for each direction

        Returns:
            Probabilities (sum to 1.0)
        """
        values = np.array(list(scores.values()))

        # Numerical stability: subtract max
        values = values - np.max(values)

        exp_values = np.exp(values)
        softmax_values = exp_values / np.sum(exp_values)

        directions = list(scores.keys())
        return {d: float(p) for d, p in zip(directions, softmax_values)}

    def _classify_direction(
        self,
        probabilities: dict[Direction, float],
    ) -> Direction:
        """Classify direction via argmax.

        Args:
            probabilities: Probabilities for each direction

        Returns:
            Direction with highest probability
        """
        return max(probabilities, key=lambda d: probabilities[d])

    def _calculate_confidence(
        self,
        probabilities: dict[Direction, float],
    ) -> float:
        """Calculate confidence as margin between top-1 and top-2.

        Args:
            probabilities: Probabilities for each direction

        Returns:
            Confidence value (0 to 1)
        """
        sorted_probs = sorted(probabilities.values(), reverse=True)

        if len(sorted_probs) < 2:
            return sorted_probs[0] if sorted_probs else 0.0

        # Confidence is the margin between top-1 and top-2
        return sorted_probs[0] - sorted_probs[1]

    def _is_actionable(self, direction: Direction, confidence: float) -> bool:
        """Determine if the signal is actionable.

        Actionable = confidence >= 0.6 AND direction != consolidation

        Args:
            direction: Predicted direction
            confidence: Confidence value

        Returns:
            True if signal is actionable
        """
        return (
            confidence >= self.HIGH_CONFIDENCE_THRESHOLD
            and direction != Direction.CONSOLIDATION
        )
