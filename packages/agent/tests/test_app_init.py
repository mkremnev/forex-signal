#!/usr/bin/env python3
"""Test script to check full application initialization"""

import asyncio
import os
from src.forex_signal_agent.main import Application

async def test_app_init():
    config_path = "config.yaml"
    
    print(f"Testing application initialization with config: {config_path}")
    print(f"Config file exists: {os.path.exists(config_path)}")
    
    app = Application(config_path)
    
    try:
        await app.initialize()
        print("Application initialization successful!")
        
        # Check if cache tables were created by querying them
        result = await app.cache.get_meta("test_key")
        print(f"Cache query successful, returned: {result}")
        
        # Set a test value
        await app.cache.set_meta("test_key", "app_test_value")
        print("Test value set successfully via app")
        
        # Get it back
        result = await app.cache.get_meta("test_key")
        print(f"Retrieved value via app: {result}")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"Error during application initialization: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if app.cache:
            await app.cleanup()

if __name__ == "__main__":
    asyncio.run(test_app_init())