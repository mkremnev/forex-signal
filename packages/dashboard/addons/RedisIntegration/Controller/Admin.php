<?php
/**
 * Admin controller for Redis integration UI.
 *
 * Provides:
 * - Agent Monitor page
 * - Server-Sent Events (SSE) endpoint for real-time updates
 */

namespace RedisIntegration\Controller;

use App\Controller\Base;
use RedisIntegration\Helper\RedisClient;

class Admin extends Base
{
    protected $layout = "app:layouts/app.php";

    /**
     * Check permissions before executing any action.
     */
    public function before(string $action = ""): bool
    {
        // Allow health check without authentication
        if ($action === "stream" && $this->hasValidApiKey()) {
            return true;
        }

        // Check for view permission
        if (!$this->helper("acl")->hasPermission("redisintegration/view")) {
            $this->stop(401);
            return false;
        }

        return true;
    }

    /**
     * GET /redis-integration
     *
     * Render Agent Monitor page.
     */
    public function index()
    {
        return $this->render("redisintegration:views/index.php", [
            "title" => "Agent Monitor",
            "canControl" => $this->helper("acl")->hasPermission(
                "redisintegration/control",
            ),
        ]);
    }

    /**
     * GET /redis-integration/stream
     *
     * SSE endpoint disabled - using polling via API instead.
     */
    public function stream()
    {
        header("Content-Type: application/json");
        echo json_encode(["error" => "SSE disabled, use API polling"]);
        exit();
    }

    /**
     * Send Server-Sent Event.
     *
     * @param string $event Event type
     * @param array $data Event data
     */
    public function sendSSE(string $event, array $data): void
    {
        $eventId = time() . "-" . mt_rand(1000, 9999);

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
    public function channelToEventType(string $channel): string
    {
        $mapping = [
            "forex:status" => "status",
            "forex:signals" => "signal",
            "forex:metrics" => "metrics",
        ];

        return $mapping[$channel] ?? "message";
    }

    /**
     * Check for valid API key.
     *
     * @return bool True if valid
     */
    private function hasValidApiKey(): bool
    {
        // Get token from header or query parameter
        $token = $_SERVER["HTTP_COCKPIT_TOKEN"] ?? null;
        if (!$token) {
            $token = $this->param("token");
        }

        if (!$token) {
            return false;
        }

        try {
            return $this->app->helper("api")->isApiRequestAllowed($token);
        } catch (\Exception $e) {
            return false;
        }
    }
}
