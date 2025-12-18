#!/usr/bin/env python3
"""Test script to check cache database initialization"""

import asyncio
import os
import tempfile
import pytest
from forex_signal_agent.sqlite_cache import Cache


@pytest.mark.asyncio
async def test_cache():
    """Test cache initialization and basic operations."""
    # Use a temp file for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        cache = Cache(db_path)
        await cache.init()

        # Check if tables were created by attempting to use the cache
        result = await cache.get_meta("test_key")
        assert result is None  # Should be None initially

        # Set a test value
        await cache.set_meta("test_key", "test_value")

        # Get it back
        result = await cache.get_meta("test_key")
        assert result == "test_value"

    finally:
        # Clean up temp file
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    asyncio.run(test_cache())
