"""Market Sentiment Aggregation module.

Aggregates data from multiple markets (Forex + Crypto) to determine
overall market sentiment (risk-on / risk-off / neutral) and volatility regime.

Flow:
    [Forex + Crypto data] → MarketSentimentAggregator → MarketSentiment
                                                            ↓
    [Instrument analysis] ← market context modifier ← MarketSentiment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class RiskSentiment(str, Enum):
    """Market risk sentiment classification."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NEUTRAL = "neutral"


class VolatilityRegimeGlobal(str, Enum):
    """Global volatility regime classification."""

    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRISIS = "crisis"


@dataclass
class RiskIndicators:
    """Risk asset indicators (BTC, ETH, etc.).

    Attributes:
        btc_roc_24h: BTC rate of change over 24h (%)
        eth_roc_24h: ETH rate of change over 24h (%)
        crypto_avg_roc: Average ROC across crypto assets (%)
        risk_score: Normalized risk score (-1 to 1)
    """

    btc_roc_24h: float = 0.0
    eth_roc_24h: float = 0.0
    crypto_avg_roc: float = 0.0
    risk_score: float = 0.0


@dataclass
class SafeHavenIndicators:
    """Safe haven asset indicators (Gold, JPY, CHF).

    Attributes:
        gold_roc_24h: Gold rate of change over 24h (%)
        jpy_strength: JPY strength indicator
        chf_strength: CHF strength indicator
        safe_haven_score: Normalized safe haven score (-1 to 1)
    """

    gold_roc_24h: float = 0.0
    jpy_strength: float = 0.0
    chf_strength: float = 0.0
    safe_haven_score: float = 0.0


@dataclass
class GlobalVolatilityIndicators:
    """Global volatility indicators.

    Attributes:
        forex_avg_atr_pct: Average ATR% across forex pairs
        crypto_avg_atr_pct: Average ATR% across crypto pairs
        cross_market_atr_pct: Combined cross-market ATR%
        volatility_expansion: True if volatility is expanding
        regime: Current volatility regime
    """

    forex_avg_atr_pct: float = 0.0
    crypto_avg_atr_pct: float = 0.0
    cross_market_atr_pct: float = 0.0
    volatility_expansion: bool = False
    regime: VolatilityRegimeGlobal = VolatilityRegimeGlobal.NORMAL


@dataclass
class MarketSentiment:
    """Aggregated market sentiment.

    Attributes:
        timestamp: When sentiment was calculated
        risk_sentiment: Overall risk sentiment (risk_on/risk_off/neutral)
        risk_indicators: Risk asset indicators
        safe_haven_indicators: Safe haven indicators
        volatility_indicators: Volatility indicators
        confidence: Confidence in the sentiment classification (0-1)
        dominant_factor: Main factor driving the sentiment
        summary: Human-readable summary
        raw_scores: Raw calculation scores for debugging
    """

    timestamp: datetime
    risk_sentiment: RiskSentiment
    risk_indicators: RiskIndicators
    safe_haven_indicators: SafeHavenIndicators
    volatility_indicators: GlobalVolatilityIndicators
    confidence: float
    dominant_factor: str
    summary: str
    raw_scores: Dict[str, float] = field(default_factory=dict)


class MarketSentimentAggregator:
    """Aggregates market data to determine overall market sentiment.

    Uses crypto assets (BTC, ETH) as risk indicators and Gold/JPY/CHF
    as safe haven indicators to classify market sentiment.

    Example:
        aggregator = MarketSentimentAggregator()
        sentiment = aggregator.aggregate(all_data)
        print(f"Sentiment: {sentiment.risk_sentiment.value}")
    """

    # Default risk assets (crypto)
    DEFAULT_RISK_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # Default safe haven assets
    DEFAULT_SAFE_HAVEN = ["GC=F", "USDJPY=X", "USDCHF=X"]

    # Thresholds for sentiment classification
    RISK_THRESHOLD = 0.3
    SAFE_HAVEN_THRESHOLD = 0.3

    # Volatility thresholds (ATR%)
    VOL_LOW_THRESHOLD = 0.5
    VOL_ELEVATED_THRESHOLD = 2.0
    VOL_CRISIS_THRESHOLD = 4.0

    def __init__(
        self,
        roc_lookback: int = 24,
        atr_period: int = 14,
        risk_assets: Optional[List[str]] = None,
        safe_haven_assets: Optional[List[str]] = None,
    ):
        """Initialize market sentiment aggregator.

        Args:
            roc_lookback: Lookback periods for ROC calculation
            atr_period: ATR calculation period
            risk_assets: List of risk asset symbols (default: crypto)
            safe_haven_assets: List of safe haven symbols
        """
        self._roc_lookback = roc_lookback
        self._atr_period = atr_period
        self._risk_assets = risk_assets or self.DEFAULT_RISK_ASSETS
        self._safe_haven_assets = safe_haven_assets or self.DEFAULT_SAFE_HAVEN

    def aggregate(self, all_data: Dict[str, pd.DataFrame]) -> MarketSentiment:
        """Aggregate market data to determine sentiment.

        Args:
            all_data: Dictionary mapping symbol to OHLCV DataFrame

        Returns:
            MarketSentiment with aggregated analysis
        """
        now = datetime.now(timezone.utc)

        # Calculate indicators
        risk = self._calculate_risk_indicators(all_data)
        safe_haven = self._calculate_safe_haven_indicators(all_data)
        volatility = self._calculate_volatility_indicators(all_data)

        # Classify sentiment
        sentiment, confidence, factor = self._classify_sentiment(
            risk, safe_haven, volatility
        )

        # Generate summary
        summary = self._generate_summary(sentiment, risk, safe_haven, volatility, factor)

        return MarketSentiment(
            timestamp=now,
            risk_sentiment=sentiment,
            risk_indicators=risk,
            safe_haven_indicators=safe_haven,
            volatility_indicators=volatility,
            confidence=confidence,
            dominant_factor=factor,
            summary=summary,
            raw_scores={
                "risk_score": risk.risk_score,
                "safe_haven_score": safe_haven.safe_haven_score,
                "net_score": risk.risk_score - safe_haven.safe_haven_score,
            },
        )

    def _calculate_risk_indicators(
        self, all_data: Dict[str, pd.DataFrame]
    ) -> RiskIndicators:
        """Calculate risk asset indicators.

        Args:
            all_data: Market data dictionary

        Returns:
            RiskIndicators with calculated values
        """
        btc_roc = 0.0
        eth_roc = 0.0
        rocs: List[float] = []

        # Calculate ROC for each risk asset
        for symbol in self._risk_assets:
            if symbol not in all_data:
                continue

            roc = self._calculate_roc(all_data[symbol])
            if roc is None:
                continue

            rocs.append(roc)

            if "BTC" in symbol:
                btc_roc = roc
            elif "ETH" in symbol:
                eth_roc = roc

        # Average ROC
        avg_roc = sum(rocs) / len(rocs) if rocs else 0.0

        # Normalize to -1 to 1 (assuming ±10% is extreme)
        risk_score = max(-1.0, min(1.0, avg_roc / 10.0))

        return RiskIndicators(
            btc_roc_24h=btc_roc,
            eth_roc_24h=eth_roc,
            crypto_avg_roc=avg_roc,
            risk_score=risk_score,
        )

    def _calculate_safe_haven_indicators(
        self, all_data: Dict[str, pd.DataFrame]
    ) -> SafeHavenIndicators:
        """Calculate safe haven asset indicators.

        Args:
            all_data: Market data dictionary

        Returns:
            SafeHavenIndicators with calculated values
        """
        gold_roc = 0.0
        jpy_strength = 0.0
        chf_strength = 0.0
        scores: List[float] = []

        for symbol in self._safe_haven_assets:
            if symbol not in all_data:
                continue

            roc = self._calculate_roc(all_data[symbol])
            if roc is None:
                continue

            if "GC=" in symbol or "GOLD" in symbol.upper():
                gold_roc = roc
                # Gold rising = safe haven demand
                scores.append(roc / 5.0)  # Normalize (±5% is significant for Gold)
            elif "JPY" in symbol:
                # For USD/JPY, falling = JPY strength = safe haven
                jpy_strength = -roc / 3.0  # Normalize and invert
                scores.append(jpy_strength)
            elif "CHF" in symbol:
                # For USD/CHF, falling = CHF strength = safe haven
                chf_strength = -roc / 3.0
                scores.append(chf_strength)

        # Average safe haven score
        avg_score = sum(scores) / len(scores) if scores else 0.0
        safe_haven_score = max(-1.0, min(1.0, avg_score))

        return SafeHavenIndicators(
            gold_roc_24h=gold_roc,
            jpy_strength=jpy_strength,
            chf_strength=chf_strength,
            safe_haven_score=safe_haven_score,
        )

    def _calculate_volatility_indicators(
        self, all_data: Dict[str, pd.DataFrame]
    ) -> GlobalVolatilityIndicators:
        """Calculate global volatility indicators.

        Args:
            all_data: Market data dictionary

        Returns:
            GlobalVolatilityIndicators with calculated values
        """
        forex_atrs: List[float] = []
        crypto_atrs: List[float] = []

        for symbol, df in all_data.items():
            atr_pct = self._calculate_atr_percent(df)
            if atr_pct is None:
                continue

            # Classify by symbol type
            if any(crypto in symbol for crypto in ["BTC", "ETH", "SOL", "USDT"]):
                crypto_atrs.append(atr_pct)
            else:
                forex_atrs.append(atr_pct)

        # Calculate averages
        forex_avg = sum(forex_atrs) / len(forex_atrs) if forex_atrs else 0.0
        crypto_avg = sum(crypto_atrs) / len(crypto_atrs) if crypto_atrs else 0.0

        # Cross-market average (weight forex less than crypto due to different scales)
        all_atrs = forex_atrs + [a * 0.5 for a in crypto_atrs]  # Scale crypto down
        cross_market = sum(all_atrs) / len(all_atrs) if all_atrs else 0.0

        # Determine regime
        regime = self._classify_volatility_regime(cross_market)

        # Check for volatility expansion (compare recent vs historical)
        # Simplified: just check if above normal threshold
        volatility_expansion = cross_market > self.VOL_ELEVATED_THRESHOLD

        return GlobalVolatilityIndicators(
            forex_avg_atr_pct=forex_avg,
            crypto_avg_atr_pct=crypto_avg,
            cross_market_atr_pct=cross_market,
            volatility_expansion=volatility_expansion,
            regime=regime,
        )

    def _classify_volatility_regime(self, atr_pct: float) -> VolatilityRegimeGlobal:
        """Classify volatility regime based on ATR%.

        Args:
            atr_pct: Cross-market ATR percentage

        Returns:
            Volatility regime classification
        """
        if atr_pct < self.VOL_LOW_THRESHOLD:
            return VolatilityRegimeGlobal.LOW
        elif atr_pct < self.VOL_ELEVATED_THRESHOLD:
            return VolatilityRegimeGlobal.NORMAL
        elif atr_pct < self.VOL_CRISIS_THRESHOLD:
            return VolatilityRegimeGlobal.ELEVATED
        else:
            return VolatilityRegimeGlobal.CRISIS

    def _classify_sentiment(
        self,
        risk: RiskIndicators,
        safe_haven: SafeHavenIndicators,
        volatility: GlobalVolatilityIndicators,
    ) -> Tuple[RiskSentiment, float, str]:
        """Classify overall market sentiment.

        Logic:
        - net_score = risk_score - safe_haven_score
        - net_score > 0.3 → RISK_ON
        - net_score < -0.3 or safe_haven_score > 0.3 → RISK_OFF
        - Crisis volatility → override to NEUTRAL
        - Otherwise → NEUTRAL

        Args:
            risk: Risk indicators
            safe_haven: Safe haven indicators
            volatility: Volatility indicators

        Returns:
            Tuple of (sentiment, confidence, dominant_factor)
        """
        net_score = risk.risk_score - safe_haven.safe_haven_score

        # Default values
        sentiment = RiskSentiment.NEUTRAL
        confidence = 0.5
        factor = "mixed_signals"

        # Crisis volatility overrides everything
        if volatility.regime == VolatilityRegimeGlobal.CRISIS:
            sentiment = RiskSentiment.NEUTRAL
            confidence = 0.4
            factor = "crisis_volatility"
            logger.debug(f"Crisis volatility override: {volatility.cross_market_atr_pct:.2f}%")
            return sentiment, confidence, factor

        # Classify based on net score
        if net_score > self.RISK_THRESHOLD:
            sentiment = RiskSentiment.RISK_ON
            confidence = min(1.0, 0.5 + abs(net_score))
            factor = "crypto_strength" if risk.risk_score > 0.3 else "risk_appetite"
        elif net_score < -self.SAFE_HAVEN_THRESHOLD or safe_haven.safe_haven_score > self.SAFE_HAVEN_THRESHOLD:
            sentiment = RiskSentiment.RISK_OFF
            confidence = min(1.0, 0.5 + max(abs(net_score), safe_haven.safe_haven_score))
            if safe_haven.gold_roc_24h > 1.0:
                factor = "gold_demand"
            elif safe_haven.jpy_strength > 0.3:
                factor = "jpy_strength"
            elif safe_haven.chf_strength > 0.3:
                factor = "chf_strength"
            else:
                factor = "safe_haven_demand"
        else:
            sentiment = RiskSentiment.NEUTRAL
            confidence = 0.5 - abs(net_score)  # Less confidence when closer to threshold
            factor = "balanced_market"

        # Elevated volatility reduces confidence
        if volatility.regime == VolatilityRegimeGlobal.ELEVATED:
            confidence *= 0.85
            factor += "_elevated_vol"

        logger.debug(
            f"Sentiment classification: {sentiment.value}, "
            f"net_score={net_score:.3f}, confidence={confidence:.2f}, factor={factor}"
        )

        return sentiment, confidence, factor

    def _generate_summary(
        self,
        sentiment: RiskSentiment,
        risk: RiskIndicators,
        safe_haven: SafeHavenIndicators,
        volatility: GlobalVolatilityIndicators,
        factor: str,
    ) -> str:
        """Generate human-readable summary.

        Args:
            sentiment: Risk sentiment
            risk: Risk indicators
            safe_haven: Safe haven indicators
            volatility: Volatility indicators
            factor: Dominant factor

        Returns:
            Summary string
        """
        parts = []

        if sentiment == RiskSentiment.RISK_ON:
            parts.append("Risk-on sentiment")
            if risk.btc_roc_24h != 0:
                parts.append(f"BTC {risk.btc_roc_24h:+.1f}%")
        elif sentiment == RiskSentiment.RISK_OFF:
            parts.append("Risk-off sentiment")
            if safe_haven.gold_roc_24h != 0:
                parts.append(f"Gold {safe_haven.gold_roc_24h:+.1f}%")
        else:
            parts.append("Neutral sentiment")

        if volatility.regime != VolatilityRegimeGlobal.NORMAL:
            parts.append(f"vol={volatility.regime.value}")

        return " | ".join(parts)

    def _calculate_roc(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate Rate of Change over lookback period.

        Args:
            df: OHLCV DataFrame

        Returns:
            ROC as percentage or None
        """
        if df.empty or len(df) < self._roc_lookback + 1:
            return None

        close = df["close"]
        current = close.iloc[-1]
        past = close.iloc[-self._roc_lookback - 1]

        if past <= 0:
            return None

        return ((current - past) / past) * 100

    def _calculate_atr_percent(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate ATR as percentage of price.

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR% or None
        """
        if df.empty or len(df) < self._atr_period + 1:
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
