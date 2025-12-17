"""Seed script for initial settings values based on agent config."""

import asyncio
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forex_backend.db.database import async_session_maker
from forex_backend.models.setting import Setting, ValueType


# Default settings based on agent's AppConfig
DEFAULT_SETTINGS = [
    # Telegram config
    {
        "key": "telegram.bot_token",
        "value_type": ValueType.STRING,
        "value": "",
        "default_value": "",
    },
    {
        "key": "telegram.chat_id",
        "value_type": ValueType.STRING,
        "value": "",
        "default_value": "",
    },
    {
        "key": "telegram.message_cooldown_minutes",
        "value_type": ValueType.INT,
        "value": 60,
        "default_value": "60",
    },
    # Trading config
    {
        "key": "timezone",
        "value_type": ValueType.STRING,
        "value": "Europe/Moscow",
        "default_value": "Europe/Moscow",
    },
    {
        "key": "pairs",
        "value_type": ValueType.JSON,
        "value": ["EUR_USD", "GBP_USD", "USD_JPY"],
        "default_value": '["EUR_USD", "GBP_USD", "USD_JPY"]',
    },
    {
        "key": "notify_hourly_summary",
        "value_type": ValueType.BOOL,
        "value": True,
        "default_value": "true",
    },
    # Timeframes config
    {
        "key": "timeframes",
        "value_type": ValueType.JSON,
        "value": [{"timeframe": "5", "poll_interval_seconds": 60}],
        "default_value": '[{"timeframe": "5", "poll_interval_seconds": 60}]',
    },
    # Indicators config
    {
        "key": "adx_threshold",
        "value_type": ValueType.FLOAT,
        "value": 20.0,
        "default_value": "20.0",
    },
    {
        "key": "rsi_overbought",
        "value_type": ValueType.FLOAT,
        "value": 70.0,
        "default_value": "70.0",
    },
    {
        "key": "rsi_oversold",
        "value_type": ValueType.FLOAT,
        "value": 30.0,
        "default_value": "30.0",
    },
    # System config
    {
        "key": "sqlite_path",
        "value_type": ValueType.STRING,
        "value": "./data/cache.db",
        "default_value": "./data/cache.db",
    },
    {
        "key": "backtest.enabled",
        "value_type": ValueType.BOOL,
        "value": False,
        "default_value": "false",
    },
    {
        "key": "backtest.lookback_bars",
        "value_type": ValueType.INT,
        "value": 1500,
        "default_value": "1500",
    },
]


async def seed_settings(session: AsyncSession) -> None:
    """Seed initial global settings."""
    for setting_data in DEFAULT_SETTINGS:
        # Check if setting already exists
        stmt = select(Setting).where(
            Setting.key == setting_data["key"],
            Setting.user_id.is_(None),  # Global setting
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Setting '{setting_data['key']}' already exists, skipping...")
            continue

        # Create new setting
        setting = Setting(
            id=uuid.uuid4(),
            key=setting_data["key"],
            value_type=setting_data["value_type"],
            default_value=setting_data["default_value"],
            user_id=None,  # Global setting
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Set the value in the appropriate column
        setting.set_value(setting_data["value"])

        session.add(setting)
        print(f"Created setting: {setting_data['key']}")

    await session.commit()
    print("Settings seeding completed!")


async def main():
    """Run the seed script."""
    print("Starting settings seed...")

    async with async_session_maker() as session:
        await seed_settings(session)

    print("Seed script completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())