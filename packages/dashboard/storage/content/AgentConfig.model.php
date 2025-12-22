<?php
/**
 * AgentConfig Singleton Model
 *
 * Stores configuration for Forex Signal Agent.
 * When saved, triggers Redis Pub/Sub to sync with Agent.
 */

return [
    "name" => "AgentConfig",
    "label" => "Agent Configuration",
    "type" => "singleton",
    "description" => "Forex Signal Agent configuration settings",
    "color" => "#4A90D9",
    "icon" => "settings",
    "fields" => [
        // Trading pairs
        [
            "name" => "pairs",
            "label" => "Trading Pairs",
            "type" => "tags",
            "opts" => [
                "placeholder" => "Add pair (e.g. EUR_USD)",
            ],
            "info" =>
                "Currency pairs to monitor. Enter each pair separately (e.g. EUR_USD, GBP/USD)",
            "default" => ["EUR_USD", "GBP_USD"],
        ],
        // Timeframes configuration
        [
            "name" => "timeframes",
            "label" => "Timeframes",
            "type" => "repeater",
            "opts" => [
                "fields" => [
                    [
                        "name" => "timeframe",
                        "label" => "Timeframe",
                        "type" => "select",
                        "opts" => [
                            "options" => [
                                "1" => "1 minute",
                                "5" => "5 minutes",
                                "15" => "15 minutes",
                                "30" => "30 minutes",
                                "60" => "1 hour",
                                "4h" => "4 hours",
                                "D" => "Daily",
                            ],
                        ],
                    ],
                    [
                        "name" => "poll_interval_seconds",
                        "label" => "Poll Interval (seconds)",
                        "type" => "number",
                        "default" => 60,
                    ],
                ],
            ],
            "info" => "Timeframes and their polling intervals",
        ],
        // Telegram settings group
        [
            "name" => "telegram",
            "label" => "Telegram Settings",
            "type" => "set",
            "opts" => [
                "fields" => [
                    [
                        "name" => "bot_token",
                        "label" => "Bot Token",
                        "type" => "text",
                        "info" => "Telegram Bot API token",
                    ],
                    [
                        "name" => "chat_id",
                        "label" => "Chat ID",
                        "type" => "text",
                        "info" => "Telegram chat/channel ID for notifications",
                    ],
                    [
                        "name" => "message_cooldown_minutes",
                        "label" => "Message Cooldown (minutes)",
                        "type" => "number",
                        "default" => 60,
                        "info" => "Minimum time between same signal messages",
                    ],
                ],
            ],
        ],
        // Technical analysis thresholds
        [
            "name" => "adx_threshold",
            "label" => "ADX Threshold",
            "type" => "number",
            "default" => 20.0,
            "opts" => [
                "step" => 0.1,
                "min" => 0,
                "max" => 100,
            ],
            "info" => "ADX value above which trend is considered strong",
        ],
        [
            "name" => "rsi_overbought",
            "label" => "RSI Overbought Level",
            "type" => "number",
            "default" => 70.0,
            "opts" => [
                "step" => 1,
                "min" => 50,
                "max" => 100,
            ],
            "info" => "RSI level indicating overbought condition",
        ],
        [
            "name" => "rsi_oversold",
            "label" => "RSI Oversold Level",
            "type" => "number",
            "default" => 30.0,
            "opts" => [
                "step" => 1,
                "min" => 0,
                "max" => 50,
            ],
            "info" => "RSI level indicating oversold condition",
        ],
        // Other settings
        [
            "name" => "notify_hourly_summary",
            "label" => "Hourly Summary Notifications",
            "type" => "boolean",
            "default" => true,
            "info" => "Send hourly status summary to Telegram",
        ],
    ],
    "data" => [
        // Default values
        "pairs" => ["EUR_USD", "GBP_USD", "USD_JPY"],
        "timeframes" => [
            ["timeframe" => "5", "poll_interval_seconds" => 60],
            ["timeframe" => "4h", "poll_interval_seconds" => 180],
        ],
        "telegram" => [
            "bot_token" => "",
            "chat_id" => "",
            "message_cooldown_minutes" => 60,
        ],
        "adx_threshold" => 20.0,
        "rsi_overbought" => 70.0,
        "rsi_oversold" => 30.0,
        "notify_hourly_summary" => true,
    ],
];
