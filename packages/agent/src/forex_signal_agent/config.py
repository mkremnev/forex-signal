from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional
import yaml


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    message_cooldown_minutes: int = 60


@dataclass
class TimeframeJob:
    timeframe: str = "5"
    poll_interval_seconds: int = 60


@dataclass
class BacktestConfig:
    enabled: bool = False
    lookback_bars: int = 1500


@dataclass
class RedisConfig:
    """Redis configuration for Pub/Sub integration with Dashboard"""
    enabled: bool = False
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    status_interval_seconds: int = 30
    reconnect_max_attempts: int = 10
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 60.0


@dataclass
class CorrelationConfig:
    """Configuration for correlation analysis"""
    lookback_hours: int = 24
    min_data_points: int = 20
    high_correlation_threshold: float = 0.7


@dataclass
class VolatilityRegimeThresholds:
    """Thresholds for volatility regime classification (ATR% values)"""
    low: float = 0.5       # < 0.5% is low volatility
    normal: float = 1.0    # 0.5% - 1.0% is normal
    high: float = 2.0      # 1.0% - 2.0% is high, > 2.0% is extreme


@dataclass
class VolatilityConfig:
    """Configuration for volatility analysis"""
    atr_period: int = 14
    consolidation_threshold: float = 0.01  # 1% ATR/price ratio
    regime_thresholds: VolatilityRegimeThresholds = field(default_factory=VolatilityRegimeThresholds)


@dataclass
class ProbabilityConfig:
    """Configuration for probability model"""
    confidence_threshold: float = 0.4
    high_confidence_threshold: float = 0.6
    roc_lookback_periods: int = 24
    weights: dict = field(default_factory=lambda: {
        "roc": 0.33,
        "volatility": 0.33,
        "volume": 0.0,
        "correlation": 0.33
    })


@dataclass
class CryptoConfig:
    """Configuration for cryptocurrency data provider"""
    enabled: bool = False
    pairs: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    sandbox: bool = False


@dataclass
class SentimentVolatilityThresholds:
    """Thresholds for global volatility regime in sentiment analysis (ATR% values)"""
    low: float = 0.5
    elevated: float = 2.0
    crisis: float = 4.0


@dataclass
class SentimentConfig:
    """Configuration for market sentiment aggregation"""
    enabled: bool = True
    roc_lookback: int = 24
    risk_threshold: float = 0.3
    safe_haven_threshold: float = 0.3
    risk_assets: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    safe_haven_assets: List[str] = field(default_factory=lambda: ["GC=F", "USDJPY=X", "USDCHF=X"])
    volatility_thresholds: SentimentVolatilityThresholds = field(default_factory=SentimentVolatilityThresholds)


@dataclass
class AppConfig:
    timezone: str = "Europe/Moscow"
    pairs: List[str] = field(default_factory=lambda: ["EUR_USD", "GBP_USD", "USD_JPY"])
    timeframes: List[TimeframeJob] = field(default_factory=lambda: [TimeframeJob(timeframe="5", poll_interval_seconds=60)])
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    notify_hourly_summary: bool = True
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    sqlite_path: str = "./data/cache.db"
    redis: RedisConfig = field(default_factory=RedisConfig)
    correlation: CorrelationConfig = field(default_factory=CorrelationConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    probability: ProbabilityConfig = field(default_factory=ProbabilityConfig)
    crypto: CryptoConfig = field(default_factory=CryptoConfig)
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)


def load_config(path: Optional[str] = None) -> AppConfig:
    cfg = AppConfig()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # shallow merge
        _merge_dataclass(cfg, raw)

    # env overrides
    cfg.telegram.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", cfg.telegram.bot_token)
    cfg.telegram.chat_id = os.getenv("TELEGRAM_CHAT_ID", cfg.telegram.chat_id)
    cfg.sqlite_path = os.getenv("SQLITE_PATH", cfg.sqlite_path)

    # Redis env overrides
    if os.getenv("REDIS_ENABLED", "").lower() in ("true", "1", "yes"):
        cfg.redis.enabled = True
    cfg.redis.host = os.getenv("REDIS_HOST", cfg.redis.host)
    if os.getenv("REDIS_PORT"):
        try:
            cfg.redis.port = int(os.getenv("REDIS_PORT", "6379"))
        except ValueError:
            pass
    cfg.redis.password = os.getenv("REDIS_PASSWORD", cfg.redis.password)

    # Crypto env override
    if os.getenv("CRYPTO_ENABLED", "").lower() in ("true", "1", "yes"):
        cfg.crypto.enabled = True

    # Normalize timeframes to dataclass instances
    normalized_tfs: List[TimeframeJob] = []
    for item in cfg.timeframes or []:
        if isinstance(item, TimeframeJob):
            normalized_tfs.append(item)
        elif isinstance(item, dict):
            tf = str(item.get("timeframe", "5"))
            try:
                poll = int(item.get("poll_interval_seconds", 60))
            except (TypeError, ValueError):
                poll = 60
            normalized_tfs.append(TimeframeJob(timeframe=tf, poll_interval_seconds=poll))
        else:
            # allow simple values like "5" or 5
            normalized_tfs.append(TimeframeJob(timeframe=str(item), poll_interval_seconds=60))
    if normalized_tfs:
        cfg.timeframes = normalized_tfs

    return cfg


def _merge_dataclass(dc_obj, raw: dict):
    for k, v in raw.items():
        if not hasattr(dc_obj, k):
            continue
        cur = getattr(dc_obj, k)
        if isinstance(cur, list) and isinstance(v, list):
            setattr(dc_obj, k, v)
        elif hasattr(cur, "__dataclass_fields__") and isinstance(v, dict):
            _merge_dataclass(cur, v)
        else:
            setattr(dc_obj, k, v)
