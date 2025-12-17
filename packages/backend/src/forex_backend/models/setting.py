"""Settings models for configuration management."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forex_backend.db.database import Base


class ValueType(enum.Enum):
    """Enum for setting value types."""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    JSON = "json"


class Setting(Base):
    """
    Setting model for hybrid configuration storage.

    Supports both global settings (user_id is NULL) and user-specific overrides.
    """

    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    value_type: Mapped[ValueType] = mapped_column(
        Enum(ValueType),
        nullable=False,
    )

    # Type-specific value columns (only one should be populated)
    string_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    int_value: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    float_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    bool_value: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    json_value: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Default value stored as string
    default_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # User association (NULL = global setting)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Version for optimistic locking
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="settings",
    )
    history: Mapped[list["SettingHistory"]] = relationship(
        "SettingHistory",
        back_populates="setting",
        cascade="all, delete-orphan",
    )

    # Composite unique index: (key, user_id)
    __table_args__ = (
        Index("ix_settings_key_user", "key", "user_id", unique=True),
    )

    def get_value(self):
        """Get the actual value based on value_type."""
        if self.value_type == ValueType.STRING:
            return self.string_value
        elif self.value_type == ValueType.INT:
            return self.int_value
        elif self.value_type == ValueType.FLOAT:
            return self.float_value
        elif self.value_type == ValueType.BOOL:
            return self.bool_value
        elif self.value_type == ValueType.JSON:
            return self.json_value
        return None

    def set_value(self, value):
        """Set the value in the appropriate column based on value_type."""
        # Clear all value columns first
        self.string_value = None
        self.int_value = None
        self.float_value = None
        self.bool_value = None
        self.json_value = None

        # Set the appropriate column
        if self.value_type == ValueType.STRING:
            self.string_value = str(value)
        elif self.value_type == ValueType.INT:
            self.int_value = int(value)
        elif self.value_type == ValueType.FLOAT:
            self.float_value = float(value)
        elif self.value_type == ValueType.BOOL:
            self.bool_value = bool(value)
        elif self.value_type == ValueType.JSON:
            self.json_value = value

    def __repr__(self) -> str:
        return f"<Setting(key={self.key}, user_id={self.user_id})>"


class SettingHistory(Base):
    """Audit log for all setting changes."""

    __tablename__ = "setting_history"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    setting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("settings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    new_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships
    setting: Mapped["Setting"] = relationship(
        "Setting",
        back_populates="history",
    )

    def __repr__(self) -> str:
        return f"<SettingHistory(setting_id={self.setting_id}, changed_at={self.changed_at})>"