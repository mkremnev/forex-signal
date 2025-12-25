"""Data providers module for market data fetching.

Contains:
- OHLCV: Standard candlestick data structure
- DataProviderProtocol: Unified interface for all providers
- YahooFinanceProvider: Forex and commodities data
- BinanceProvider: Cryptocurrency data via CCXT
- DataManager: Routing and caching layer
"""

from .base import (
    OHLCV,
    BaseDataProvider,
    DataProviderProtocol,
    Instrument,
    InstrumentType,
    Timeframe,
    normalize_timeframe,
    ohlcv_list_to_dataframe,
)
from .binance_client import BinanceProvider
from .data_manager import DataManager, create_instruments_from_config
from .yahoo_client import YahooFinanceProvider

__all__ = [
    # Base types
    "OHLCV",
    "Instrument",
    "InstrumentType",
    "Timeframe",
    # Protocols and base classes
    "DataProviderProtocol",
    "BaseDataProvider",
    # Providers
    "YahooFinanceProvider",
    "BinanceProvider",
    # Manager
    "DataManager",
    # Utilities
    "normalize_timeframe",
    "ohlcv_list_to_dataframe",
    "create_instruments_from_config",
]
