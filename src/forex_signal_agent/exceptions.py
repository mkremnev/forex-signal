"""Custom exceptions for the forex signal agent."""

from typing import Optional


class ForexSignalAgentException(Exception):
    """Base exception for all forex signal agent specific exceptions"""
    pass


class DataProviderException(ForexSignalAgentException):
    """Raised when data provider operations fail"""
    pass


class ConfigurationException(ForexSignalAgentException):
    """Raised when configuration is invalid"""
    pass


class CacheException(ForexSignalAgentException):
    """Raised when cache operations fail"""
    pass


class NotificationException(ForexSignalAgentException):
    """Raised when notification operations fail"""
    pass


class AnalysisException(ForexSignalAgentException):
    """Raised when analysis operations fail"""
    pass