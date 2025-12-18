<?php
/**
 * RedisIntegration addon bootstrap.
 *
 * Provides Redis Pub/Sub integration between Dashboard and Agent.
 *
 * Features:
 * - REST API for sending commands and config updates to Agent
 * - SSE endpoint for real-time status, signals, and metrics
 * - Automatic config sync via Cockpit hooks
 * - Agent Monitor UI page
 */

// Load admin interface when system initializes
$this->on('app.admin.init', function() {
    include(__DIR__.'/admin.php');
});

// Load API routes
include(__DIR__.'/api.php');

// Register module functions
$this->module('redisintegration')->extend([

    /**
     * Get addon configuration.
     *
     * @param string|null $key Configuration key
     * @param mixed $default Default value
     * @return mixed Configuration value or array
     */
    'config' => function (?string $key = null, $default = null) {
        $config = array_replace_recursive([
            'enabled' => true,
            'redis' => [
                'host' => getenv('REDIS_HOST') ?: 'redis',
                'port' => (int)(getenv('REDIS_PORT') ?: 6379),
            ],
        ], $this->app->retrieve('redisintegration', []) ?? []);

        return $key ? ($config[$key] ?? $default) : $config;
    },

    /**
     * Send command to Agent.
     *
     * @param string $action Command action
     * @param array $params Optional parameters
     * @return array Result with subscribers count
     */
    'sendCommand' => function ($action, $params = []) {
        $redis = \RedisIntegration\Helper\RedisClient::getInstance();
        $message = \RedisIntegration\Helper\MessageBuilder::command($action, $params);
        $channel = $redis->getChannel('commands');
        $subscribers = $redis->publish($channel, $message);

        return [
            'success' => true,
            'subscribers' => $subscribers,
            'correlation_id' => $message['correlation_id'],
        ];
    },

    /**
     * Send configuration update to Agent.
     *
     * @param array $config Configuration data
     * @return array Result with subscribers count
     */
    'sendConfigToAgent' => function ($config) {
        $redis = \RedisIntegration\Helper\RedisClient::getInstance();
        $message = \RedisIntegration\Helper\MessageBuilder::configUpdate($config);
        $channel = $redis->getChannel('config');
        $subscribers = $redis->publish($channel, $message);

        return [
            'success' => true,
            'subscribers' => $subscribers,
            'correlation_id' => $message['correlation_id'],
        ];
    },

    /**
     * Get Agent status from Redis.
     *
     * @return array|null Status data or null
     */
    'getAgentStatus' => function () {
        try {
            $redis = \RedisIntegration\Helper\RedisClient::getInstance();
            $key = $redis->getKey('last_status');
            return $redis->getJson($key);
        } catch (\Exception $e) {
            return null;
        }
    },

    /**
     * Get recent signals from Redis.
     *
     * @param int $limit Maximum signals to return
     * @return array List of signals
     */
    'getRecentSignals' => function ($limit = 50) {
        try {
            $redis = \RedisIntegration\Helper\RedisClient::getInstance();
            $key = $redis->getKey('signals_list');
            return $redis->getListJson($key, $limit);
        } catch (\Exception $e) {
            return [];
        }
    },

    /**
     * Check Redis connection health.
     *
     * @return bool True if connected
     */
    'isRedisConnected' => function () {
        try {
            $redis = \RedisIntegration\Helper\RedisClient::getInstance();
            return $redis->isConnected();
        } catch (\Exception $e) {
            return false;
        }
    },
]);

// Hook: Sync config when AgentConfig singleton is saved
// Cockpit uses content.item.save.{modelName} for all content types including singletons
$this->on('content.item.save.AgentConfig', function ($item, $isUpdate, $collection) {

    try {
        // Convert singleton data to Agent config format
        $config = \RedisIntegration\Helper\MessageBuilder::configFromSingleton($item);

        if (!empty($config)) {
            $this->module('redisintegration')->sendConfigToAgent($config);
            error_log('RedisIntegration: Config synced to Agent - pairs: ' . json_encode($config['pairs'] ?? []));
        }

        // Trigger custom event
        $this->trigger('redisintegration.config.sent', [$item, $config]);

    } catch (\Exception $e) {
        // Log error but don't break the save operation
        error_log('RedisIntegration: Failed to sync config - ' . $e->getMessage());
    }
});
