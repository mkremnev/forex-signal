"""
Redis subscriber for receiving commands and config updates from Dashboard.

Subscribes to channels:
- forex:commands - Control commands (reload, pause, resume, status)
- forex:config   - Configuration updates
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional, Awaitable, TYPE_CHECKING

from .message_types import (
    RedisChannels,
    CommandMessage,
    ConfigUpdateMessage,
    parse_incoming_message,
)
from .redis_client import RedisConnectionManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Type aliases for handlers
CommandHandler = Callable[[CommandMessage], Awaitable[None]]
ConfigHandler = Callable[[ConfigUpdateMessage], Awaitable[None]]


class RedisSubscriber:
    """
    Async subscriber for receiving messages from Dashboard.

    Features:
    - Subscribes to command and config channels
    - Automatic reconnection on connection loss
    - Message routing to appropriate handlers
    - Graceful shutdown
    """

    # Channels to subscribe to
    CHANNELS = [RedisChannels.COMMANDS, RedisChannels.CONFIG]

    def __init__(
        self,
        redis_manager: RedisConnectionManager,
        command_handler: CommandHandler,
        config_handler: ConfigHandler
    ):
        """
        Initialize Redis subscriber.

        Args:
            redis_manager: Redis connection manager instance
            command_handler: Async handler for command messages
            config_handler: Async handler for config update messages
        """
        self._redis = redis_manager
        self._command_handler = command_handler
        self._config_handler = config_handler
        self._running = False
        self._listener_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the subscriber listener task."""
        if self._running:
            return

        self._running = True
        self._listener_task = asyncio.create_task(self._listen())
        logger.info(
            f"Redis subscriber started, listening on {self.CHANNELS}",
            extra={"event_type": "subscriber_started", "channels": self.CHANNELS}
        )

    async def stop(self) -> None:
        """Stop the subscriber gracefully."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        logger.info("Redis subscriber stopped", extra={"event_type": "subscriber_stopped"})

    async def _listen(self) -> None:
        """
        Main listener loop with automatic reconnection.

        Subscribes to channels and processes incoming messages.
        Reconnects automatically if connection is lost.
        """
        while self._running:
            try:
                pubsub = await self._redis.get_pubsub()
                await pubsub.subscribe(*self.CHANNELS)

                logger.info(
                    f"Subscribed to channels: {self.CHANNELS}",
                    extra={"event_type": "subscribed", "channels": self.CHANNELS}
                )

                # Listen for messages
                async for message in pubsub.listen():
                    if not self._running:
                        break

                    if message["type"] == "message":
                        await self._handle_message(message)

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error(
                    f"Error in subscriber listener: {e}",
                    extra={"event_type": "subscriber_error"}
                )

                if self._running:
                    # Try to reconnect
                    logger.info("Attempting to reconnect subscriber...")
                    success = await self._redis.reconnect_with_backoff()
                    if not success:
                        logger.error("Failed to reconnect, stopping subscriber")
                        break

    async def _handle_message(self, message: dict) -> None:
        """
        Handle incoming Redis message.

        Parses JSON, determines message type, and routes to appropriate handler.

        Args:
            message: Raw Redis message dict with 'channel' and 'data' keys
        """
        channel = message.get("channel", "")
        data = message.get("data", "")

        logger.debug(
            f"Received message on {channel}",
            extra={"event_type": "message_received", "channel": channel}
        )

        try:
            # Parse JSON
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            parsed = json.loads(data)

            # Parse into typed message
            typed_message = parse_incoming_message(parsed)

            if typed_message is None:
                logger.warning(
                    f"Unknown message type on {channel}: {parsed.get('type')}",
                    extra={"event_type": "unknown_message_type"}
                )
                return

            # Route to appropriate handler
            if isinstance(typed_message, CommandMessage):
                await self._handle_command(typed_message)
            elif isinstance(typed_message, ConfigUpdateMessage):
                await self._handle_config_update(typed_message)

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON message: {e}",
                extra={"event_type": "json_parse_error", "channel": channel}
            )

        except Exception as e:
            logger.error(
                f"Error handling message: {e}",
                extra={"event_type": "message_handler_error", "channel": channel}
            )

    async def _handle_command(self, message: CommandMessage) -> None:
        """
        Handle command message.

        Args:
            message: Parsed command message
        """
        action = message.payload.action
        correlation_id = message.correlation_id

        logger.info(
            f"Received command: {action} (correlation_id: {correlation_id})",
            extra={
                "event_type": "command_received",
                "action": action,
                "correlation_id": correlation_id
            }
        )

        try:
            await self._command_handler(message)
            logger.info(
                f"Command {action} executed successfully",
                extra={"event_type": "command_executed", "action": action}
            )
        except Exception as e:
            logger.error(
                f"Error executing command {action}: {e}",
                extra={"event_type": "command_error", "action": action}
            )

    async def _handle_config_update(self, message: ConfigUpdateMessage) -> None:
        """
        Handle configuration update message.

        Args:
            message: Parsed config update message
        """
        correlation_id = message.correlation_id

        logger.info(
            f"Received config update (correlation_id: {correlation_id})",
            extra={
                "event_type": "config_update_received",
                "correlation_id": correlation_id
            }
        )

        try:
            await self._config_handler(message)
            logger.info(
                "Config update applied successfully",
                extra={"event_type": "config_updated"}
            )
        except Exception as e:
            logger.error(
                f"Error applying config update: {e}",
                extra={"event_type": "config_update_error"}
            )
