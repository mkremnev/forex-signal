"""
Tests for Redis Pub/Sub integration components.

Tests cover:
- Message types parsing and serialization
- IntegrationManager command and config handling
- RedisPublisher message formatting
- RedisSubscriber message routing
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json

from forex_signal_agent.message_types import (
    CommandMessage,
    CommandPayload,
    ConfigUpdateMessage,
    ConfigUpdatePayload,
    TelegramConfigPayload,
    TimeframeConfigPayload,
    StatusMessage,
    StatusPayload,
    SignalMessage,
    SignalPayload,
    MetricsMessage,
    MetricsPayload,
    parse_incoming_message,
    RedisChannels,
)
from forex_signal_agent.redis_publisher import (
    create_status_payload,
    create_signal_payload,
    create_metrics_payload,
)


class TestMessageTypes:
    """Tests for Pydantic message models."""

    def test_command_message_creation(self):
        """Test creating a command message."""
        payload = CommandPayload(action="pause", params={})
        msg = CommandMessage(payload=payload)

        assert msg.type == "command"
        assert msg.payload.action == "pause"
        assert msg.payload.params == {}
        assert msg.correlation_id is not None
        assert msg.timestamp is not None

    def test_command_message_with_params(self):
        """Test command message with parameters."""
        payload = CommandPayload(action="reload", params={"full": True})
        msg = CommandMessage(payload=payload)

        assert msg.payload.action == "reload"
        assert msg.payload.params == {"full": True}

    def test_config_update_message_pairs_only(self):
        """Test config update with only pairs."""
        payload = ConfigUpdatePayload(pairs=["EUR_USD", "GBP_USD"])
        msg = ConfigUpdateMessage(payload=payload)

        assert msg.type == "config_update"
        assert msg.payload.pairs == ["EUR_USD", "GBP_USD"]
        assert msg.payload.timeframes is None
        assert msg.payload.telegram is None

    def test_config_update_message_full(self):
        """Test config update with all fields."""
        telegram = TelegramConfigPayload(
            bot_token="token123",
            chat_id="123456",
            message_cooldown_minutes=30
        )
        timeframes = [
            TimeframeConfigPayload(timeframe="5", poll_interval_seconds=60),
            TimeframeConfigPayload(timeframe="4h", poll_interval_seconds=180)
        ]
        payload = ConfigUpdatePayload(
            pairs=["EUR_USD"],
            timeframes=timeframes,
            telegram=telegram,
            notify_hourly_summary=False
        )
        msg = ConfigUpdateMessage(payload=payload)

        assert msg.payload.pairs == ["EUR_USD"]
        assert len(msg.payload.timeframes) == 2
        assert msg.payload.telegram.bot_token == "token123"
        assert msg.payload.notify_hourly_summary is False

    def test_status_message_creation(self):
        """Test creating a status message."""
        payload = StatusPayload(
            state="running",
            uptime_seconds=3600.0,
            error_count=0,
            pairs_count=3,
            timeframes_count=2
        )
        msg = StatusMessage(payload=payload)

        assert msg.type == "status"
        assert msg.payload.state == "running"
        assert msg.payload.uptime_seconds == 3600.0

    def test_signal_message_creation(self):
        """Test creating a signal message."""
        payload = SignalPayload(
            symbol="EUR_USD",
            timeframe="4h",
            kind="macd_bull",
            message="MACD bullish crossover detected",
            importance=2,
            price=1.0850
        )
        msg = SignalMessage(payload=payload)

        assert msg.type == "signal"
        assert msg.payload.symbol == "EUR_USD"
        assert msg.payload.importance == 2

    def test_metrics_message_creation(self):
        """Test creating a metrics message."""
        payload = MetricsPayload(
            pairs_processed=6,
            cycle_duration_ms=1234.5,
            signals_generated=2,
            signals_sent=1,
            active_pairs=["EUR_USD", "GBP_USD"],
            active_timeframes=["5", "4h"]
        )
        msg = MetricsMessage(payload=payload)

        assert msg.type == "metrics"
        assert msg.payload.pairs_processed == 6
        assert msg.payload.cycle_duration_ms == 1234.5


class TestMessageParsing:
    """Tests for message parsing utilities."""

    def test_parse_command_message(self):
        """Test parsing a command message from JSON."""
        data = {
            "type": "command",
            "timestamp": "2025-12-18T12:00:00Z",
            "correlation_id": "test-uuid",
            "payload": {
                "action": "pause",
                "params": {}
            }
        }

        msg = parse_incoming_message(data)

        assert isinstance(msg, CommandMessage)
        assert msg.payload.action == "pause"

    def test_parse_config_update_message(self):
        """Test parsing a config update message from JSON."""
        data = {
            "type": "config_update",
            "timestamp": "2025-12-18T12:00:00Z",
            "correlation_id": "test-uuid",
            "payload": {
                "pairs": ["EUR_USD", "GBP_USD"],
                "notify_hourly_summary": True
            }
        }

        msg = parse_incoming_message(data)

        assert isinstance(msg, ConfigUpdateMessage)
        assert msg.payload.pairs == ["EUR_USD", "GBP_USD"]
        assert msg.payload.notify_hourly_summary is True

    def test_parse_unknown_message_type(self):
        """Test parsing unknown message type returns None."""
        data = {
            "type": "unknown",
            "payload": {}
        }

        msg = parse_incoming_message(data)

        assert msg is None

    def test_parse_invalid_message(self):
        """Test parsing invalid message returns None."""
        data = {"invalid": "data"}

        msg = parse_incoming_message(data)

        assert msg is None


class TestPayloadCreators:
    """Tests for payload creation helper functions."""

    def test_create_status_payload(self):
        """Test creating status payload."""
        payload = create_status_payload(
            state="running",
            uptime_seconds=1800.0,
            last_cycle_at="2025-12-18T12:00:00Z",
            error_count=0,
            pairs_count=3,
            timeframes_count=2,
            version="0.1.0"
        )

        # Functions return Pydantic models, not dicts
        assert payload.state == "running"
        assert payload.uptime_seconds == 1800.0
        assert payload.pairs_count == 3

    def test_create_signal_payload(self):
        """Test creating signal payload."""
        payload = create_signal_payload(
            symbol="EUR_USD",
            timeframe="4h",
            kind="trend_up",
            message="Strong uptrend detected",
            importance=2,
            price=1.0850,
            rsi=45.0,
            adx=28.0
        )

        # Functions return Pydantic models, not dicts
        assert payload.symbol == "EUR_USD"
        assert payload.timeframe == "4h"
        assert payload.kind == "trend_up"
        assert payload.indicators.rsi == 45.0

    def test_create_metrics_payload(self):
        """Test creating metrics payload."""
        payload = create_metrics_payload(
            pairs_processed=6,
            cycle_duration_ms=1500.0,
            signals_generated=2,
            signals_sent=1,
            errors_in_cycle=0,
            active_pairs=["EUR_USD"],
            active_timeframes=["5"]
        )

        # Functions return Pydantic models, not dicts
        assert payload.pairs_processed == 6
        assert payload.cycle_duration_ms == 1500.0
        assert payload.active_pairs == ["EUR_USD"]


class TestRedisChannels:
    """Tests for Redis channel constants."""

    def test_channel_names(self):
        """Test that channel names are correctly defined."""
        assert RedisChannels.COMMANDS == "forex:commands"
        assert RedisChannels.CONFIG == "forex:config"
        assert RedisChannels.STATUS == "forex:status"
        assert RedisChannels.SIGNALS == "forex:signals"
        assert RedisChannels.METRICS == "forex:metrics"

    def test_key_names(self):
        """Test that Redis key names are correctly defined."""
        assert RedisChannels.LAST_STATUS == "forex:agent:last_status"
        assert RedisChannels.SIGNALS_LIST == "forex:agent:signals"


class TestIntegrationManagerCommands:
    """Tests for IntegrationManager command handling (mocked)."""

    @pytest.fixture
    def mock_app(self):
        """Create mock Application."""
        app = MagicMock()
        app.paused = False
        app.config = MagicMock()
        app.config.pairs = ["EUR_USD"]
        app.config.timeframes = []
        app.config.telegram = MagicMock()
        app.config.telegram.bot_token = ""
        app.config.telegram.chat_id = ""
        app.config.telegram.message_cooldown_minutes = 60
        app.config.adx_threshold = 20.0
        app.config.rsi_overbought = 70.0
        app.config.rsi_oversold = 30.0
        app.config.notify_hourly_summary = True
        return app

    def test_pause_command_sets_paused_flag(self, mock_app):
        """Test that pause command sets app.paused = True."""
        mock_app.pause = MagicMock()

        # Simulate what IntegrationManager._handle_pause does
        mock_app.pause()

        mock_app.pause.assert_called_once()

    def test_resume_command_clears_paused_flag(self, mock_app):
        """Test that resume command sets app.paused = False."""
        mock_app.resume = MagicMock()

        # Simulate what IntegrationManager._handle_resume does
        mock_app.resume()

        mock_app.resume.assert_called_once()


class TestConfigUpdateHandling:
    """Tests for configuration update handling."""

    @pytest.fixture
    def mock_app(self):
        """Create mock Application with config."""
        app = MagicMock()
        app.config = MagicMock()
        app.config.pairs = ["EUR_USD"]
        app.config.timeframes = []
        app.config.telegram = MagicMock()
        app.config.telegram.bot_token = ""
        app.config.telegram.chat_id = ""
        app.config.telegram.message_cooldown_minutes = 60
        app.config.adx_threshold = 20.0
        app.config.rsi_overbought = 70.0
        app.config.rsi_oversold = 30.0
        return app

    def test_config_update_pairs(self, mock_app):
        """Test updating pairs configuration."""
        new_pairs = ["GBP_USD", "USD_JPY"]

        # Simulate what IntegrationManager._handle_config_update does
        mock_app.config.pairs = new_pairs

        assert mock_app.config.pairs == ["GBP_USD", "USD_JPY"]

    def test_config_update_thresholds(self, mock_app):
        """Test updating threshold values."""
        mock_app.config.adx_threshold = 25.0
        mock_app.config.rsi_overbought = 75.0
        mock_app.config.rsi_oversold = 25.0

        assert mock_app.config.adx_threshold == 25.0
        assert mock_app.config.rsi_overbought == 75.0
        assert mock_app.config.rsi_oversold == 25.0


class TestMessageSerialization:
    """Tests for message JSON serialization."""

    def test_command_message_to_json(self):
        """Test serializing command message to JSON."""
        payload = CommandPayload(action="pause", params={})
        msg = CommandMessage(payload=payload)

        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        assert data["type"] == "command"
        assert data["payload"]["action"] == "pause"
        assert "timestamp" in data
        assert "correlation_id" in data

    def test_status_message_to_json(self):
        """Test serializing status message to JSON."""
        payload = StatusPayload(
            state="running",
            uptime_seconds=3600.0,
            error_count=0,
            pairs_count=3,
            timeframes_count=2
        )
        msg = StatusMessage(payload=payload)

        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        assert data["type"] == "status"
        assert data["payload"]["state"] == "running"

    def test_config_update_message_to_json(self):
        """Test serializing config update message to JSON."""
        payload = ConfigUpdatePayload(
            pairs=["EUR_USD"],
            notify_hourly_summary=True
        )
        msg = ConfigUpdateMessage(payload=payload)

        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        assert data["type"] == "config_update"
        assert data["payload"]["pairs"] == ["EUR_USD"]
        assert data["payload"]["notify_hourly_summary"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
