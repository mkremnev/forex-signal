<?php
/**
 * RedisIntegration admin interface setup.
 *
 * Handles:
 * - Route binding for admin controller
 * - Menu registration
 * - Permission definitions
 * - Asset loading
 */

// Define addon permissions
$this->helper("acl")->addPermissions([
    "redisintegration" => [
        "manage" => "Manage Agent Monitor",
        "view" => "View Agent Status",
        "control" => "Control Agent (pause/resume/reload)",
    ],
]);

// Bind admin controller (always register the route)
$this->bindClass("RedisIntegration\\Controller\\Admin", "/redis-integration");

// Add to settings menu
$this->on("app.settings.collect", function ($settings) {
    $settings["System"][] = [
        "icon" => "redisintegration:icon.svg",
        "route" => "/redis-integration",
        "label" => "Agent Monitor",
        "permission" => "redisintegration/view",
    ];
});

// Register assets for admin pages
$this->on("app.layout.assets", function () {
    $route = $this->retrieve("route", "");
    if (is_string($route) && strpos($route, "/redis-integration") === 0) {
        $this->script("redisintegration:assets/agent-monitor.js");
    }
});
