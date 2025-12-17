"""Pydantic schemas for settings."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from forex_backend.models.setting import ValueType


class SettingBase(BaseModel):
    """Base setting schema."""

    key: str = Field(..., min_length=1, max_length=255)
    value: Any


class SettingCreate(SettingBase):
    """Schema for creating a setting."""

    pass


class SettingUpdate(BaseModel):
    """Schema for updating a setting."""

    value: Any


class SettingRead(SettingBase):
    """Schema for reading a setting."""

    id: UUID
    value_type: ValueType
    is_user_override: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingHistoryRead(BaseModel):
    """Schema for reading setting history."""

    id: UUID
    setting_id: UUID
    old_value: str
    new_value: str
    changed_by: UUID | None
    changed_at: datetime

    model_config = {"from_attributes": True}


# Configuration schemas based on agent's AppConfig
class TelegramConfigSchema(BaseModel):
    """Telegram configuration schema."""

    bot_token: str = Field(default="", description="Telegram bot token")
    chat_id: str = Field(default="", description="Telegram chat ID")
    message_cooldown_minutes: int = Field(
        default=60, ge=1, le=1440, description="Cooldown between messages in minutes"
    )


class TimeframeJobSchema(BaseModel):
    """Timeframe job configuration schema."""

    timeframe: str = Field(..., description="Timeframe (e.g., '5', '15', '60')")
    poll_interval_seconds: int = Field(
        default=60, ge=10, le=3600, description="Polling interval in seconds"
    )


class BacktestConfigSchema(BaseModel):
    """Backtest configuration schema."""

    enabled: bool = Field(default=False, description="Enable backtesting")
    lookback_bars: int = Field(
        default=1500, ge=100, le=10000, description="Number of bars to look back"
    )


class AppConfigSchema(BaseModel):
    """Full application configuration schema with validation."""

    # Trading
    timezone: str = Field(default="Europe/Moscow", description="Timezone")
    pairs: list[str] = Field(
        default=["EUR_USD", "GBP_USD", "USD_JPY"],
        min_length=1,
        description="Currency pairs to trade",
    )
    notify_hourly_summary: bool = Field(
        default=True, description="Send hourly summary notifications"
    )

    # Timeframes
    timeframes: list[TimeframeJobSchema] = Field(
        default=[TimeframeJobSchema(timeframe="5", poll_interval_seconds=60)],
        min_length=1,
        description="Timeframe configurations",
    )

    # Telegram
    telegram: TelegramConfigSchema = Field(
        default_factory=TelegramConfigSchema, description="Telegram configuration"
    )

    # Indicators
    adx_threshold: float = Field(
        default=20.0, ge=0, le=100, description="ADX threshold"
    )
    rsi_overbought: float = Field(
        default=70.0, ge=50, le=100, description="RSI overbought level"
    )
    rsi_oversold: float = Field(
        default=30.0, ge=0, le=50, description="RSI oversold level"
    )

    # System
    sqlite_path: str = Field(
        default="./data/cache.db", description="Path to SQLite cache database"
    )
    backtest: BacktestConfigSchema = Field(
        default_factory=BacktestConfigSchema, description="Backtest configuration"
    )

    @field_validator("rsi_overbought", "rsi_oversold")
    @classmethod
    def validate_rsi_levels(cls, v: float, info) -> float:
        """Validate RSI levels."""
        if info.field_name == "rsi_overbought" and v <= 50:
            raise ValueError("RSI overbought must be greater than 50")
        if info.field_name == "rsi_oversold" and v >= 50:
            raise ValueError("RSI oversold must be less than 50")
        return v

    model_config = {"from_attributes": True}


class BulkUpdateRequest(BaseModel):
    """Schema for bulk updating settings."""

    updates: dict[str, Any] = Field(
        ..., description="Dictionary of setting keys and their new values"
    )