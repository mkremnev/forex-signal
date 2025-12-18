#!/usr/bin/env python3
"""Test script to check full application initialization"""

import asyncio
import os
import pytest
from forex_signal_agent.main import Application


@pytest.mark.asyncio
async def test_app_init():
    """Test application initialization with config file."""
    config_path = "config.yaml"

    # Skip if config file doesn't exist
    if not os.path.exists(config_path):
        pytest.skip("config.yaml not found")

    app = Application(config_path)

    try:
        await app.initialize()

        # Check if cache tables were created by querying them
        result = await app.cache.get_meta("test_key")

        # Set a test value
        await app.cache.set_meta("test_key", "app_test_value")

        # Get it back
        result = await app.cache.get_meta("test_key")
        assert result == "app_test_value"

    finally:
        if app.cache:
            await app.cleanup()


if __name__ == "__main__":
    asyncio.run(test_app_init())
