"""
Redis publisher for sending status, signals, and metrics to Dashboard.

Publishes to channels:
- forex:status  - Agent status updates
- forex:signals - Trading signals
- forex:metrics - Performance metrics
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from .message_types import (
    RedisChannels,
    StatusMessage,
    StatusPayload,
    SignalMessage,
    SignalPayload,
    MetricsMessage,
    MetricsPayload,
    ProbabilitySignalMessage,
    ProbabilitySignalPayload,
    OutgoingMessage,
)
from .redis_client import RedisConnectionManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RedisPublisher:
    """
    Async publisher for sending messages from Agent to Dashboard.

    Features:
    - Non-blocking message queue
    - Background publisher task
    - Automatic status storage in Redis key
    - Signal history in Redis list
    """

    # TTL for status key in Redis (5 minutes)
    STATUS_TTL_SECONDS = 300

    # Maximum signals to keep in history
    MAX_SIGNALS_HISTORY = 100

    def __init__(self, redis_manager: RedisConnectionManager):
        """
        Initialize Redis publisher.

        Args:
            redis_manager: Redis connection manager instance
        """
        self._redis = redis_manager
        self._queue: asyncio.Queue[OutgoingMessage] = asyncio.Queue()
        self._running = False
        self._publisher_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start background publisher task."""
        if self._running:
            return

        self._running = True
        self._publisher_task = asyncio.create_task(self._publisher_loop())
        logger.info("Redis publisher started", extra={"event_type": "publisher_started"})

    async def stop(self) -> None:
        """Stop publisher and flush remaining messages."""
        self._running = False

        # Process remaining messages in queue
        while not self._queue.empty():
            try:
                msg = self._queue.get_nowait()
                await self._publish_message(msg)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.warning(f"Error flushing message: {e}")

        if self._publisher_task:
            self._publisher_task.cancel()
            try:
                await self._publisher_task
            except asyncio.CancelledError:
                pass

        logger.info("Redis publisher stopped", extra={"event_type": "publisher_stopped"})

    async def publish_status(self, payload: StatusPayload) -> None:
        """
        Publish agent status update.

        Also stores the status in a Redis key with TTL for Dashboard polling.

        Args:
            payload: Status payload
        """
        message = StatusMessage(payload=payload)
        await self._queue.put(message)

        # Also store in Redis key for polling access
        try:
            await self._redis.set_with_expiry(
                RedisChannels.LAST_STATUS,
                message.model_dump_json(),
                self.STATUS_TTL_SECONDS
            )
        except Exception as e:
            logger.warning(f"Failed to store status in Redis key: {e}")

    async def publish_signal(self, payload: SignalPayload) -> None:
        """
        Publish trading signal.

        Also stores in Redis list for signal history.

        Args:
            payload: Signal payload
        """
        message = SignalMessage(payload=payload)
        await self._queue.put(message)

        # Also store in Redis list for history
        try:
            await self._redis.lpush_with_trim(
                RedisChannels.SIGNALS_LIST,
                message.model_dump_json(),
                self.MAX_SIGNALS_HISTORY
            )
        except Exception as e:
            logger.warning(f"Failed to store signal in Redis list: {e}")

    async def publish_metrics(self, payload: MetricsPayload) -> None:
        """
        Publish performance metrics.

        Args:
            payload: Metrics payload
        """
        message = MetricsMessage(payload=payload)
        await self._queue.put(message)

    async def publish_probability_signal(self, payload: ProbabilitySignalPayload) -> None:
        """
        Publish probability-based trading signal.

        Also stores in Redis list for signal history.

        Args:
            payload: Probability signal payload
        """
        message = ProbabilitySignalMessage(payload=payload)
        await self._queue.put(message)

        # Also store in Redis list for history
        try:
            await self._redis.lpush_with_trim(
                RedisChannels.SIGNALS_LIST,
                message.model_dump_json(),
                self.MAX_SIGNALS_HISTORY
            )
        except Exception as e:
            logger.warning(f"Failed to store probability signal in Redis list: {e}")

    async def _publisher_loop(self) -> None:
        """Background loop for publishing messages from queue."""
        while self._running:
            try:
                # Wait for message with timeout to allow checking _running flag
                try:
                    message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                await self._publish_message(message)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publisher loop: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    async def _publish_message(self, message: OutgoingMessage) -> None:
        """
        Publish a single message to appropriate channel.

        Args:
            message: Message to publish
        """
        channel = self._get_channel_for_message(message)
        if not channel:
            logger.warning(f"Unknown message type: {message.type}")
            return

        try:
            json_data = message.model_dump_json()
            subscribers = await self._redis.publish(channel, json_data)

            logger.debug(
                f"Published {message.type} to {channel}, {subscribers} subscribers",
                extra={
                    "event_type": "message_published",
                    "channel": channel,
                    "message_type": message.type,
                    "subscribers": subscribers
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to publish {message.type} to {channel}: {e}",
                extra={"event_type": "publish_error", "channel": channel}
            )
            # Re-queue message for retry (with limit to avoid infinite loop)
            if self._queue.qsize() < 1000:
                await self._queue.put(message)

    @staticmethod
    def _get_channel_for_message(message: OutgoingMessage) -> Optional[str]:
        """
        Get Redis channel for message type.

        Args:
            message: Message to get channel for

        Returns:
            Channel name or None if unknown
        """
        if isinstance(message, StatusMessage):
            return RedisChannels.STATUS
        elif isinstance(message, SignalMessage):
            return RedisChannels.SIGNALS
        elif isinstance(message, ProbabilitySignalMessage):
            return RedisChannels.SIGNALS
        elif isinstance(message, MetricsMessage):
            return RedisChannels.METRICS
        return None


# =============================================================================
# Helper functions for creating payloads
# =============================================================================

def create_status_payload(
    state: str,
    uptime_seconds: float,
    last_cycle_at: Optional[str] = None,
    error_count: int = 0,
    pairs_count: int = 0,
    timeframes_count: int = 0,
    version: str = "0.1.0"
) -> StatusPayload:
    """
    Create status payload with common fields.

    Args:
        state: Agent state (running, paused, error, starting, stopping)
        uptime_seconds: Time since agent start
        last_cycle_at: ISO timestamp of last cycle
        error_count: Number of errors since start
        pairs_count: Number of active pairs
        timeframes_count: Number of active timeframes
        version: Agent version

    Returns:
        StatusPayload instance
    """
    from datetime import datetime

    last_cycle = None
    if last_cycle_at:
        try:
            last_cycle = datetime.fromisoformat(last_cycle_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    return StatusPayload(
        state=state,  # type: ignore
        uptime_seconds=uptime_seconds,
        last_cycle_at=last_cycle,
        error_count=error_count,
        pairs_count=pairs_count,
        timeframes_count=timeframes_count,
        version=version
    )


def create_signal_payload(
    symbol: str,
    timeframe: str,
    kind: str,
    message: str,
    importance: int = 1,
    price: Optional[float] = None,
    rsi: Optional[float] = None,
    macd: Optional[float] = None,
    adx: Optional[float] = None
) -> SignalPayload:
    """
    Create signal payload from event data.

    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (e.g., "5", "15", "1h")
        kind: Signal type (e.g., "macd_bull", "trend_up")
        message: Human-readable signal message
        importance: Signal importance (1=normal, 2=critical)
        price: Current price (optional)
        rsi: RSI value (optional)
        macd: MACD value (optional)
        adx: ADX value (optional)

    Returns:
        SignalPayload instance
    """
    from .message_types import IndicatorsPayload

    indicators = None
    if any([rsi, macd, adx]):
        indicators = IndicatorsPayload(rsi=rsi, macd=macd, adx=adx)

    return SignalPayload(
        symbol=symbol,
        timeframe=timeframe,
        kind=kind,
        message=message,
        importance=importance,
        price=price,
        indicators=indicators
    )


def create_metrics_payload(
    pairs_processed: int,
    cycle_duration_ms: float,
    signals_generated: int = 0,
    signals_sent: int = 0,
    errors_in_cycle: int = 0,
    active_pairs: Optional[list] = None,
    active_timeframes: Optional[list] = None
) -> MetricsPayload:
    """
    Create metrics payload from cycle data.

    Args:
        pairs_processed: Number of pairs processed in cycle
        cycle_duration_ms: Cycle duration in milliseconds
        signals_generated: Number of signals generated
        signals_sent: Number of signals actually sent (after cooldown)
        errors_in_cycle: Number of errors in cycle
        active_pairs: List of active pair symbols
        active_timeframes: List of active timeframes

    Returns:
        MetricsPayload instance
    """
    return MetricsPayload(
        pairs_processed=pairs_processed,
        cycle_duration_ms=cycle_duration_ms,
        signals_generated=signals_generated,
        signals_sent=signals_sent,
        errors_in_cycle=errors_in_cycle,
        active_pairs=active_pairs or [],
        active_timeframes=active_timeframes or []
    )


def create_probability_signal_payload(
    symbol: str,
    timeframe: str,
    direction: str,
    probabilities: dict[str, float],
    confidence: float,
    is_actionable: bool,
    importance: int = 1,
    factors: Optional[dict[str, float]] = None,
    volatility_regime: Optional[str] = None,
    atr_percent: Optional[float] = None
) -> ProbabilitySignalPayload:
    """
    Create probability signal payload from analysis results.

    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (e.g., "1d", "4h")
        direction: Predicted direction ("upward", "downward", "consolidation")
        probabilities: Dict of probabilities for each direction
        confidence: Overall confidence score (0-1)
        is_actionable: Whether the signal is actionable
        importance: Signal importance (1=normal, 2=high confidence)
        factors: Dict of factor contributions (optional)
        volatility_regime: Current volatility regime (optional)
        atr_percent: ATR as percentage of price (optional)

    Returns:
        ProbabilitySignalPayload instance
    """
    return ProbabilitySignalPayload(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        probabilities=probabilities,
        confidence=confidence,
        is_actionable=is_actionable,
        importance=importance,
        factors=factors or {},
        volatility_regime=volatility_regime,
        atr_percent=atr_percent
    )