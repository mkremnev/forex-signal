#!/usr/bin/env python3
"""Test script to check cache database initialization"""

import asyncio
import os
from src.forex_signal_agent.sqlite_cache import Cache

async def test_cache():
    # Use the same path as in config.yaml
    db_path = "./data/cache.db"
    
    print(f"Testing cache initialization at: {db_path}")
    print(f"Directory exists: {os.path.exists(os.path.dirname(db_path))}")
    print(f"File exists before init: {os.path.exists(db_path)}")
    
    cache = Cache(db_path)
    
    try:
        await cache.init()
        print("Cache initialization successful!")
        
        # Check if tables were created by attempting to use the cache
        result = await cache.get_meta("test_key")
        print(f"Test query successful, returned: {result}")
        
        # Set a test value
        await cache.set_meta("test_key", "test_value")
        print("Test value set successfully")
        
        # Get it back
        result = await cache.get_meta("test_key")
        print(f"Retrieved value: {result}")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"Error during cache operations: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cache())