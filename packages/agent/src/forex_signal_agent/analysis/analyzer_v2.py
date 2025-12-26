"""Probabilistic analyzer for market analysis.

Orchestrates correlation, volatility, and probability analysis
to generate actionable trading signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

import pandas as pd

from .correlation import CorrelationAnalyzer
from .probability import Direction, ProbabilityModel, ProbabilityResult, ProbabilityWeights
from .volatility import VolatilityAnalyzer, VolatilityRegime, VolatilityResult

if TYPE_CHECKING:
    from .aggregation import MarketSentiment

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of analysis events."""

    PROBABILITY_SIGNAL = "probability_signal"
    VOLATILITY_ALERT = "volatility_alert"


@dataclass
class AnalysisEvent:
    """Event emitted by the analyzer.

    Attributes:
        event_type: Type of event
        symbol: Instrument symbol
        timeframe: Analysis timeframe
        timestamp: When the event was generated
        importance: Event importance (1=normal, 2=high)
        data: Event-specific data
    """

    event_type: EventType
    symbol: str
    timeframe: str
    timestamp: datetime
    importance: int
    data: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete analysis result for a symbol.

    Attributes:
        symbol: Instrument symbol
        timeframe: Analysis timeframe
        probability: Probability analysis result
        volatility: Volatility analysis result
        events: List of generated events
        timestamp: Analysis timestamp
        market_sentiment: Aggregated market sentiment context (if available)
    """

    symbol: str
    timeframe: str
    probability: ProbabilityResult | None
    volatility: VolatilityResult | None
    events: list[AnalysisEvent]
    timestamp: datetime
    market_sentiment: Optional["MarketSentiment"] = None


class ProbabilisticAnalyzer:
    """Main analyzer orchestrating probabilistic market analysis.

    Combines correlation, volatility, and probability analysis
    to generate trading signals and alerts.

    Example:
        analyzer = ProbabilisticAnalyzer()

        # Update correlations with all market data
        await analyzer.update_correlations(all_data)

        # Analyze a single symbol
        result = analyzer.analyze(df_eurusd, "EUR/USD", "1h")

        # Process events
        for event in result.events:
            if event.event_type == EventType.PROBABILITY_SIGNAL:
                print(f"Signal: {event.data['direction']}")
    """

    # Thresholds for events
    CONFIDENCE_THRESHOLD = 0.4
    HIGH_CONFIDENCE_THRESHOLD = 0.6

    def __init__(
        self,
        correlation_lookback_hours: int = 24,
        correlation_min_points: int = 20,
        high_correlation_threshold: float = 0.7,
        atr_period: int = 14,
        consolidation_threshold: float = 0.01,
        probability_weights: ProbabilityWeights | None = None,
    ):
        """Initialize probabilistic analyzer.

        Args:
            correlation_lookback_hours: Lookback for correlation analysis
            correlation_min_points: Min data points for correlation
            high_correlation_threshold: Threshold for high correlation
            atr_period: ATR calculation period
            consolidation_threshold: ATR% threshold for consolidation
            probability_weights: Weights for probability model
        """
        self._correlation = CorrelationAnalyzer(
            lookback_hours=correlation_lookback_hours,
            min_data_points=correlation_min_points,
            high_correlation_threshold=high_correlation_threshold,
        )
        self._volatility = VolatilityAnalyzer(
            atr_period=atr_period,
            consolidation_threshold=consolidation_threshold,
        )
        self._probability = ProbabilityModel(
            weights=probability_weights,
            lookback_periods=24,
        )

    @property
    def correlation_analyzer(self) -> CorrelationAnalyzer:
        """Get correlation analyzer instance."""
        return self._correlation

    @property
    def volatility_analyzer(self) -> VolatilityAnalyzer:
        """Get volatility analyzer instance."""
        return self._volatility

    @property
    def probability_model(self) -> ProbabilityModel:
        """Get probability model instance."""
        return self._probability

    def update_correlations(
        self,
        all_data: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Update correlation matrix with all market data.

        Should be called before analyze() to have correlation context.

        Args:
            all_data: Dictionary mapping symbol to OHLCV DataFrame

        Returns:
            Correlation matrix DataFrame
        """
        return self._correlation.build_correlation_matrix(all_data)

    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        market_sentiment: Optional["MarketSentiment"] = None,
    ) -> AnalysisResult:
        """Analyze a single instrument.

        Args:
            df: OHLCV DataFrame
            symbol: Instrument symbol
            timeframe: Analysis timeframe (e.g., "1h", "4h")
            market_sentiment: Aggregated market sentiment for context

        Returns:
            AnalysisResult with probability, volatility, and events
        """
        now = datetime.now(timezone.utc)
        events: list[AnalysisEvent] = []

        # Volatility analysis
        volatility_result = self._volatility.analyze(df, symbol)

        # Probability analysis (with correlation and market sentiment context)
        avg_correlation = self._correlation.get_average_correlation(symbol)
        probability_result = self._probability.predict(
            df, symbol, avg_correlation, market_sentiment
        )

        # Generate events
        if probability_result:
            prob_events = self._generate_probability_events(
                probability_result, timeframe, now
            )
            events.extend(prob_events)

        if volatility_result:
            vol_events = self._generate_volatility_events(
                volatility_result, timeframe, now
            )
            events.extend(vol_events)

        return AnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            probability=probability_result,
            volatility=volatility_result,
            events=events,
            timestamp=now,
            market_sentiment=market_sentiment,
        )

    def analyze_batch(
        self,
        data: dict[str, pd.DataFrame],
        timeframe: str,
    ) -> dict[str, AnalysisResult]:
        """Analyze multiple instruments.

        Args:
            data: Dictionary mapping symbol to OHLCV DataFrame
            timeframe: Analysis timeframe

        Returns:
            Dictionary mapping symbol to AnalysisResult
        """
        results: dict[str, AnalysisResult] = {}

        for symbol, df in data.items():
            result = self.analyze(df, symbol, timeframe)
            results[symbol] = result

        return results

    def _generate_probability_events(
        self,
        result: ProbabilityResult,
        timeframe: str,
        timestamp: datetime,
    ) -> list[AnalysisEvent]:
        """Generate probability signal events.

        Emits probability_signal when confidence >= 0.4
        Sets importance=2 when confidence >= 0.6

        Args:
            result: Probability analysis result
            timeframe: Analysis timeframe
            timestamp: Event timestamp

        Returns:
            List of probability events
        """
        events: list[AnalysisEvent] = []

        # Only emit if above confidence threshold
        if result.confidence < self.CONFIDENCE_THRESHOLD:
            return events

        # Determine importance
        importance = (
            2 if result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD else 1
        )

        # Build event data
        event_data = {
            "direction": result.direction.value,
            "probabilities": {
                d.value: round(p, 4)
                for d, p in result.probabilities.items()
            },
            "confidence": round(result.confidence, 4),
            "is_actionable": result.is_actionable,
            "factors": result.factors,
        }

        # Add market context if available
        if result.market_context is not None:
            event_data["market_sentiment"] = result.market_context.sentiment
            event_data["market_modifier"] = result.market_context.modifier
            event_data["market_reasoning"] = result.market_context.reasoning

        event = AnalysisEvent(
            event_type=EventType.PROBABILITY_SIGNAL,
            symbol=result.symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            importance=importance,
            data=event_data,
        )

        events.append(event)
        logger.debug(
            f"Probability signal for {result.symbol}: "
            f"{result.direction.value} (conf={result.confidence:.2%})"
        )

        return events

    def _generate_volatility_events(
        self,
        result: VolatilityResult,
        timeframe: str,
        timestamp: datetime,
    ) -> list[AnalysisEvent]:
        """Generate volatility alert events.

        Emits volatility_alert when regime is HIGH or EXTREME.

        Args:
            result: Volatility analysis result
            timeframe: Analysis timeframe
            timestamp: Event timestamp

        Returns:
            List of volatility events
        """
        events: list[AnalysisEvent] = []

        # Only emit for high/extreme volatility
        if result.regime not in (VolatilityRegime.HIGH, VolatilityRegime.EXTREME):
            return events

        # Higher importance for extreme volatility
        importance = 2 if result.regime == VolatilityRegime.EXTREME else 1

        event = AnalysisEvent(
            event_type=EventType.VOLATILITY_ALERT,
            symbol=result.symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            importance=importance,
            data={
                "regime": result.regime.value,
                "atr": round(result.atr, 6),
                "atr_percent": round(result.atr_percent, 4),
                "current_price": round(result.current_price, 6),
                "is_consolidation": result.is_consolidation,
            },
        )

        events.append(event)
        logger.debug(
            f"Volatility alert for {result.symbol}: "
            f"{result.regime.value} (ATR%={result.atr_percent:.2f}%)"
        )

        return events

    def get_actionable_signals(
        self,
        results: dict[str, AnalysisResult],
    ) -> list[AnalysisEvent]:
        """Filter for actionable probability signals.

        Args:
            results: Dictionary of analysis results

        Returns:
            List of actionable probability signal events
        """
        actionable: list[AnalysisEvent] = []

        for result in results.values():
            if result.probability and result.probability.is_actionable:
                for event in result.events:
                    if event.event_type == EventType.PROBABILITY_SIGNAL:
                        actionable.append(event)

        return actionable

    def get_high_importance_events(
        self,
        results: dict[str, AnalysisResult],
    ) -> list[AnalysisEvent]:
        """Filter for high importance events (importance=2).

        Args:
            results: Dictionary of analysis results

        Returns:
            List of high importance events
        """
        high_importance: list[AnalysisEvent] = []

        for result in results.values():
            for event in result.events:
                if event.importance >= 2:
                    high_importance.append(event)

        return high_importance
