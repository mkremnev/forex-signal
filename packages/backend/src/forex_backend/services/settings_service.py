"""Service layer for settings management."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forex_backend.models.setting import Setting, SettingHistory, ValueType
from forex_backend.schemas.settings import AppConfigSchema


class SettingsService:
    """Service for managing application settings."""

    def __init__(self, db: AsyncSession):
        """
        Initialize settings service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_merged_settings(
        self, user_id: UUID | None = None
    ) -> dict[str, Any]:
        """
        Get merged settings (global + user overrides).

        User-specific settings override global settings.

        Args:
            user_id: Optional user ID for user-specific settings

        Returns:
            Dictionary of merged settings
        """
        # Get global settings
        global_stmt = select(Setting).where(Setting.user_id.is_(None))
        global_result = await self.db.execute(global_stmt)
        global_settings = global_result.scalars().all()

        # Create settings dictionary from global settings
        settings_dict = {s.key: s.get_value() for s in global_settings}

        # If user_id provided, override with user-specific settings
        if user_id:
            user_stmt = select(Setting).where(Setting.user_id == user_id)
            user_result = await self.db.execute(user_stmt)
            user_settings = user_result.scalars().all()

            # Override global settings with user settings
            for setting in user_settings:
                settings_dict[setting.key] = setting.get_value()

        return settings_dict

    async def get_setting(
        self, key: str, user_id: UUID | None = None
    ) -> Setting | None:
        """
        Get a specific setting.

        Checks user-specific setting first, then falls back to global.

        Args:
            key: Setting key
            user_id: Optional user ID

        Returns:
            Setting or None if not found
        """
        # Try user-specific setting first
        if user_id:
            user_stmt = select(Setting).where(
                Setting.key == key, Setting.user_id == user_id
            )
            user_result = await self.db.execute(user_stmt)
            user_setting = user_result.scalar_one_or_none()

            if user_setting:
                return user_setting

        # Fall back to global setting
        global_stmt = select(Setting).where(
            Setting.key == key, Setting.user_id.is_(None)
        )
        global_result = await self.db.execute(global_stmt)
        return global_result.scalar_one_or_none()

    async def update_setting(
        self, key: str, value: Any, user_id: UUID | None = None
    ) -> Setting:
        """
        Update or create a setting.

        Args:
            key: Setting key
            value: New value
            user_id: Optional user ID for user-specific setting

        Returns:
            Updated or created setting
        """
        # Get existing setting
        stmt = select(Setting).where(Setting.key == key, Setting.user_id == user_id)
        result = await self.db.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            # Update existing setting
            old_value = str(setting.get_value())
            setting.set_value(value)
            setting.version += 1
            setting.updated_at = datetime.utcnow()

            # Create history entry
            history = SettingHistory(
                id=uuid4(),
                setting_id=setting.id,
                old_value=old_value,
                new_value=str(value),
                changed_by=user_id,
                changed_at=datetime.utcnow(),
            )
            self.db.add(history)
        else:
            # Create new setting
            # Infer value type
            value_type = self._infer_value_type(value)

            setting = Setting(
                id=uuid4(),
                key=key,
                value_type=value_type,
                default_value=str(value),
                user_id=user_id,
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            setting.set_value(value)
            self.db.add(setting)

        await self.db.commit()
        await self.db.refresh(setting)

        return setting

    async def delete_setting(
        self, key: str, user_id: UUID | None = None
    ) -> bool:
        """
        Delete a user-specific setting (revert to global).

        Args:
            key: Setting key
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        if user_id is None:
            # Cannot delete global settings
            return False

        stmt = select(Setting).where(Setting.key == key, Setting.user_id == user_id)
        result = await self.db.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            await self.db.delete(setting)
            await self.db.commit()
            return True

        return False

    async def bulk_update(
        self, updates: dict[str, Any], user_id: UUID | None = None
    ) -> dict[str, Setting]:
        """
        Bulk update multiple settings.

        Args:
            updates: Dictionary of setting keys and values
            user_id: Optional user ID

        Returns:
            Dictionary of updated settings
        """
        result = {}

        for key, value in updates.items():
            setting = await self.update_setting(key, value, user_id)
            result[key] = setting

        return result

    async def get_app_config(self, user_id: UUID | None = None) -> AppConfigSchema:
        """
        Get application configuration in AppConfig format.

        Args:
            user_id: Optional user ID

        Returns:
            Application configuration schema
        """
        settings = await self.get_merged_settings(user_id)

        # Build config dict from flat settings
        config_dict = {
            "timezone": settings.get("timezone", "Europe/Moscow"),
            "pairs": settings.get("pairs", ["EUR_USD", "GBP_USD", "USD_JPY"]),
            "notify_hourly_summary": settings.get("notify_hourly_summary", True),
            "timeframes": settings.get(
                "timeframes", [{"timeframe": "5", "poll_interval_seconds": 60}]
            ),
            "telegram": {
                "bot_token": settings.get("telegram.bot_token", ""),
                "chat_id": settings.get("telegram.chat_id", ""),
                "message_cooldown_minutes": settings.get(
                    "telegram.message_cooldown_minutes", 60
                ),
            },
            "adx_threshold": settings.get("adx_threshold", 20.0),
            "rsi_overbought": settings.get("rsi_overbought", 70.0),
            "rsi_oversold": settings.get("rsi_oversold", 30.0),
            "sqlite_path": settings.get("sqlite_path", "./data/cache.db"),
            "backtest": {
                "enabled": settings.get("backtest.enabled", False),
                "lookback_bars": settings.get("backtest.lookback_bars", 1500),
            },
        }

        return AppConfigSchema(**config_dict)

    async def get_history(
        self, key: str, user_id: UUID | None = None, limit: int = 100
    ) -> list[SettingHistory]:
        """
        Get change history for a setting.

        Args:
            key: Setting key
            user_id: Optional user ID
            limit: Maximum number of history entries

        Returns:
            List of history entries
        """
        # Get setting
        setting = await self.get_setting(key, user_id)
        if not setting:
            return []

        # Get history
        stmt = (
            select(SettingHistory)
            .where(SettingHistory.setting_id == setting.id)
            .order_by(SettingHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def _infer_value_type(self, value: Any) -> ValueType:
        """
        Infer the ValueType from a Python value.

        Args:
            value: Python value

        Returns:
            Corresponding ValueType
        """
        if isinstance(value, bool):
            return ValueType.BOOL
        elif isinstance(value, int):
            return ValueType.INT
        elif isinstance(value, float):
            return ValueType.FLOAT
        elif isinstance(value, (list, dict)):
            return ValueType.JSON
        else:
            return ValueType.STRING