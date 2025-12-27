"""Probability model for directional forecasting.

Uses multiple market factors to compute probabilities for
upward, downward, and consolidation market directions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional, Protocol, Tuple

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .aggregation import MarketSentiment

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
class MarketContextModifier:
    """Market context modifier for probability adjustments.

    Attributes:
        sentiment: Market sentiment (risk_on, risk_off, neutral)
        modifier: Probability modifier (0.8 - 1.2)
        adjusted_confidence: Confidence after market context adjustment
        reasoning: Explanation of the modification
    """

    sentiment: str
    modifier: float
    adjusted_confidence: float
    reasoning: str


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
    market_context: Optional[MarketContextModifier] = None

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
        market_sentiment: Optional["MarketSentiment"] = None,
    ) -> ProbabilityResult | None:
        """Predict direction probabilities.

        Args:
            df: OHLCV DataFrame
            symbol: Instrument symbol
            avg_correlation: Average correlation with other instruments
            market_sentiment: Aggregated market sentiment for context

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

    def __init__(
        self,
        weights: ProbabilityWeights | None = None,
        lookback_periods: int = 24,
        confidence_threshold: float = 0.4,
        high_confidence_threshold: float = 0.6,
        atr_period: int = 14,
    ):
        """Initialize probability model.

        Args:
            weights: Factor weights (default: equal weights 0.25)
            lookback_periods: Periods for ROC calculation
            confidence_threshold: Minimum confidence for signal emission
            high_confidence_threshold: Confidence threshold for actionable signals
            atr_period: Period for ATR calculation
        """
        self._weights = weights or ProbabilityWeights()
        self._lookback = lookback_periods
        self._confidence_threshold = confidence_threshold
        self._high_confidence_threshold = high_confidence_threshold
        self._atr_period = atr_period

    @property
    def weights(self) -> ProbabilityWeights:
        """Get factor weights."""
        return self._weights

    def predict(
        self,
        df: pd.DataFrame,
        symbol: str,
        avg_correlation: float | None = None,
        market_sentiment: Optional["MarketSentiment"] = None,
    ) -> ProbabilityResult | None:
        """Predict direction probabilities.

        Args:
            df: OHLCV DataFrame with close, high, low, volume columns
            symbol: Instrument symbol
            avg_correlation: Average correlation with other instruments
            market_sentiment: Aggregated market sentiment for context

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

        # Apply market context if available
        market_context: Optional[MarketContextModifier] = None
        if market_sentiment is not None:
            probabilities, market_context = self._apply_market_context(
                probabilities, symbol, market_sentiment
            )
            # Recalculate direction and confidence after context adjustment
            direction = self._classify_direction(probabilities)
            confidence = self._calculate_confidence(probabilities)
            is_actionable = self._is_actionable(direction, confidence)

        return ProbabilityResult(
            symbol=symbol,
            direction=direction,
            probabilities=probabilities,
            confidence=confidence,
            is_actionable=is_actionable,
            factors=factors,
            market_context=market_context,
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
        if len(df) < self._atr_period + 1:
            return None

        high = df["high"]
        low = df["low"]
        close = df["close"]

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=self._atr_period).mean().iloc[-1]

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

        Actionable = confidence >= high_confidence_threshold AND direction != consolidation

        Args:
            direction: Predicted direction
            confidence: Confidence value

        Returns:
            True if signal is actionable
        """
        return (
            confidence >= self._high_confidence_threshold
            and direction != Direction.CONSOLIDATION
        )

    def _apply_market_context(
        self,
        probabilities: Dict[Direction, float],
        symbol: str,
        sentiment: "MarketSentiment",
    ) -> Tuple[Dict[Direction, float], MarketContextModifier]:
        """Apply market sentiment to adjust probabilities.

        Rules:
        - Risk-on + risk assets (EUR, GBP, BTC, ETH) -> upward +10%
        - Risk-off + risk assets -> downward +10%
        - Risk-off + safe havens (JPY, CHF, Gold) -> upward +10%
        - Crisis volatility -> consolidation +15%

        Args:
            probabilities: Current direction probabilities
            symbol: Instrument symbol
            sentiment: Aggregated market sentiment

        Returns:
            Tuple of (adjusted_probabilities, MarketContextModifier)
        """
        from .aggregation import RiskSentiment, VolatilityRegimeGlobal

        # Identify asset type
        is_risk_asset = any(x in symbol.upper() for x in ["EUR", "GBP", "AUD", "NZD", "BTC", "ETH", "SOL"])
        is_safe_haven = any(x in symbol.upper() for x in ["JPY", "CHF", "GC=F", "GOLD"])

        modifier = 1.0
        reasoning = "neutral market"

        # Apply sentiment-based modifications
        if sentiment.risk_sentiment == RiskSentiment.RISK_ON:
            if is_risk_asset:
                modifier = 1.1
                reasoning = "risk-on supports this risk asset"
            elif is_safe_haven:
                modifier = 0.95
                reasoning = "risk-on reduces safe haven demand"
        elif sentiment.risk_sentiment == RiskSentiment.RISK_OFF:
            if is_risk_asset:
                modifier = 0.9
                reasoning = "risk-off pressures this risk asset"
            elif is_safe_haven:
                modifier = 1.1
                reasoning = "risk-off supports safe haven flow"

        # Create a copy of probabilities
        adjusted = dict(probabilities)

        # Apply volatility adjustment for crisis regime
        if sentiment.volatility_indicators.regime == VolatilityRegimeGlobal.CRISIS:
            # Boost consolidation in crisis
            adjusted[Direction.CONSOLIDATION] = adjusted.get(Direction.CONSOLIDATION, 0.0) + 0.15
            reasoning += " | high volatility favors consolidation"

        # Adjust directional probabilities based on modifier
        if modifier > 1.0:
            # Boost upward probability
            adjusted[Direction.UPWARD] = adjusted.get(Direction.UPWARD, 0.0) * modifier
        elif modifier < 1.0:
            # Boost downward probability (inverse of modifier)
            adjusted[Direction.DOWNWARD] = adjusted.get(Direction.DOWNWARD, 0.0) * (2 - modifier)

        # Renormalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {d: p / total for d, p in adjusted.items()}

        # Calculate adjusted confidence
        sorted_probs = sorted(adjusted.values(), reverse=True)
        adjusted_confidence = (sorted_probs[0] - sorted_probs[1]) * sentiment.confidence if len(sorted_probs) >= 2 else 0.0

        logger.debug(
            f"Market context for {symbol}: {sentiment.risk_sentiment.value}, "
            f"modifier={modifier:.2f}, reasoning={reasoning}"
        )

        return adjusted, MarketContextModifier(
            sentiment=sentiment.risk_sentiment.value,
            modifier=modifier,
            adjusted_confidence=adjusted_confidence,
            reasoning=reasoning,
        )
