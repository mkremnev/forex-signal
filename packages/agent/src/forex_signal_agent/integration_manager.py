"""
Integration manager coordinating Redis Pub/Sub communication with Dashboard.

Responsibilities:
- Initialize and manage Redis connection
- Handle incoming commands and config updates
- Publish status, signals, and metrics
- Manage status heartbeat
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, Any, Dict, List

from .config import RedisConfig, TimeframeJob
from .redis_client import RedisConnectionManager, RedisConnectionError
from .redis_publisher import (
    RedisPublisher,
    create_status_payload,
    create_signal_payload,
    create_metrics_payload,
)
from .redis_subscriber import RedisSubscriber
from .message_types import CommandMessage, ConfigUpdateMessage

if TYPE_CHECKING:
    from .main import Application

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Central coordinator for Redis integration.

    Features:
    - Manages Redis connection lifecycle
    - Routes commands to Application
    - Handles hot-reload of configuration
    - Periodic status heartbeat
    - Publishes signals and metrics
    """

    VERSION = "0.1.0"

    def __init__(self, app: Application, redis_config: RedisConfig):
        """
        Initialize integration manager.

        Args:
            app: Reference to main Application instance
            redis_config: Redis configuration
        """
        self.app = app
        self.config = redis_config

        self._redis_manager = RedisConnectionManager(redis_config)
        self._publisher: Optional[RedisPublisher] = None
        self._subscriber: Optional[RedisSubscriber] = None

        self._start_time = time.time()
        self._error_count = 0
        self._last_cycle_at: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def publisher(self) -> Optional[RedisPublisher]:
        """Get publisher instance."""
        return self._publisher

    async def start(self) -> None:
        """
        Initialize and start all Redis components.

        Connects to Redis, starts publisher, subscriber, and heartbeat.
        """
        if self._running:
            return

        try:
            # Connect to Redis
            await self._redis_manager.connect()

            # Start health monitor
            await self._redis_manager.start_health_monitor(
                interval=self.config.status_interval_seconds
            )

            # Initialize publisher
            self._publisher = RedisPublisher(self._redis_manager)
            await self._publisher.start()

            # Initialize subscriber with handlers
            self._subscriber = RedisSubscriber(
                self._redis_manager,
                command_handler=self._handle_command,
                config_handler=self._handle_config_update
            )
            await self._subscriber.start()

            # Start heartbeat
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._status_heartbeat())

            # Publish initial status
            await self._publish_status("starting")

            logger.info(
                "Integration manager started",
                extra={"event_type": "integration_started"}
            )

        except RedisConnectionError as e:
            logger.error(
                f"Failed to start integration manager: {e}",
                extra={"event_type": "integration_start_error"}
            )
            raise

    async def stop(self) -> None:
        """Stop all Redis components gracefully."""
        self._running = False

        # Publish stopping status
        try:
            await self._publish_status("stopping")
        except Exception:
            pass

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop subscriber
        if self._subscriber:
            await self._subscriber.stop()

        # Stop publisher
        if self._publisher:
            await self._publisher.stop()

        # Disconnect from Redis
        await self._redis_manager.disconnect()

        logger.info(
            "Integration manager stopped",
            extra={"event_type": "integration_stopped"}
        )

    async def _handle_command(self, message: CommandMessage) -> None:
        """
        Handle command from Dashboard.

        Args:
            message: Command message
        """
        action = message.payload.action
        params = message.payload.params

        logger.info(
            f"Handling command: {action}",
            extra={"event_type": "handling_command", "action": action}
        )

        if action == "pause":
            await self._handle_pause()
        elif action == "resume":
            await self._handle_resume()
        elif action == "reload":
            await self._handle_reload(params)
        elif action == "status":
            await self._handle_status_request()
        else:
            logger.warning(f"Unknown command action: {action}")

    async def _handle_pause(self) -> None:
        """Handle pause command."""
        self.app.pause()
        await self._publish_status("paused")
        logger.info("Agent paused via Redis command")

    async def _handle_resume(self) -> None:
        """Handle resume command."""
        self.app.resume()
        await self._publish_status("running")
        logger.info("Agent resumed via Redis command")

    async def _handle_reload(self, params: Dict[str, Any]) -> None:
        """
        Handle reload command.

        Args:
            params: Optional parameters for reload
        """
        # For now, just trigger a config reload if config handler is set
        # This will be expanded when config hot-reload is fully implemented
        logger.info("Reload command received (config reload not yet implemented)")
        await self._publish_status("running")

    async def _handle_status_request(self) -> None:
        """Handle status request command - publish current status."""
        state = "paused" if getattr(self.app, "paused", False) else "running"
        await self._publish_status(state)

    async def _handle_config_update(self, message: ConfigUpdateMessage) -> None:
        """
        Handle configuration update from Dashboard.

        Applies new configuration to the running agent.

        Args:
            message: Config update message
        """
        payload = message.payload

        logger.info(
            "Applying configuration update",
            extra={"event_type": "applying_config_update"}
        )

        try:
            config_changed = False

            # Update pairs
            if payload.pairs is not None:
                self.app.config.pairs = payload.pairs
                config_changed = True
                logger.info(f"Updated pairs: {payload.pairs}")

            # Update timeframes
            if payload.timeframes is not None:
                new_timeframes = [
                    TimeframeJob(
                        timeframe=tf.timeframe,
                        poll_interval_seconds=tf.poll_interval_seconds
                    )
                    for tf in payload.timeframes
                ]
                self.app.config.timeframes = new_timeframes
                config_changed = True
                logger.info(f"Updated timeframes: {[tf.timeframe for tf in new_timeframes]}")

            # Update telegram settings
            if payload.telegram is not None:
                if payload.telegram.bot_token is not None:
                    self.app.config.telegram.bot_token = payload.telegram.bot_token
                if payload.telegram.chat_id is not None:
                    self.app.config.telegram.chat_id = payload.telegram.chat_id
                if payload.telegram.message_cooldown_minutes is not None:
                    self.app.config.telegram.message_cooldown_minutes = payload.telegram.message_cooldown_minutes
                config_changed = True
                logger.info("Updated telegram settings")

            # Update thresholds
            if payload.adx_threshold is not None:
                self.app.config.adx_threshold = payload.adx_threshold
                config_changed = True
                logger.info(f"Updated ADX threshold: {payload.adx_threshold}")

            if payload.rsi_overbought is not None:
                self.app.config.rsi_overbought = payload.rsi_overbought
                config_changed = True
                logger.info(f"Updated RSI overbought: {payload.rsi_overbought}")

            if payload.rsi_oversold is not None:
                self.app.config.rsi_oversold = payload.rsi_oversold
                config_changed = True
                logger.info(f"Updated RSI oversold: {payload.rsi_oversold}")

            if payload.notify_hourly_summary is not None:
                self.app.config.notify_hourly_summary = payload.notify_hourly_summary
                config_changed = True
                logger.info(f"Updated notify_hourly_summary: {payload.notify_hourly_summary}")

            if config_changed:
                logger.info(
                    "Configuration update applied successfully",
                    extra={"event_type": "config_applied"}
                )

        except Exception as e:
            self._error_count += 1
            logger.error(
                f"Error applying config update: {e}",
                extra={"event_type": "config_apply_error"}
            )

    async def _status_heartbeat(self) -> None:
        """
        Background task sending periodic status updates.

        Runs every status_interval_seconds.
        """
        while self._running:
            try:
                await asyncio.sleep(self.config.status_interval_seconds)

                if not self._running:
                    break

                state = "paused" if getattr(self.app, "paused", False) else "running"
                await self._publish_status(state)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status heartbeat: {e}")

    async def _publish_status(self, state: str) -> None:
        """
        Publish current agent status.

        Args:
            state: Current state (running, paused, error, starting, stopping)
        """
        if not self._publisher:
            return

        uptime = time.time() - self._start_time

        payload = create_status_payload(
            state=state,
            uptime_seconds=uptime,
            last_cycle_at=self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            error_count=self._error_count,
            pairs_count=len(self.app.config.pairs) if self.app.config else 0,
            timeframes_count=len(self.app.config.timeframes) if self.app.config else 0,
            version=self.VERSION
        )

        await self._publisher.publish_status(payload)

    async def publish_signal(
        self,
        symbol: str,
        timeframe: str,
        kind: str,
        message: str,
        importance: int = 1,
        price: Optional[float] = None,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        adx: Optional[float] = None
    ) -> None:
        """
        Publish trading signal to Dashboard.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe
            kind: Signal type
            message: Signal message
            importance: Signal importance
            price: Current price
            rsi: RSI value
            macd: MACD value
            adx: ADX value
        """
        if not self._publisher:
            return

        payload = create_signal_payload(
            symbol=symbol,
            timeframe=timeframe,
            kind=kind,
            message=message,
            importance=importance,
            price=price,
            rsi=rsi,
            macd=macd,
            adx=adx
        )

        await self._publisher.publish_signal(payload)

    async def publish_metrics(
        self,
        pairs_processed: int,
        cycle_duration_ms: float,
        signals_generated: int = 0,
        signals_sent: int = 0,
        errors_in_cycle: int = 0,
        active_pairs: Optional[List[str]] = None,
        active_timeframes: Optional[List[str]] = None
    ) -> None:
        """
        Publish cycle metrics to Dashboard.

        Args:
            pairs_processed: Number of pairs processed
            cycle_duration_ms: Cycle duration in ms
            signals_generated: Signals generated
            signals_sent: Signals actually sent
            errors_in_cycle: Errors in this cycle
            active_pairs: Active pair symbols
            active_timeframes: Active timeframes
        """
        if not self._publisher:
            return

        self._last_cycle_at = datetime.now(timezone.utc)
        self._error_count += errors_in_cycle

        payload = create_metrics_payload(
            pairs_processed=pairs_processed,
            cycle_duration_ms=cycle_duration_ms,
            signals_generated=signals_generated,
            signals_sent=signals_sent,
            errors_in_cycle=errors_in_cycle,
            active_pairs=active_pairs,
            active_timeframes=active_timeframes
        )

        await self._publisher.publish_metrics(payload)

    def increment_error_count(self) -> None:
        """Increment error counter."""
        self._error_count += 1
