"""Unit tests for Telegram message formatters."""

from datetime import datetime, timezone
from dataclasses import dataclass, field

import pytest

from forex_signal_agent.message_formatter import (
    format_probability_signal,
    format_volatility_alert,
    _confidence_bar,
)


@dataclass
class MockAnalysisEvent:
    """Mock AnalysisEvent for testing."""

    event_type: str
    symbol: str
    timeframe: str
    timestamp: datetime
    importance: int
    data: dict = field(default_factory=dict)


class TestConfidenceBar:
    """Tests for _confidence_bar helper function."""

    def test_confidence_bar_empty(self):
        """Test confidence bar with 0% confidence."""
        result = _confidence_bar(0.0)
        assert result == "░░░░░"
        assert len(result) == 5

    def test_confidence_bar_full(self):
        """Test confidence bar with 100% confidence."""
        result = _confidence_bar(1.0)
        assert result == "█████"
        assert len(result) == 5

    def test_confidence_bar_half(self):
        """Test confidence bar with 50% confidence."""
        result = _confidence_bar(0.5)
        assert result == "██░░░" or result == "███░░"
        assert len(result) == 5

    def test_confidence_bar_high(self):
        """Test confidence bar with 80% confidence."""
        result = _confidence_bar(0.8)
        assert result == "████░"
        assert len(result) == 5

    def test_confidence_bar_low(self):
        """Test confidence bar with 20% confidence."""
        result = _confidence_bar(0.2)
        assert result == "█░░░░"
        assert len(result) == 5


class TestFormatProbabilitySignal:
    """Tests for format_probability_signal function."""

    def test_format_probability_signal_upward(self):
        """Test formatting for upward probability signal."""
        event = MockAnalysisEvent(
            event_type="probability_signal",
            symbol="EUR_USD",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            importance=2,
            data={
                "direction": "upward",
                "confidence": 0.65,
                "probabilities": {
                    "upward": 0.65,
                    "downward": 0.25,
                    "consolidation": 0.10,
                },
                "is_actionable": True,
                "factors": {"roc": 0.2, "volatility": 0.3},
            },
        )

        result = format_probability_signal(event)

        # Check required content from plan
        assert "EUR_USD" in result
        assert "📈" in result  # upward emoji
        assert "Рост" in result  # Russian direction name
        assert "65%" in result  # confidence percentage
        assert "Сигнал к действию" in result  # actionable indicator

    def test_format_probability_signal_downward(self):
        """Test formatting for downward probability signal."""
        event = MockAnalysisEvent(
            event_type="probability_signal",
            symbol="GBP_USD",
            timeframe="4h",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "direction": "downward",
                "confidence": 0.55,
                "probabilities": {
                    "upward": 0.25,
                    "downward": 0.55,
                    "consolidation": 0.20,
                },
                "is_actionable": False,
            },
        )

        result = format_probability_signal(event)

        assert "GBP_USD" in result
        assert "📉" in result  # downward emoji
        assert "Падение" in result
        assert "55%" in result
        assert "Сигнал к действию" not in result  # not actionable

    def test_format_probability_signal_consolidation(self):
        """Test formatting for consolidation signal."""
        event = MockAnalysisEvent(
            event_type="probability_signal",
            symbol="USD_JPY",
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "direction": "consolidation",
                "confidence": 0.40,
                "probabilities": {
                    "upward": 0.30,
                    "downward": 0.30,
                    "consolidation": 0.40,
                },
                "is_actionable": False,
            },
        )

        result = format_probability_signal(event)

        assert "USD_JPY" in result
        assert "➡️" in result  # consolidation emoji
        assert "Консолидация" in result
        assert "40%" in result

    def test_format_probability_signal_includes_timeframe(self):
        """Test that timeframe is included in output."""
        event = MockAnalysisEvent(
            event_type="probability_signal",
            symbol="EUR_USD",
            timeframe="4h",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "direction": "upward",
                "confidence": 0.50,
                "probabilities": {},
                "is_actionable": False,
            },
        )

        result = format_probability_signal(event)
        assert "(4h)" in result


class TestFormatVolatilityAlert:
    """Tests for format_volatility_alert function."""

    def test_format_volatility_alert_extreme(self):
        """Test formatting for extreme volatility alert."""
        event = MockAnalysisEvent(
            event_type="volatility_alert",
            symbol="EUR_USD",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            importance=2,
            data={
                "regime": "extreme",
                "atr_percent": 0.0325,
                "is_consolidation": False,
            },
        )

        result = format_volatility_alert(event)

        assert "EUR_USD" in result
        assert "🔥" in result  # extreme emoji
        assert "Экстремальная волатильность" in result
        assert "3.25%" in result  # ATR percent

    def test_format_volatility_alert_high(self):
        """Test formatting for high volatility alert."""
        event = MockAnalysisEvent(
            event_type="volatility_alert",
            symbol="GBP_USD",
            timeframe="4h",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "regime": "high",
                "atr_percent": 0.0215,
                "is_consolidation": False,
            },
        )

        result = format_volatility_alert(event)

        assert "GBP_USD" in result
        assert "⚠️" in result  # non-extreme emoji
        assert "Высокая волатильность" in result
        assert "2.15%" in result

    def test_format_volatility_alert_with_consolidation(self):
        """Test formatting for volatility alert with consolidation."""
        event = MockAnalysisEvent(
            event_type="volatility_alert",
            symbol="USD_JPY",
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "regime": "low",
                "atr_percent": 0.0085,
                "is_consolidation": True,
            },
        )

        result = format_volatility_alert(event)

        assert "USD_JPY" in result
        assert "Низкая волатильность" in result
        assert "Рынок в консолидации" in result

    def test_format_volatility_alert_normal(self):
        """Test formatting for normal volatility alert."""
        event = MockAnalysisEvent(
            event_type="volatility_alert",
            symbol="EUR_GBP",
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            importance=1,
            data={
                "regime": "normal",
                "atr_percent": 0.0150,
                "is_consolidation": False,
            },
        )

        result = format_volatility_alert(event)

        assert "EUR_GBP" in result
        assert "⚠️" in result
        assert "Нормальная волатильность" in result
        assert "1.50%" in result
        assert "Рынок в консолидации" not in result
