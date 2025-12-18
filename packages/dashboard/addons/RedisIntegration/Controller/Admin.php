<?php
/**
 * Admin controller for Redis integration UI.
 *
 * Provides:
 * - Agent Monitor page
 * - Server-Sent Events (SSE) endpoint for real-time updates
 */

namespace RedisIntegration\Controller;

use RedisIntegration\Helper\RedisClient;

class Admin extends \Cockpit\AuthController
{
    /**
     * GET /redis-integration
     *
     * Render Agent Monitor page.
     */
    public function index()
    {
        // Check authentication
        if (!$this->helper('auth')->getUser()) {
            return $this->helper('auth')->redirect();
        }

        return $this->render('redisintegration:views/index.php', [
            'title' => 'Agent Monitor',
        ]);
    }

    /**
     * GET /redis-integration/stream
     *
     * Server-Sent Events endpoint for real-time updates.
     *
     * Subscribes to Agent channels and forwards messages to browser.
     */
    public function stream()
    {
        // Check authentication via session or token
        if (!$this->helper('auth')->getUser() && !$this->hasValidApiKey()) {
            http_response_code(401);
            echo "data: {\"error\": \"Unauthorized\"}\n\n";
            exit;
        }

        // Set SSE headers
        header('Content-Type: text/event-stream');
        header('Cache-Control: no-cache');
        header('Connection: keep-alive');
        header('X-Accel-Buffering: no');

        // Disable output buffering
        if (ob_get_level()) {
            ob_end_clean();
        }

        try {
            $redis = RedisClient::getInstance();
            $client = $redis->getClient();

            // Subscribe to Agent channels
            $channels = [
                $redis->getChannel('status'),
                $redis->getChannel('signals'),
                $redis->getChannel('metrics'),
            ];

            $pubsub = $client->pubSubLoop();
            $pubsub->subscribe(...$channels);

            // Send initial connection event
            $this->sendSSE('connected', ['channels' => $channels]);

            // Listen for messages
            foreach ($pubsub as $message) {
                if ($message->kind === 'message') {
                    $eventType = $this->channelToEventType($message->channel);
                    $data = json_decode($message->payload, true) ?? [];

                    $this->sendSSE($eventType, $data);
                }

                // Check if connection is still alive
                if (connection_aborted()) {
                    break;
                }
            }
        } catch (\Exception $e) {
            $this->sendSSE('error', ['message' => $e->getMessage()]);
        }
    }

    /**
     * Send Server-Sent Event.
     *
     * @param string $event Event type
     * @param array $data Event data
     */
    private function sendSSE(string $event, array $data): void
    {
        $eventId = time() . '-' . mt_rand(1000, 9999);

        echo "id: {$eventId}\n";
        echo "event: {$event}\n";
        echo "data: " . json_encode($data, JSON_UNESCAPED_UNICODE) . "\n\n";

        flush();
    }

    /**
     * Convert Redis channel name to SSE event type.
     *
     * @param string $channel Channel name
     * @return string Event type
     */
    private function channelToEventType(string $channel): string
    {
        $mapping = [
            'forex:status' => 'status',
            'forex:signals' => 'signal',
            'forex:metrics' => 'metrics',
        ];

        return $mapping[$channel] ?? 'message';
    }

    /**
     * Check for valid API key.
     *
     * @return bool True if valid
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

        return $this->module('cockpit')->hasValidApiToken($token);
    }
}
