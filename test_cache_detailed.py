#!/usr/bin/env python3
"""Detailed cache functionality test to diagnose the cooldown issue"""

import asyncio
import time
from src.forex_signal_agent.sqlite_cache import Cache

async def test_cache_detailed():
    # Use the same path as in your config
    db_path = "./data/cache.db"
    
    print(f"Testing cache in detail at: {db_path}")
    
    cache = Cache(db_path)
    
    # Initialize the cache
    await cache.init()
    
    # Test 1: Basic set and get
    print("\n--- Test 1: Basic set/get ---")
    symbol, timeframe, kind = "TEST_EUR_USD", "4h", "test_event"
    current_time = int(time.time())
    
    print(f"Setting timestamp {current_time} for {symbol}, {timeframe}, {kind}")
    await cache.set_last_sent(symbol, timeframe, kind, current_time)
    
    retrieved_time = await cache.get_last_sent(symbol, timeframe, kind)
    print(f"Retrieved timestamp: {retrieved_time}")
    
    if retrieved_time == current_time:
        print("✓ Basic set/get test PASSED")
    else:
        print("✗ Basic set/get test FAILED")
        return False
    
    # Test 2: Update timestamp (simulate cooldown)
    print("\n--- Test 2: Update timestamp ---")
    new_time = current_time + 300  # 5 minutes later
    
    print(f"Updating to timestamp {new_time} for {symbol}, {timeframe}, {kind}")
    await cache.set_last_sent(symbol, timeframe, kind, new_time)
    
    updated_time = await cache.get_last_sent(symbol, timeframe, kind)
    print(f"Retrieved updated timestamp: {updated_time}")
    
    if updated_time == new_time:
        print("✓ Update timestamp test PASSED")
    else:
        print("✗ Update timestamp test FAILED")
        return False

    # Test 3: Multiple events, same symbol/timeframe, different kinds
    print("\n--- Test 3: Multiple event types ---")
    kinds = ["trend_up", "rsi_overbought", "macd_bull"]
    base_time = int(time.time())
    
    for i, k in enumerate(kinds):
        event_time = base_time + i * 60  # Different times
        print(f"Setting {k} with timestamp {event_time}")
        await cache.set_last_sent(symbol, timeframe, k, event_time)
    
    # Verify all were set correctly
    for i, k in enumerate(kinds):
        event_time = base_time + i * 60
        retrieved = await cache.get_last_sent(symbol, timeframe, k)
        print(f"Retrieved {k}: {retrieved} (expected {event_time})")
        if retrieved != event_time:
            print(f"✗ Multiple event types test FAILED for {k}")
            return False
    
    print("✓ Multiple event types test PASSED")
    
    # Test 4: Same event, different symbols
    print("\n--- Test 4: Same event, different symbols ---")
    symbols = ["EUR_USD", "GBP_USD", "USD_JPY"]
    event_kind = "trend_up"
    current_time = int(time.time()) + 1000
    
    for sym in symbols:
        print(f"Setting {event_kind} for {sym} with timestamp {current_time}")
        await cache.set_last_sent(sym, timeframe, event_kind, current_time)
    
    # Verify all were set correctly
    for sym in symbols:
        retrieved = await cache.get_last_sent(sym, timeframe, event_kind)
        print(f"Retrieved {event_kind} for {sym}: {retrieved} (expected {current_time})")
        if retrieved != current_time:
            print(f"✗ Different symbols test FAILED for {sym}")
            return False
    
    print("✓ Different symbols test PASSED")
    
    print("\n--- All tests completed successfully! ---")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_cache_detailed())
    if success:
        print("\n✓ All cache functionality tests PASSED")
    else:
        print("\n✗ Some cache functionality tests FAILED")