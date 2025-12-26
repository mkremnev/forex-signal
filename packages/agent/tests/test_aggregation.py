"""Unit tests for Market Sentiment Aggregation."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from forex_signal_agent.analysis.aggregation import (
    GlobalVolatilityIndicators,
    MarketSentiment,
    MarketSentimentAggregator,
    RiskIndicators,
    RiskSentiment,
    SafeHavenIndicators,
    VolatilityRegimeGlobal,
)


def create_ohlcv_df(
    close_prices: list[float],
    high_factor: float = 1.01,
    low_factor: float = 0.99,
) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame for testing.

    Args:
        close_prices: List of close prices
        high_factor: Multiplier for high prices
        low_factor: Multiplier for low prices

    Returns:
        DataFrame with OHLCV data
    """
    n = len(close_prices)
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=n, freq="1h")

    return pd.DataFrame(
        {
            "open": [p * 0.995 for p in close_prices],
            "high": [p * high_factor for p in close_prices],
            "low": [p * low_factor for p in close_prices],
            "close": close_prices,
            "volume": [1000.0] * n,
        },
        index=dates,
    )


def create_uptrend_df(roc_pct: float = 5.0, periods: int = 30) -> pd.DataFrame:
    """Create DataFrame with uptrend (positive ROC).

    Args:
        roc_pct: Target ROC percentage
        periods: Number of periods

    Returns:
        DataFrame with uptrending prices
    """
    start_price = 100.0
    end_price = start_price * (1 + roc_pct / 100)
    prices = np.linspace(start_price, end_price, periods).tolist()
    return create_ohlcv_df(prices)


def create_downtrend_df(roc_pct: float = -5.0, periods: int = 30) -> pd.DataFrame:
    """Create DataFrame with downtrend (negative ROC).

    Args:
        roc_pct: Target ROC percentage (should be negative)
        periods: Number of periods

    Returns:
        DataFrame with downtrending prices
    """
    start_price = 100.0
    end_price = start_price * (1 + roc_pct / 100)
    prices = np.linspace(start_price, end_price, periods).tolist()
    return create_ohlcv_df(prices)


def create_flat_df(periods: int = 30) -> pd.DataFrame:
    """Create DataFrame with flat prices (minimal ROC).

    Args:
        periods: Number of periods

    Returns:
        DataFrame with flat prices
    """
    prices = [100.0] * periods
    return create_ohlcv_df(prices)


class TestMarketSentimentAggregator:
    """Tests for MarketSentimentAggregator class."""

    def test_init_default_assets(self):
        """Test initialization with default assets."""
        aggregator = MarketSentimentAggregator()

        assert aggregator._roc_lookback == 24
        assert aggregator._atr_period == 14
        assert "BTCUSDT" in aggregator._risk_assets
        assert "GC=F" in aggregator._safe_haven_assets

    def test_init_custom_assets(self):
        """Test initialization with custom assets."""
        risk_assets = ["BTCUSDT", "ETHUSDT"]
        safe_haven = ["GC=F"]

        aggregator = MarketSentimentAggregator(
            roc_lookback=12,
            atr_period=20,
            risk_assets=risk_assets,
            safe_haven_assets=safe_haven,
        )

        assert aggregator._roc_lookback == 12
        assert aggregator._atr_period == 20
        assert aggregator._risk_assets == risk_assets
        assert aggregator._safe_haven_assets == safe_haven

    def test_aggregate_risk_on(self):
        """BTC +5%, ETH +3% should produce RISK_ON sentiment."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_uptrend_df(roc_pct=5.0),
            "ETHUSDT": create_uptrend_df(roc_pct=3.0),
            "GC=F": create_flat_df(),
        }

        sentiment = aggregator.aggregate(all_data)

        assert sentiment.risk_sentiment == RiskSentiment.RISK_ON
        assert sentiment.confidence > 0.5
        assert sentiment.risk_indicators.btc_roc_24h > 0
        assert "risk" in sentiment.dominant_factor.lower() or "crypto" in sentiment.dominant_factor.lower()

    def test_aggregate_risk_off(self):
        """BTC -5%, Gold +2% should produce RISK_OFF sentiment."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_downtrend_df(roc_pct=-5.0),
            "ETHUSDT": create_downtrend_df(roc_pct=-3.0),
            "GC=F": create_uptrend_df(roc_pct=2.0),
        }

        sentiment = aggregator.aggregate(all_data)

        assert sentiment.risk_sentiment == RiskSentiment.RISK_OFF
        assert sentiment.safe_haven_indicators.gold_roc_24h > 0
        assert sentiment.risk_indicators.risk_score < 0

    def test_aggregate_neutral(self):
        """Flat markets should produce NEUTRAL sentiment."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_flat_df(),
            "ETHUSDT": create_flat_df(),
            "GC=F": create_flat_df(),
        }

        sentiment = aggregator.aggregate(all_data)

        assert sentiment.risk_sentiment == RiskSentiment.NEUTRAL
        assert abs(sentiment.risk_indicators.risk_score) < 0.3
        assert abs(sentiment.safe_haven_indicators.safe_haven_score) < 0.3

    def test_aggregate_empty_data(self):
        """Empty data should produce NEUTRAL with default indicators."""
        aggregator = MarketSentimentAggregator()

        sentiment = aggregator.aggregate({})

        assert sentiment.risk_sentiment == RiskSentiment.NEUTRAL
        assert sentiment.risk_indicators.btc_roc_24h == 0.0

    def test_aggregate_partial_data(self):
        """Should handle partial data (missing symbols)."""
        aggregator = MarketSentimentAggregator()

        # Only BTC data, no safe haven
        all_data = {
            "BTCUSDT": create_uptrend_df(roc_pct=10.0),
        }

        sentiment = aggregator.aggregate(all_data)

        # Should still work, but with limited data
        assert isinstance(sentiment, MarketSentiment)
        assert sentiment.risk_indicators.btc_roc_24h > 0

    def test_market_sentiment_has_all_fields(self):
        """MarketSentiment should have all required fields."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_uptrend_df(roc_pct=5.0),
        }

        sentiment = aggregator.aggregate(all_data)

        # Check all required fields exist
        assert hasattr(sentiment, "timestamp")
        assert hasattr(sentiment, "risk_sentiment")
        assert hasattr(sentiment, "risk_indicators")
        assert hasattr(sentiment, "safe_haven_indicators")
        assert hasattr(sentiment, "volatility_indicators")
        assert hasattr(sentiment, "confidence")
        assert hasattr(sentiment, "dominant_factor")
        assert hasattr(sentiment, "summary")
        assert hasattr(sentiment, "raw_scores")

    def test_summary_generation(self):
        """Summary should contain relevant information."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_uptrend_df(roc_pct=5.0),
        }

        sentiment = aggregator.aggregate(all_data)

        assert isinstance(sentiment.summary, str)
        assert len(sentiment.summary) > 0


class TestRiskIndicatorsCalculation:
    """Tests for risk indicators calculation."""

    def test_calculate_risk_indicators_positive(self):
        """Test risk indicators with positive crypto movement."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_uptrend_df(roc_pct=5.0),
            "ETHUSDT": create_uptrend_df(roc_pct=3.0),
        }

        risk = aggregator._calculate_risk_indicators(all_data)

        assert risk.btc_roc_24h > 0
        assert risk.eth_roc_24h > 0
        assert risk.crypto_avg_roc > 0
        assert risk.risk_score > 0

    def test_calculate_risk_indicators_negative(self):
        """Test risk indicators with negative crypto movement."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "BTCUSDT": create_downtrend_df(roc_pct=-5.0),
            "ETHUSDT": create_downtrend_df(roc_pct=-3.0),
        }

        risk = aggregator._calculate_risk_indicators(all_data)

        assert risk.btc_roc_24h < 0
        assert risk.eth_roc_24h < 0
        assert risk.crypto_avg_roc < 0
        assert risk.risk_score < 0


class TestSafeHavenIndicatorsCalculation:
    """Tests for safe haven indicators calculation."""

    def test_calculate_safe_haven_gold_rising(self):
        """Test safe haven indicators with rising gold."""
        aggregator = MarketSentimentAggregator()

        all_data = {
            "GC=F": create_uptrend_df(roc_pct=2.0),
        }

        safe_haven = aggregator._calculate_safe_haven_indicators(all_data)

        assert safe_haven.gold_roc_24h > 0
        assert safe_haven.safe_haven_score > 0


class TestVolatilityRegimeClassification:
    """Tests for volatility regime classification."""

    def test_classify_volatility_low(self):
        """Test low volatility classification."""
        aggregator = MarketSentimentAggregator()

        regime = aggregator._classify_volatility_regime(0.3)
        assert regime == VolatilityRegimeGlobal.LOW

    def test_classify_volatility_normal(self):
        """Test normal volatility classification."""
        aggregator = MarketSentimentAggregator()

        regime = aggregator._classify_volatility_regime(1.0)
        assert regime == VolatilityRegimeGlobal.NORMAL

    def test_classify_volatility_elevated(self):
        """Test elevated volatility classification."""
        aggregator = MarketSentimentAggregator()

        regime = aggregator._classify_volatility_regime(3.0)
        assert regime == VolatilityRegimeGlobal.ELEVATED

    def test_classify_volatility_crisis(self):
        """Test crisis volatility classification."""
        aggregator = MarketSentimentAggregator()

        regime = aggregator._classify_volatility_regime(5.0)
        assert regime == VolatilityRegimeGlobal.CRISIS


class TestRocCalculation:
    """Tests for ROC calculation."""

    def test_calculate_roc_positive(self):
        """Test ROC calculation with positive trend."""
        aggregator = MarketSentimentAggregator()
        df = create_uptrend_df(roc_pct=5.0)

        roc = aggregator._calculate_roc(df)

        assert roc is not None
        assert roc > 0

    def test_calculate_roc_negative(self):
        """Test ROC calculation with negative trend."""
        aggregator = MarketSentimentAggregator()
        df = create_downtrend_df(roc_pct=-5.0)

        roc = aggregator._calculate_roc(df)

        assert roc is not None
        assert roc < 0

    def test_calculate_roc_insufficient_data(self):
        """Test ROC calculation with insufficient data."""
        aggregator = MarketSentimentAggregator(roc_lookback=24)
        df = create_flat_df(periods=10)  # Less than lookback

        roc = aggregator._calculate_roc(df)

        assert roc is None

    def test_calculate_roc_empty_df(self):
        """Test ROC calculation with empty DataFrame."""
        aggregator = MarketSentimentAggregator()
        df = pd.DataFrame()

        roc = aggregator._calculate_roc(df)

        assert roc is None


class TestAtrPercentCalculation:
    """Tests for ATR% calculation."""

    def test_calculate_atr_percent(self):
        """Test ATR% calculation returns valid value."""
        aggregator = MarketSentimentAggregator()
        df = create_ohlcv_df([100.0] * 30, high_factor=1.02, low_factor=0.98)

        atr_pct = aggregator._calculate_atr_percent(df)

        assert atr_pct is not None
        assert atr_pct > 0

    def test_calculate_atr_percent_insufficient_data(self):
        """Test ATR% calculation with insufficient data."""
        aggregator = MarketSentimentAggregator(atr_period=14)
        df = create_flat_df(periods=10)  # Less than ATR period

        atr_pct = aggregator._calculate_atr_percent(df)

        assert atr_pct is None


class TestSentimentClassification:
    """Tests for sentiment classification logic."""

    def test_classify_sentiment_risk_on(self):
        """Test classification produces RISK_ON."""
        aggregator = MarketSentimentAggregator()

        risk = RiskIndicators(risk_score=0.5)
        safe_haven = SafeHavenIndicators(safe_haven_score=0.0)
        volatility = GlobalVolatilityIndicators()

        sentiment, confidence, factor = aggregator._classify_sentiment(
            risk, safe_haven, volatility
        )

        assert sentiment == RiskSentiment.RISK_ON

    def test_classify_sentiment_risk_off(self):
        """Test classification produces RISK_OFF."""
        aggregator = MarketSentimentAggregator()

        risk = RiskIndicators(risk_score=-0.2)
        safe_haven = SafeHavenIndicators(safe_haven_score=0.5)
        volatility = GlobalVolatilityIndicators()

        sentiment, confidence, factor = aggregator._classify_sentiment(
            risk, safe_haven, volatility
        )

        assert sentiment == RiskSentiment.RISK_OFF

    def test_classify_sentiment_neutral(self):
        """Test classification produces NEUTRAL."""
        aggregator = MarketSentimentAggregator()

        risk = RiskIndicators(risk_score=0.1)
        safe_haven = SafeHavenIndicators(safe_haven_score=0.1)
        volatility = GlobalVolatilityIndicators()

        sentiment, confidence, factor = aggregator._classify_sentiment(
            risk, safe_haven, volatility
        )

        assert sentiment == RiskSentiment.NEUTRAL

    def test_classify_sentiment_crisis_override(self):
        """Test crisis volatility overrides to NEUTRAL."""
        aggregator = MarketSentimentAggregator()

        # Strong risk-on signals
        risk = RiskIndicators(risk_score=0.8)
        safe_haven = SafeHavenIndicators(safe_haven_score=0.0)
        volatility = GlobalVolatilityIndicators(regime=VolatilityRegimeGlobal.CRISIS)

        sentiment, confidence, factor = aggregator._classify_sentiment(
            risk, safe_haven, volatility
        )

        # Crisis should override to neutral
        assert sentiment == RiskSentiment.NEUTRAL
        assert "crisis" in factor.lower()


class TestDataclasses:
    """Tests for dataclass definitions."""

    def test_risk_sentiment_enum_values(self):
        """Test RiskSentiment enum has expected values."""
        assert RiskSentiment.RISK_ON.value == "risk_on"
        assert RiskSentiment.RISK_OFF.value == "risk_off"
        assert RiskSentiment.NEUTRAL.value == "neutral"

    def test_volatility_regime_global_enum_values(self):
        """Test VolatilityRegimeGlobal enum has expected values."""
        assert VolatilityRegimeGlobal.LOW.value == "low"
        assert VolatilityRegimeGlobal.NORMAL.value == "normal"
        assert VolatilityRegimeGlobal.ELEVATED.value == "elevated"
        assert VolatilityRegimeGlobal.CRISIS.value == "crisis"

    def test_risk_indicators_defaults(self):
        """Test RiskIndicators has correct defaults."""
        indicators = RiskIndicators()

        assert indicators.btc_roc_24h == 0.0
        assert indicators.eth_roc_24h == 0.0
        assert indicators.crypto_avg_roc == 0.0
        assert indicators.risk_score == 0.0

    def test_safe_haven_indicators_defaults(self):
        """Test SafeHavenIndicators has correct defaults."""
        indicators = SafeHavenIndicators()

        assert indicators.gold_roc_24h == 0.0
        assert indicators.jpy_strength == 0.0
        assert indicators.chf_strength == 0.0
        assert indicators.safe_haven_score == 0.0

    def test_global_volatility_indicators_defaults(self):
        """Test GlobalVolatilityIndicators has correct defaults."""
        indicators = GlobalVolatilityIndicators()

        assert indicators.forex_avg_atr_pct == 0.0
        assert indicators.crypto_avg_atr_pct == 0.0
        assert indicators.cross_market_atr_pct == 0.0
        assert indicators.volatility_expansion is False
        assert indicators.regime == VolatilityRegimeGlobal.NORMAL
