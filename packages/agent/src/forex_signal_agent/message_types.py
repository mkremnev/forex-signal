"""
Pydantic models for Redis Pub/Sub messages between Agent and Dashboard.

Channels:
- forex:commands  - Dashboard -> Agent (commands: reload, pause, resume, status)
- forex:config    - Dashboard -> Agent (configuration updates)
- forex:status    - Agent -> Dashboard (agent status)
- forex:signals   - Agent -> Dashboard (trading signals)
- forex:metrics   - Agent -> Dashboard (performance metrics)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _generate_correlation_id() -> str:
    """Generate unique correlation ID for message tracing."""
    return str(uuid.uuid4())


# =============================================================================
# Base Message
# =============================================================================

class BaseMessage(BaseModel):
    """Base class for all Redis Pub/Sub messages."""
    type: str
    timestamp: datetime = Field(default_factory=_utc_now)
    correlation_id: str = Field(default_factory=_generate_correlation_id)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# =============================================================================
# Dashboard -> Agent: Commands
# =============================================================================

class CommandPayload(BaseModel):
    """Payload for command messages."""
    action: Literal["reload", "pause", "resume", "status"]
    params: Dict[str, Any] = Field(default_factory=dict)


class CommandMessage(BaseMessage):
    """Command message from Dashboard to Agent."""
    type: Literal["command"] = "command"
    payload: CommandPayload


# =============================================================================
# Dashboard -> Agent: Configuration Updates
# =============================================================================

class TelegramConfigPayload(BaseModel):
    """Telegram configuration subset for updates."""
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    message_cooldown_minutes: Optional[int] = None


class TimeframeConfigPayload(BaseModel):
    """Timeframe configuration for updates."""
    timeframe: str
    poll_interval_seconds: int = 60


class ConfigUpdatePayload(BaseModel):
    """Payload for configuration update messages."""
    pairs: Optional[List[str]] = None
    timeframes: Optional[List[TimeframeConfigPayload]] = None
    telegram: Optional[TelegramConfigPayload] = None
    notify_hourly_summary: Optional[bool] = None


class ConfigUpdateMessage(BaseMessage):
    """Configuration update message from Dashboard to Agent."""
    type: Literal["config_update"] = "config_update"
    payload: ConfigUpdatePayload


# =============================================================================
# Agent -> Dashboard: Status
# =============================================================================

class StatusPayload(BaseModel):
    """Payload for agent status messages."""
    state: Literal["running", "paused", "error", "starting", "stopping"]
    uptime_seconds: float
    last_cycle_at: Optional[datetime] = None
    error_count: int = 0
    version: str = "0.1.0"
    pairs_count: int = 0
    timeframes_count: int = 0


class StatusMessage(BaseMessage):
    """Status message from Agent to Dashboard."""
    type: Literal["status"] = "status"
    payload: StatusPayload


# =============================================================================
# Agent -> Dashboard: Trading Signals
# =============================================================================

class IndicatorsPayload(BaseModel):
    """Technical indicators values."""
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    adx: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None


class SignalPayload(BaseModel):
    """Payload for trading signal messages."""
    symbol: str
    timeframe: str
    kind: str  # e.g., "macd_bull", "trend_up", "rsi_overbought", etc.
    message: str
    importance: int = 1  # 1 = normal, 2 = critical
    indicators: Optional[IndicatorsPayload] = None
    price: Optional[float] = None


class SignalMessage(BaseMessage):
    """Trading signal message from Agent to Dashboard."""
    type: Literal["signal"] = "signal"
    payload: SignalPayload


# =============================================================================
# Agent -> Dashboard: Probability Signals
# =============================================================================

class ProbabilitySignalPayload(BaseModel):
    """Payload for probability-based trading signals."""
    symbol: str
    timeframe: str
    direction: str  # "upward", "downward", "consolidation"
    probabilities: Dict[str, float]  # {"upward": 0.6, "downward": 0.3, "consolidation": 0.1}
    confidence: float
    is_actionable: bool
    importance: int = 1  # 1 = normal, 2 = high confidence
    factors: Dict[str, float] = Field(default_factory=dict)
    volatility_regime: Optional[str] = None
    atr_percent: Optional[float] = None
    # Market context fields
    market_sentiment: Optional[str] = None
    market_modifier: Optional[float] = None
    market_reasoning: Optional[str] = None


class ProbabilitySignalMessage(BaseMessage):
    """Probability signal message from Agent to Dashboard."""
    type: Literal["probability_signal"] = "probability_signal"
    payload: ProbabilitySignalPayload


# =============================================================================
# Agent -> Dashboard: Market Sentiment
# =============================================================================

class MarketSentimentPayload(BaseModel):
    """Payload for market sentiment updates."""
    risk_sentiment: str  # "risk_on", "risk_off", "neutral"
    confidence: float
    dominant_factor: str
    btc_roc_24h: float = 0.0
    eth_roc_24h: float = 0.0
    gold_roc_24h: float = 0.0
    volatility_regime: str = "normal"
    summary: str
    timestamp: datetime = Field(default_factory=_utc_now)


class MarketSentimentMessage(BaseMessage):
    """Market sentiment message from Agent to Dashboard."""
    type: Literal["market_sentiment"] = "market_sentiment"
    payload: MarketSentimentPayload


# =============================================================================
# Agent -> Dashboard: Correlation Matrix
# =============================================================================

class CorrelationMatrixPayload(BaseModel):
    """Payload for correlation matrix updates."""
    symbols: List[str]
    matrix: Dict[str, Dict[str, float]]  # symbol -> {symbol: correlation}
    high_correlations: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


class CorrelationMatrixMessage(BaseMessage):
    """Correlation matrix message from Agent to Dashboard."""
    type: Literal["correlation_matrix"] = "correlation_matrix"
    payload: CorrelationMatrixPayload


# =============================================================================
# Agent -> Dashboard: Metrics
# =============================================================================

class MetricsPayload(BaseModel):
    """Payload for performance metrics messages."""
    pairs_processed: int = 0
    cycle_duration_ms: float = 0.0
    signals_generated: int = 0
    signals_sent: int = 0
    errors_in_cycle: int = 0
    memory_mb: Optional[float] = None
    active_pairs: List[str] = Field(default_factory=list)
    active_timeframes: List[str] = Field(default_factory=list)


class MetricsMessage(BaseMessage):
    """Metrics message from Agent to Dashboard."""
    type: Literal["metrics"] = "metrics"
    payload: MetricsPayload


# =============================================================================
# Message Parsing Utilities
# =============================================================================

# Union type for all incoming messages (Dashboard -> Agent)
IncomingMessage = Union[CommandMessage, ConfigUpdateMessage]

# Union type for all outgoing messages (Agent -> Dashboard)
OutgoingMessage = Union[
    StatusMessage,
    SignalMessage,
    MetricsMessage,
    ProbabilitySignalMessage,
    MarketSentimentMessage,
    CorrelationMatrixMessage,
]


def parse_incoming_message(data: Dict[str, Any]) -> Optional[IncomingMessage]:
    """
    Parse incoming JSON message from Dashboard.

    Args:
        data: Parsed JSON dictionary

    Returns:
        Parsed message object or None if parsing fails
    """
    msg_type = data.get("type")

    try:
        if msg_type == "command":
            return CommandMessage.model_validate(data)
        elif msg_type == "config_update":
            return ConfigUpdateMessage.model_validate(data)
        else:
            return None
    except Exception:
        return None


# =============================================================================
# Redis Channel Constants
# =============================================================================

class RedisChannels:
    """Redis Pub/Sub channel names."""
    COMMANDS = "forex:commands"
    CONFIG = "forex:config"
    STATUS = "forex:status"
    SIGNALS = "forex:signals"
    METRICS = "forex:metrics"

    # Redis keys for storing latest data
    LAST_STATUS = "forex:agent:last_status"
    SIGNALS_LIST = "forex:agent:signals"
    METRICS_SORTED = "forex:agent:metrics"
