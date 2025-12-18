<?php
/**
 * Redis configuration for Dashboard <-> Agent integration
 */

return [
    'host' => getenv('REDIS_HOST') ?: 'redis',
    'port' => (int)(getenv('REDIS_PORT') ?: 6379),
    'db' => 0,
    'password' => getenv('REDIS_PASSWORD') ?: null,

    // Channel names
    'channels' => [
        'commands' => 'forex:commands',
        'config' => 'forex:config',
        'status' => 'forex:status',
        'signals' => 'forex:signals',
        'metrics' => 'forex:metrics',
    ],

    // Redis keys
    'keys' => [
        'last_status' => 'forex:agent:last_status',
        'signals_list' => 'forex:agent:signals',
    ],
];