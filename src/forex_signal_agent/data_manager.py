"""Data management module for optimizing data fetching operations."""

from typing import Dict, Tuple, Optional, List
import asyncio
import logging
import pandas as pd
from datetime import datetime, timezone
from .yahoo_finance_client import YahooFinanceClient, fetch_candles
from .exceptions import DataProviderException


logger = logging.getLogger(__name__)


class DataFetchManager:
    """Manages data fetching with caching to reduce redundant API calls."""
    
    def __init__(self, cache_ttl: int = 60):
        self.cache: Dict[Tuple[str, str], Tuple[pd.DataFrame, datetime]] = {}
        self.cache_lock = asyncio.Lock()
        self.cache_ttl = cache_ttl  # seconds

    async def get_candles(
        self, 
        client: YahooFinanceClient, 
        symbol: str, 
        timeframe: str, 
        bars: int = 600
    ) -> pd.DataFrame:
        """Get candles with caching to avoid redundant API calls."""
        cache_key = (symbol, timeframe)
        
        async with self.cache_lock:
            # Check if we have cached data that's still valid
            if cache_key in self.cache:
                df, timestamp = self.cache[cache_key]
                if (datetime.now(tz=timezone.utc) - timestamp).total_seconds() < self.cache_ttl:
                    return df
            
            # Fetch new data
            df = await fetch_candles(client, symbol, timeframe, bars)
            self.cache[cache_key] = (df, datetime.now(tz=timezone.utc))
            return df


async def batch_fetch_candles(
    client: YahooFinanceClient,
    requests: List[Tuple[str, str, int]]  # [(symbol, timeframe, bars), ...]
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """Fetch multiple datasets in parallel with deduplication."""
    # Remove duplicates while preserving order
    seen = set()
    deduplicated_requests = []
    for req in requests:
        if req not in seen:
            seen.add(req)
            deduplicated_requests.append(req)
    
    tasks = [
        fetch_candles(client, symbol, timeframe, bars) 
        for symbol, timeframe, bars in deduplicated_requests
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Map results back to original request list
    result_map = {}
    for i, (symbol, timeframe, _) in enumerate(deduplicated_requests):
        if not isinstance(results[i], Exception):
            result_map[(symbol, timeframe)] = results[i]
        else:
            # Log error and continue with empty DataFrame
            logger.error(f"Error fetching {symbol} {timeframe}: {results[i]}", extra={'event_type': 'data_fetch_error', 'symbol': symbol, 'timeframe': timeframe})
            result_map[(symbol, timeframe)] = pd.DataFrame()
    
    return result_map