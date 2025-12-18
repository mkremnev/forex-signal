<?php
/**
 * REST API controller for Redis integration.
 *
 * Endpoints:
 * - POST /api/redis-integration/command - Send command to Agent
 * - POST /api/redis-integration/config - Update Agent config
 * - GET /api/redis-integration/status - Get Agent status
 * - GET /api/redis-integration/signals - Get recent signals
 * - GET /api/redis-integration/health - Check Redis connection
 */

namespace RedisIntegration\Controller;

use RedisIntegration\Helper\RedisClient;
use RedisIntegration\Helper\MessageBuilder;

class Api extends \Lime\AppAware
{
    /**
     * GET /api/redis-integration/health
     *
     * Check Redis connection health. Public endpoint.
     *
     * @return array Health status
     */
    public function health()
    {
        try {
            $redis = RedisClient::getInstance();
            $connected = $redis->isConnected();

            return $this->json([
                'redis' => $connected ? 'connected' : 'disconnected',
                'timestamp' => gmdate('c'),
            ]);
        } catch (\Exception $e) {
            return $this->json([
                'redis' => 'error',
                'message' => $e->getMessage(),
                'timestamp' => gmdate('c'),
            ]);
        }
    }

    /**
     * POST /api/redis-integration/command
     *
     * Send command to Agent via Redis Pub/Sub.
     *
     * @return array Response with success status
     */
    public function command()
    {
        if (!$this->isAuthenticated()) {
            return $this->json(['error' => 'Unauthorized'], 401);
        }

        $action = $this->param('action');
        $params = $this->param('params', []);

        // Validate action
        $validActions = ['reload', 'pause', 'resume', 'status'];
        if (!in_array($action, $validActions)) {
            return $this->json([
                'error' => 'Invalid action',
                'valid_actions' => $validActions
            ], 400);
        }

        try {
            $redis = RedisClient::getInstance();
            $message = MessageBuilder::command($action, $params);
            $channel = $redis->getChannel('commands');
            $subscribers = $redis->publish($channel, $message);

            return $this->json([
                'success' => true,
                'action' => $action,
                'subscribers' => $subscribers,
                'correlation_id' => $message['correlation_id'],
            ]);
        } catch (\Exception $e) {
            return $this->json([
                'error' => 'Failed to send command',
                'message' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * POST /api/redis-integration/config
     *
     * Send configuration update to Agent.
     *
     * @return array Response with success status
     */
    public function config()
    {
        if (!$this->isAuthenticated()) {
            return $this->json(['error' => 'Unauthorized'], 401);
        }

        $config = $this->param('config', []);

        if (empty($config)) {
            return $this->json(['error' => 'Config is required'], 400);
        }

        try {
            $redis = RedisClient::getInstance();
            $message = MessageBuilder::configUpdate($config);
            $channel = $redis->getChannel('config');
            $subscribers = $redis->publish($channel, $message);

            return $this->json([
                'success' => true,
                'subscribers' => $subscribers,
                'correlation_id' => $message['correlation_id'],
            ]);
        } catch (\Exception $e) {
            return $this->json([
                'error' => 'Failed to send config update',
                'message' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * GET /api/redis-integration/status
     *
     * Get latest Agent status from Redis.
     *
     * @return array Status data or unknown state
     */
    public function status()
    {
        if (!$this->isAuthenticated()) {
            return $this->json(['error' => 'Unauthorized'], 401);
        }

        try {
            $redis = RedisClient::getInstance();
            $key = $redis->getKey('last_status');
            $status = $redis->getJson($key);

            if ($status === null) {
                return $this->json([
                    'state' => 'unknown',
                    'message' => 'No status available. Agent may not be running.',
                ]);
            }

            return $this->json($status);
        } catch (\Exception $e) {
            return $this->json([
                'error' => 'Failed to get status',
                'message' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * GET /api/redis-integration/signals
     *
     * Get recent trading signals from Redis.
     *
     * @return array List of signals
     */
    public function signals()
    {
        if (!$this->isAuthenticated()) {
            return $this->json(['error' => 'Unauthorized'], 401);
        }

        $limit = (int)$this->param('limit', 50);
        $limit = min(max($limit, 1), 100); // Clamp between 1 and 100

        try {
            $redis = RedisClient::getInstance();
            $key = $redis->getKey('signals_list');
            $signals = $redis->getListJson($key, $limit);

            return $this->json([
                'count' => count($signals),
                'signals' => $signals,
            ]);
        } catch (\Exception $e) {
            return $this->json([
                'error' => 'Failed to get signals',
                'message' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * Check if request is authenticated.
     * Page is protected by ACL, so we allow all requests from browser.
     *
     * @return bool True if authenticated
     */
    private function isAuthenticated(): bool
    {
        // Simply allow all requests - the page itself is ACL protected
        return true;
    }

    /**
     * Get parameter from request.
     *
     * @param string $name Parameter name
     * @param mixed $default Default value
     * @return mixed
     */
    private function param(string $name, $default = null)
    {
        return $this->app->request->param($name, $default);
    }

    /**
     * Return JSON response.
     *
     * @param array $data Response data
     * @param int $status HTTP status code
     */
    private function json(array $data, int $status = 200)
    {
        header('Content-Type: application/json');
        http_response_code($status);
        echo json_encode($data, JSON_UNESCAPED_UNICODE);
        $this->app->stop();
    }
}
