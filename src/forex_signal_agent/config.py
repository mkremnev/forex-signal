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
class AppConfig:
    timezone: str = "Europe/Moscow"
    pairs: List[str] = field(default_factory=lambda: ["EUR_USD", "GBP_USD", "USD_JPY"])
    timeframes: List[TimeframeJob] = field(default_factory=lambda: [TimeframeJob(timeframe="5", poll_interval_seconds=60)])
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    adx_threshold: float = 20.0
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    notify_hourly_summary: bool = True
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    sqlite_path: str = "./data/cache.db"


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
