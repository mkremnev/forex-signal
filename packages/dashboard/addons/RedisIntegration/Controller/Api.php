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

class Api extends \Cockpit\AuthController
{
    /**
     * POST /api/redis-integration/command
     *
     * Send command to Agent via Redis Pub/Sub.
     *
     * @return array Response with success status
     */
    public function command()
    {
        // Check authentication
        if (!$this->isAuthenticated()) {
            return $this->stop(['error' => 'Unauthorized'], 401);
        }

        $action = $this->param('action');
        $params = $this->param('params', []);

        // Validate action
        $validActions = ['reload', 'pause', 'resume', 'status'];
        if (!in_array($action, $validActions)) {
            return $this->stop([
                'error' => 'Invalid action',
                'valid_actions' => $validActions
            ], 400);
        }

        try {
            $redis = RedisClient::getInstance();
            $message = MessageBuilder::command($action, $params);
            $channel = $redis->getChannel('commands');
            $subscribers = $redis->publish($channel, $message);

            return [
                'success' => true,
                'action' => $action,
                'subscribers' => $subscribers,
                'correlation_id' => $message['correlation_id'],
            ];
        } catch (\Exception $e) {
            return $this->stop([
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
    public function updateConfig()
    {
        if (!$this->isAuthenticated()) {
            return $this->stop(['error' => 'Unauthorized'], 401);
        }

        $config = $this->param('config', []);

        if (empty($config)) {
            return $this->stop(['error' => 'Config is required'], 400);
        }

        try {
            $redis = RedisClient::getInstance();
            $message = MessageBuilder::configUpdate($config);
            $channel = $redis->getChannel('config');
            $subscribers = $redis->publish($channel, $message);

            return [
                'success' => true,
                'subscribers' => $subscribers,
                'correlation_id' => $message['correlation_id'],
            ];
        } catch (\Exception $e) {
            return $this->stop([
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
            return $this->stop(['error' => 'Unauthorized'], 401);
        }

        try {
            $redis = RedisClient::getInstance();
            $key = $redis->getKey('last_status');
            $status = $redis->getJson($key);

            if ($status === null) {
                return [
                    'state' => 'unknown',
                    'message' => 'No status available. Agent may not be running.',
                ];
            }

            return $status;
        } catch (\Exception $e) {
            return $this->stop([
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
            return $this->stop(['error' => 'Unauthorized'], 401);
        }

        $limit = (int)$this->param('limit', 50);
        $limit = min(max($limit, 1), 100); // Clamp between 1 and 100

        try {
            $redis = RedisClient::getInstance();
            $key = $redis->getKey('signals_list');
            $signals = $redis->getListJson($key, $limit);

            return [
                'count' => count($signals),
                'signals' => $signals,
            ];
        } catch (\Exception $e) {
            return $this->stop([
                'error' => 'Failed to get signals',
                'message' => $e->getMessage()
            ], 500);
        }
    }

    /**
     * GET /api/redis-integration/health
     *
     * Check Redis connection health.
     *
     * @return array Health status
     */
    public function health()
    {
        try {
            $redis = RedisClient::getInstance();
            $connected = $redis->isConnected();

            return [
                'redis' => $connected ? 'connected' : 'disconnected',
                'timestamp' => gmdate('c'),
            ];
        } catch (\Exception $e) {
            return [
                'redis' => 'error',
                'message' => $e->getMessage(),
                'timestamp' => gmdate('c'),
            ];
        }
    }

    /**
     * Check if request is authenticated.
     *
     * @return bool True if authenticated
     */
    private function isAuthenticated(): bool
    {
        // Check for API key or session
        return $this->helper('auth')->getUser() !== null
            || $this->param('api_key')
            || $this->hasValidApiKey();
    }

    /**
     * Check for valid API key in header.
     *
     * @return bool True if valid API key present
     */
    private function hasValidApiKey(): bool
    {
        $token = $this->app->request->headers->get('Cockpit-Token');
        if (!$token) {
            $token = $this->param('token');
        }

        if (!$token) {
            return false;
        }

        // Validate token through Cockpit's built-in mechanism
        return $this->module('cockpit')->hasValidApiToken($token);
    }
}
