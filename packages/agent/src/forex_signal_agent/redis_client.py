"""
Redis connection manager with automatic reconnection and health checks.

Provides async Redis client for Pub/Sub integration between Agent and Dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional, TYPE_CHECKING

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

if TYPE_CHECKING:
    from .config import RedisConfig

logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""
    pass


class RedisConnectionManager:
    """
    Manages Redis connection with automatic reconnection and health checks.

    Features:
    - Async Redis client using redis-py 5.x
    - Exponential backoff reconnection strategy
    - Connection health monitoring
    - Separate PubSub connections
    """

    def __init__(self, config: RedisConfig):
        """
        Initialize Redis connection manager.

        Args:
            config: Redis configuration from AppConfig
        """
        self.config = config
        self._client: Optional[aioredis.Redis] = None
        self._pubsub: Optional[PubSub] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._closing = False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is currently connected."""
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """
        Establish connection to Redis server.

        Raises:
            RedisConnectionError: If connection fails after all retries
        """
        if self._connected:
            return

        try:
            self._client = aioredis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )

            # Test connection
            await self._client.ping()
            self._connected = True

            logger.info(
                f"Connected to Redis at {self.config.host}:{self.config.port}",
                extra={"event_type": "redis_connected"}
            )

        except Exception as e:
            self._connected = False
            logger.error(
                f"Failed to connect to Redis: {e}",
                extra={"event_type": "redis_connection_error"}
            )
            raise RedisConnectionError(f"Failed to connect to Redis: {e}") from e

    async def disconnect(self) -> None:
        """Close Redis connection gracefully."""
        self._closing = True

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            try:
                await self._pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing PubSub: {e}")
            self._pubsub = None

        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            self._client = None

        self._connected = False
        logger.info("Disconnected from Redis", extra={"event_type": "redis_disconnected"})

    async def get_client(self) -> aioredis.Redis:
        """
        Get Redis client, reconnecting if necessary.

        Returns:
            Active Redis client

        Raises:
            RedisConnectionError: If not connected and cannot reconnect
        """
        if not self._connected or self._client is None:
            await self.connect()

        if self._client is None:
            raise RedisConnectionError("Redis client is not available")

        return self._client

    async def get_pubsub(self) -> PubSub:
        """
        Get PubSub instance for subscriptions.

        Returns:
            PubSub instance

        Raises:
            RedisConnectionError: If not connected
        """
        client = await self.get_client()

        if self._pubsub is None:
            self._pubsub = client.pubsub()

        return self._pubsub

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._connected or self._client is None:
            return False

        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            self._connected = False
            return False

    async def reconnect_with_backoff(self) -> bool:
        """
        Attempt to reconnect with exponential backoff.

        Returns:
            True if reconnection succeeded, False otherwise
        """
        if self._closing:
            return False

        for attempt in range(self.config.reconnect_max_attempts):
            if self._closing:
                return False

            # Calculate delay with jitter
            delay = min(
                self.config.reconnect_base_delay * (2 ** attempt),
                self.config.reconnect_max_delay
            )
            delay += random.uniform(0, delay * 0.1)  # Add 10% jitter

            logger.warning(
                f"Redis reconnect attempt {attempt + 1}/{self.config.reconnect_max_attempts}, "
                f"waiting {delay:.1f}s",
                extra={"event_type": "redis_reconnect_attempt", "attempt": attempt + 1}
            )

            await asyncio.sleep(delay)

            if self._closing:
                return False

            try:
                # Close existing connection if any
                if self._client:
                    try:
                        await self._client.close()
                    except Exception:
                        pass
                    self._client = None

                await self.connect()
                logger.info(
                    "Redis reconnected successfully",
                    extra={"event_type": "redis_reconnected"}
                )
                return True

            except Exception as e:
                logger.error(
                    f"Reconnect attempt {attempt + 1} failed: {e}",
                    extra={"event_type": "redis_reconnect_failed", "attempt": attempt + 1}
                )

        logger.error(
            f"Failed to reconnect to Redis after {self.config.reconnect_max_attempts} attempts",
            extra={"event_type": "redis_reconnect_exhausted"}
        )
        return False

    async def start_health_monitor(self, interval: int = 30) -> None:
        """
        Start background health monitoring task.

        Args:
            interval: Health check interval in seconds
        """
        if self._health_check_task and not self._health_check_task.done():
            return

        async def _monitor():
            while not self._closing:
                try:
                    await asyncio.sleep(interval)
                    if not await self.health_check():
                        logger.warning(
                            "Redis health check failed, attempting reconnect",
                            extra={"event_type": "redis_health_failed"}
                        )
                        await self.reconnect_with_backoff()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in health monitor: {e}")

        self._health_check_task = asyncio.create_task(_monitor())
        logger.debug("Started Redis health monitor")

    async def publish(self, channel: str, message: str) -> int:
        """
        Publish message to Redis channel.

        Args:
            channel: Channel name
            message: Message to publish (should be JSON string)

        Returns:
            Number of subscribers that received the message
        """
        client = await self.get_client()
        try:
            result = await client.publish(channel, message)
            logger.debug(
                f"Published to {channel}, {result} subscribers received",
                extra={"event_type": "redis_publish", "channel": channel}
            )
            return result
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            self._connected = False
            raise

    async def set_with_expiry(self, key: str, value: str, ttl_seconds: int) -> bool:
        """
        Set key with expiration time.

        Args:
            key: Redis key
            value: Value to store
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful
        """
        client = await self.get_client()
        try:
            await client.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    async def lpush_with_trim(self, key: str, value: str, max_length: int = 100) -> None:
        """
        Push to list and trim to max length.

        Args:
            key: Redis list key
            value: Value to push
            max_length: Maximum list length
        """
        client = await self.get_client()
        try:
            await client.lpush(key, value)
            await client.ltrim(key, 0, max_length - 1)
        except Exception as e:
            logger.error(f"Failed to lpush to {key}: {e}")
            raise

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key.

        Args:
            key: Redis key

        Returns:
            Value or None if not found
        """
        client = await self.get_client()
        try:
            return await client.get(key)
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> list:
        """
        Get list range.

        Args:
            key: Redis list key
            start: Start index
            end: End index (-1 for all)

        Returns:
            List of values
        """
        client = await self.get_client()
        try:
            return await client.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Failed to lrange {key}: {e}")
            return []
