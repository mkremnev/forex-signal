<?php
/**
 * RedisIntegration API routes setup.
 *
 * REST API endpoints for Agent communication:
 * - POST /api/redis-integration/command - Send command to Agent
 * - POST /api/redis-integration/config - Update Agent config
 * - GET /api/redis-integration/status - Get Agent status
 * - GET /api/redis-integration/signals - Get recent signals
 * - GET /api/redis-integration/health - Check Redis connection
 */

// Bind API controller
$this->bindClass('RedisIntegration\\Controller\\Api', '/api/redis-integration');
