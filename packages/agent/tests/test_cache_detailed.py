#!/usr/bin/env python3
"""Detailed cache functionality test for cooldown logic"""

import asyncio
import os
import tempfile
import time
import pytest
import pytest_asyncio
from forex_signal_agent.sqlite_cache import Cache


@pytest_asyncio.fixture
async def cache():
    """Create a temporary cache for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    cache = Cache(db_path)
    await cache.init()
    yield cache

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_basic_set_get(cache):
    """Test basic set and get operations."""
    symbol, timeframe, kind = "TEST_EUR_USD", "4h", "test_event"
    current_time = int(time.time())

    await cache.set_last_sent(symbol, timeframe, kind, current_time)
    retrieved_time = await cache.get_last_sent(symbol, timeframe, kind)

    assert retrieved_time == current_time


@pytest.mark.asyncio
async def test_update_timestamp(cache):
    """Test updating timestamp (simulate cooldown)."""
    symbol, timeframe, kind = "TEST_EUR_USD", "4h", "test_event"
    current_time = int(time.time())

    await cache.set_last_sent(symbol, timeframe, kind, current_time)

    # Update 5 minutes later
    new_time = current_time + 300
    await cache.set_last_sent(symbol, timeframe, kind, new_time)

    updated_time = await cache.get_last_sent(symbol, timeframe, kind)
    assert updated_time == new_time


@pytest.mark.asyncio
async def test_multiple_event_types(cache):
    """Test multiple events with same symbol/timeframe but different kinds."""
    symbol, timeframe = "TEST_EUR_USD", "4h"
    kinds = ["trend_up", "rsi_overbought", "macd_bull"]
    base_time = int(time.time())

    # Set different times for each kind
    for i, k in enumerate(kinds):
        event_time = base_time + i * 60
        await cache.set_last_sent(symbol, timeframe, k, event_time)

    # Verify all were set correctly
    for i, k in enumerate(kinds):
        event_time = base_time + i * 60
        retrieved = await cache.get_last_sent(symbol, timeframe, k)
        assert retrieved == event_time, f"Failed for {k}"


@pytest.mark.asyncio
async def test_same_event_different_symbols(cache):
    """Test same event kind for different symbols."""
    symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
    timeframe = "4h"
    event_kind = "trend_up"
    current_time = int(time.time())

    for sym in symbols:
        await cache.set_last_sent(sym, timeframe, event_kind, current_time)

    # Verify all were set correctly
    for sym in symbols:
        retrieved = await cache.get_last_sent(sym, timeframe, event_kind)
        assert retrieved == current_time, f"Failed for {sym}"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(cache):
    """Test getting non-existent entry returns None."""
    result = await cache.get_last_sent("NONEXISTENT", "1h", "fake_event")
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
