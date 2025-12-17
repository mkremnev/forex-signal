"""Settings API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from forex_backend.core.dependencies import get_current_user, get_optional_current_user
from forex_backend.db.database import get_db
from forex_backend.models.user import User
from forex_backend.schemas.settings import (
    AppConfigSchema,
    BulkUpdateRequest,
    SettingHistoryRead,
    SettingRead,
    SettingUpdate,
)
from forex_backend.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=dict[str, Any])
async def get_all_settings(
    user_id: UUID | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all settings (merged: global + user overrides).

    Args:
        user_id: Optional current user ID
        db: Database session

    Returns:
        Dictionary of all settings
    """
    service = SettingsService(db)
    return await service.get_merged_settings(user_id)


@router.get("/config", response_model=AppConfigSchema)
async def get_app_config(
    user_id: UUID | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get application configuration in AppConfig format.

    This endpoint returns the full configuration needed by the agent.

    Args:
        user_id: Optional current user ID
        db: Database session

    Returns:
        Application configuration
    """
    service = SettingsService(db)
    return await service.get_app_config(user_id)


@router.get("/{key}", response_model=dict[str, Any])
async def get_setting(
    key: str,
    user_id: UUID | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific setting by key.

    Args:
        key: Setting key
        user_id: Optional current user ID
        db: Database session

    Returns:
        Setting value

    Raises:
        HTTPException: If setting not found
    """
    service = SettingsService(db)
    setting = await service.get_setting(key, user_id)

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return {"key": key, "value": setting.get_value()}


@router.put("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    update_data: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a specific setting.

    Creates a user-specific override if it doesn't exist.

    Args:
        key: Setting key
        update_data: New value
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated setting
    """
    service = SettingsService(db)

    try:
        setting = await service.update_setting(key, update_data.value, current_user.id)
        return SettingRead(
            id=setting.id,
            key=setting.key,
            value=setting.get_value(),
            value_type=setting.value_type,
            is_user_override=setting.user_id is not None,
            version=setting.version,
            created_at=setting.created_at,
            updated_at=setting.updated_at,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting_override(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user-specific setting override (revert to global).

    Args:
        key: Setting key
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If setting override not found
    """
    service = SettingsService(db)
    deleted = await service.delete_setting(key, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User override for setting '{key}' not found",
        )


@router.post("/bulk-update", response_model=dict[str, Any])
async def bulk_update_settings(
    bulk_data: BulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk update multiple settings.

    Args:
        bulk_data: Dictionary of setting keys and values
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dictionary of updated settings
    """
    service = SettingsService(db)

    try:
        result = await service.bulk_update(bulk_data.updates, current_user.id)
        return {
            key: {
                "id": str(setting.id),
                "value": setting.get_value(),
                "version": setting.version,
            }
            for key, setting in result.items()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{key}/history", response_model=list[SettingHistoryRead])
async def get_setting_history(
    key: str,
    limit: int = 100,
    user_id: UUID | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get change history for a setting.

    Args:
        key: Setting key
        limit: Maximum number of history entries (default: 100)
        user_id: Optional current user ID
        db: Database session

    Returns:
        List of history entries

    Raises:
        HTTPException: If setting not found
    """
    service = SettingsService(db)
    history = await service.get_history(key, user_id, limit)

    if not history:
        # Check if setting exists
        setting = await service.get_setting(key, user_id)
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting '{key}' not found",
            )

    return history


@router.post("/{key}/reset", response_model=dict[str, Any])
async def reset_setting_to_default(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reset a setting to its default value.

    For user overrides, this deletes the override.
    For global settings, this resets to the default_value.

    Args:
        key: Setting key
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If setting not found
    """
    service = SettingsService(db)

    # Delete user override if exists
    deleted = await service.delete_setting(key, current_user.id)

    if deleted:
        return {"message": f"User override for '{key}' deleted, reverted to global"}

    # If no user override, get global setting
    setting = await service.get_setting(key, None)

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return {"message": f"Setting '{key}' already at default value"}