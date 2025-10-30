"""Configuration validation module."""

from typing import Dict, Any
from pydantic import BaseModel, validator, ValidationError
from .config import AppConfig, TimeframeJob, TelegramConfig, BacktestConfig


class ValidatedAppConfig(AppConfig):
    """Validated configuration with additional validation rules."""
    
    @validator('adx_threshold')
    def adx_threshold_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('ADX threshold must be positive')
        return v
        
    @validator('rsi_overbought')
    def rsi_overbought_must_be_in_range(cls, v):
        if not 50 <= v <= 100:
            raise ValueError('RSI overbought threshold must be between 50 and 100')
        return v
        
    @validator('rsi_oversold')
    def rsi_oversold_must_be_in_range(cls, v):
        if not 0 <= v <= 50:
            raise ValueError('RSI oversold threshold must be between 0 and 50')
        return v
        
    @validator('rsi_overbought', 'rsi_oversold')
    def rsi_values_must_be_consistent(cls, v, values, field):
        """Ensure RSI thresholds are consistent."""
        if 'rsi_overbought' in values and 'rsi_oversold' in values:
            if values['rsi_overbought'] <= values['rsi_oversold']:
                raise ValueError('RSI overbought threshold must be greater than oversold threshold')
        return v

    @validator('timeframes')
    def validate_timeframes(cls, v):
        if not v:
            raise ValueError('At least one timeframe must be specified')
        for tf in v:
            if isinstance(tf, TimeframeJob):
                tf = {'timeframe': tf.timeframe, 'poll_interval_seconds': tf.poll_interval_seconds}
            if not isinstance(tf, dict):
                continue
            timeframe = tf.get('timeframe', '')
            if timeframe not in ['1', '5', '15', '30', '60', '1h', '4h', 'D']:
                raise ValueError(f'Invalid timeframe: {timeframe}')
            poll_interval = tf.get('poll_interval_seconds', 60)
            if poll_interval <= 0:
                raise ValueError(f'Poll interval must be positive, got: {poll_interval}')
        return v


def validate_config(config: AppConfig) -> ValidatedAppConfig:
    """Validate the configuration and return a validated copy."""
    try:
        # Convert the config to dict and back to validated model
        config_dict = {
            'timezone': config.timezone,
            'pairs': config.pairs,
            'timeframes': [{'timeframe': tf.timeframe, 'poll_interval_seconds': tf.poll_interval_seconds} 
                          if hasattr(tf, 'timeframe') else tf for tf in config.timeframes],
            'telegram': {
                'bot_token': config.telegram.bot_token,
                'chat_id': config.telegram.chat_id,
                'message_cooldown_minutes': config.telegram.message_cooldown_minutes
            },
            'adx_threshold': config.adx_threshold,
            'rsi_overbought': config.rsi_overbought,
            'rsi_oversold': config.rsi_oversold,
            'notify_hourly_summary': config.notify_hourly_summary,
            'backtest': {
                'enabled': config.backtest.enabled,
                'lookback_bars': config.backtest.lookback_bars
            },
            'sqlite_path': config.sqlite_path
        }
        
        return ValidatedAppConfig(**config_dict)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}")