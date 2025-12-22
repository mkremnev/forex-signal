import pytest
import pandas as pd

from forex_signal_agent.analyzer import analyze_pair, _detect_ema_trend, _analyze_trend
from forex_signal_agent.indicators import compute_indicators


@pytest.fixture
def empty_dataframe():
    """Empty DataFrame for edge case tests."""
    return pd.DataFrame()


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for indicator tests."""
    return pd.DataFrame({
        "o": [1.0, 1.1, 1.2, 1.3, 1.4],
        "h": [1.05, 1.15, 1.25, 1.35, 1.45],
        "l": [0.95, 1.05, 1.15, 1.25, 1.35],
        "c": [1.02, 1.12, 1.22, 1.32, 1.42],
        "v": [1000, 1100, 1200, 1300, 1400],
    })


class TestAnalyzer:
    def test_analyze_pair_empty_data(self, empty_dataframe):
        """Empty data returns empty events list."""
        events = analyze_pair(
            empty_dataframe, empty_dataframe, "EUR_USD", 20.0, 70.0, 30.0
        )
        assert events == []

    @pytest.mark.parametrize(
        ("ema20", "ema50", "expected_trend"),
        [
            (1.2000, 1.1900, "up"),
            (1.1900, 1.2000, "down"),
            (1.2000, 1.2000, None),  # equal EMAs return None (no clear trend)
        ],
        ids=["uptrend", "downtrend", "equal-ema"],
    )
    def test_detect_ema_trend(self, ema20, ema50, expected_trend):
        """EMA trend detection based on EMA20 vs EMA50."""
        bar_data = pd.Series({"ema20": ema20, "ema50": ema50})
        assert _detect_ema_trend(bar_data) == expected_trend

    def test_analyze_trend_up_with_strong_adx(self):
        """Strong uptrend detected when EMA20 > EMA50 and ADX > threshold."""
        bar_data = pd.Series({"ema20": 1.2000, "ema50": 1.1900, "adx": 25.0})

        events = _analyze_trend(bar_data, "EUR_USD", adx_threshold=20.0)

        assert len(events) == 1
        assert events[0].kind == "trend_up"
        assert "восходящий тренд" in events[0].message.lower()


class TestIndicators:
    EXPECTED_COLUMNS = {
        "o", "h", "l", "c", "v",
        "ema20", "ema50", "adx",
        "macd", "macd_signal", "macd_hist", "rsi",
    }

    def test_compute_indicators_adds_all_columns(self, sample_ohlcv_data):
        """compute_indicators adds all expected indicator columns."""
        result = compute_indicators(sample_ohlcv_data)
        assert set(result.columns) == self.EXPECTED_COLUMNS

    def test_compute_indicators_empty_dataframe(self, empty_dataframe):
        """Empty DataFrame handled correctly."""
        result = compute_indicators(empty_dataframe)
        assert result.empty