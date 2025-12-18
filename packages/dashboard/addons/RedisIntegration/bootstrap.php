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

// Register addon routes
$this->bindClass('RedisIntegration\\Controller\\Api', '/api/redis-integration');
$this->bindClass('RedisIntegration\\Controller\\Admin', '/redis-integration');

// Register module functions
$this->module('redisintegration')->extend([

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
$this->on('singleton.save.after.AgentConfig', function ($name, $data) {

    try {
        // Convert singleton data to Agent config format
        $config = \RedisIntegration\Helper\MessageBuilder::configFromSingleton($data);

        if (!empty($config)) {
            $this->module('redisintegration')->sendConfigToAgent($config);
        }

        // Trigger custom event
        $this->trigger('redisintegration.config.sent', [$data, $config]);

    } catch (\Exception $e) {
        // Log error but don't break the save operation
        error_log('RedisIntegration: Failed to sync config - ' . $e->getMessage());
    }
});

// Add menu item to admin sidebar
$this->on('cockpit.menu.main', function () {
    return [
        'label' => 'Agent Monitor',
        'icon' => 'activity',
        'route' => '/redis-integration',
        'active' => strpos($this['route'], '/redis-integration') === 0,
    ];
});

// Add to system menu
$this->on('cockpit.menu.system', function () {
    return [
        'label' => 'Agent Monitor',
        'icon' => 'activity',
        'route' => '/redis-integration',
    ];
});

// Register assets for admin pages
$this->on('app.layout.header', function () {
    // Only load on redis-integration pages
    if (strpos($this['route'], '/redis-integration') === 0) {
        echo '<script src="' . $this->pathToUrl('redisintegration:assets/agent-monitor.js') . '"></script>';
    }
});
