"""Analysis module for probabilistic market analysis.

Contains:
- CorrelationAnalyzer: Pearson correlation analysis between instruments
- VolatilityAnalyzer: ATR-based volatility metrics
- ProbabilityModel: 24h directional probability forecasting
- ProbabilisticAnalyzer: Main analyzer orchestrating all components
- MarketSentimentAggregator: Cross-market sentiment analysis
"""

from .aggregation import (
    GlobalVolatilityIndicators,
    MarketSentiment,
    MarketSentimentAggregator,
    RiskIndicators,
    RiskSentiment,
    SafeHavenIndicators,
    VolatilityRegimeGlobal,
)
from .analyzer_v2 import (
    AnalysisEvent,
    AnalysisResult,
    EventType,
    ProbabilisticAnalyzer,
)
from .correlation import CorrelationAnalyzer, CorrelationResult
from .probability import (
    Direction,
    MarketContextModifier,
    ProbabilityModel,
    ProbabilityResult,
    ProbabilityWeights,
)
from .volatility import VolatilityAnalyzer, VolatilityRegime, VolatilityResult

__all__ = [
    # Aggregation
    "GlobalVolatilityIndicators",
    "MarketSentiment",
    "MarketSentimentAggregator",
    "RiskIndicators",
    "RiskSentiment",
    "SafeHavenIndicators",
    "VolatilityRegimeGlobal",
    # Correlation
    "CorrelationAnalyzer",
    "CorrelationResult",
    # Volatility
    "VolatilityAnalyzer",
    "VolatilityRegime",
    "VolatilityResult",
    # Probability
    "Direction",
    "MarketContextModifier",
    "ProbabilityModel",
    "ProbabilityResult",
    "ProbabilityWeights",
    # Analyzer
    "AnalysisEvent",
    "AnalysisResult",
    "EventType",
    "ProbabilisticAnalyzer",
]
