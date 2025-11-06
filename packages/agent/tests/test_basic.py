import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import asyncio

from forex_signal_agent.analyzer import analyze_pair, _detect_ema_trend, _is_adx_strong, _analyze_trend
from forex_signal_agent.indicators import compute_indicators


class TestAnalyzer:
    def test_analyze_pair_empty_data(self):
        """Test that empty data returns empty events list"""
        df = pd.DataFrame()
        daily_df = pd.DataFrame()
        
        events = analyze_pair(df, daily_df, "EUR_USD", 20.0, 70.0, 30.0)
        
        assert events == []
    
    def test_detect_ema_trend_positive(self):
        """Test EMA trend detection when EMA20 > EMA50"""
        bar_data = pd.Series({
            "ema20": 1.2000,
            "ema50": 1.1900
        })
        
        trend = _detect_ema_trend(bar_data)
        
        assert trend == "up"
    
    def test_detect_ema_trend_negative(self):
        """Test EMA trend detection when EMA20 < EMA50"""
        bar_data = pd.Series({
            "ema20": 1.1900,
            "ema50": 1.2000
        })
        
        trend = _detect_ema_trend(bar_data)
        
        assert trend == "down"
    
    def test_analyze_trend_up_with_strong_adx(self):
        """Test detection of strong uptrend"""
        bar_data = pd.Series({
            "ema20": 1.2000,
            "ema50": 1.1900,
            "adx": 25.0
        })
        
        events = _analyze_trend(bar_data, "EUR_USD", 20.0)
        
        assert len(events) == 1
        assert events[0].kind == "trend_up"
        assert "восходящий тренд" in events[0].message.lower()


class TestIndicators:
    def test_compute_indicators_adds_all_columns(self):
        """Test that compute_indicators adds all expected indicator columns"""
        df = pd.DataFrame({
            'o': [1.0, 1.1, 1.2, 1.3, 1.4],
            'h': [1.05, 1.15, 1.25, 1.35, 1.45],
            'l': [0.95, 1.05, 1.15, 1.25, 1.35],
            'c': [1.02, 1.12, 1.22, 1.32, 1.42],
            'v': [1000, 1100, 1200, 1300, 1400]
        })
        
        result = compute_indicators(df)
        
        expected_columns = {'o', 'h', 'l', 'c', 'v', 'ema20', 'ema50', 'adx', 'macd', 'macd_signal', 'macd_hist', 'rsi'}
        assert set(result.columns) == expected_columns
    
    def test_compute_indicators_empty_dataframe(self):
        """Test that empty DataFrame is handled correctly"""
        df = pd.DataFrame()
        
        result = compute_indicators(df)
        
        assert result.empty


if __name__ == "__main__":
    pytest.main()