<?php
/**
 * Message builder for Redis Pub/Sub messages.
 *
 * Creates properly formatted messages for communication with Agent.
 */

namespace RedisIntegration\Helper;

class MessageBuilder
{
    /**
     * Build command message for Agent.
     *
     * @param string $action Command action (reload, pause, resume, status)
     * @param array $params Optional parameters
     * @return array Message structure
     */
    public static function command(string $action, array $params = []): array
    {
        return [
            'type' => 'command',
            'timestamp' => gmdate('c'),
            'payload' => [
                'action' => $action,
                'params' => $params,
            ],
            'correlation_id' => self::uuid(),
        ];
    }

    /**
     * Build configuration update message for Agent.
     *
     * @param array $config Configuration fields to update
     * @return array Message structure
     */
    public static function configUpdate(array $config): array
    {
        return [
            'type' => 'config_update',
            'timestamp' => gmdate('c'),
            'payload' => $config,
            'correlation_id' => self::uuid(),
        ];
    }

    /**
     * Generate UUID v4.
     *
     * @return string UUID string
     */
    private static function uuid(): string
    {
        return sprintf(
            '%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0x0fff) | 0x4000,
            mt_rand(0, 0x3fff) | 0x8000,
            mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0xffff)
        );
    }

    /**
     * Build config from AgentConfig singleton data.
     *
     * Maps Cockpit singleton fields to Agent config format.
     *
     * @param array $singletonData Data from AgentConfig singleton
     * @return array Config update payload
     */
    public static function configFromSingleton(array $singletonData): array
    {
        $config = [];

        // Map pairs
        if (isset($singletonData['pairs']) && is_array($singletonData['pairs'])) {
            $config['pairs'] = $singletonData['pairs'];
        }

        // Map timeframes
        if (isset($singletonData['timeframes']) && is_array($singletonData['timeframes'])) {
            $config['timeframes'] = array_map(function ($tf) {
                return [
                    'timeframe' => $tf['timeframe'] ?? '5',
                    'poll_interval_seconds' => (int)($tf['poll_interval_seconds'] ?? 60),
                ];
            }, $singletonData['timeframes']);
        }

        // Map telegram settings
        if (isset($singletonData['telegram'])) {
            $telegram = [];
            if (isset($singletonData['telegram']['bot_token'])) {
                $telegram['bot_token'] = $singletonData['telegram']['bot_token'];
            }
            if (isset($singletonData['telegram']['chat_id'])) {
                $telegram['chat_id'] = $singletonData['telegram']['chat_id'];
            }
            if (isset($singletonData['telegram']['message_cooldown_minutes'])) {
                $telegram['message_cooldown_minutes'] = (int)$singletonData['telegram']['message_cooldown_minutes'];
            }
            if (!empty($telegram)) {
                $config['telegram'] = $telegram;
            }
        }

        // Map thresholds
        if (isset($singletonData['adx_threshold'])) {
            $config['adx_threshold'] = (float)$singletonData['adx_threshold'];
        }
        if (isset($singletonData['rsi_overbought'])) {
            $config['rsi_overbought'] = (float)$singletonData['rsi_overbought'];
        }
        if (isset($singletonData['rsi_oversold'])) {
            $config['rsi_oversold'] = (float)$singletonData['rsi_oversold'];
        }

        // Map other settings
        if (isset($singletonData['notify_hourly_summary'])) {
            $config['notify_hourly_summary'] = (bool)$singletonData['notify_hourly_summary'];
        }

        return $config;
    }
}
