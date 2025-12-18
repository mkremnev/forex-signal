<?php
/**
 * Redis client wrapper for Dashboard integration.
 *
 * Provides singleton access to Redis connection and helper methods
 * for Pub/Sub communication with Agent.
 */

namespace RedisIntegration\Helper;

class RedisClient
{
    private static ?RedisClient $instance = null;
    private ?\Redis $client = null;
    private array $config = [];

    private function __construct()
    {
        $this->loadConfig();
    }

    /**
     * Get singleton instance.
     */
    public static function getInstance(): RedisClient
    {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    /**
     * Load Redis configuration.
     */
    private function loadConfig(): void
    {
        $configPath = COCKPIT_DIR . '/config/redis.php';
        if (file_exists($configPath)) {
            $this->config = require $configPath;
        } else {
            // Default configuration
            $this->config = [
                'host' => getenv('REDIS_HOST') ?: 'redis',
                'port' => (int)(getenv('REDIS_PORT') ?: 6379),
                'db' => 0,
                'password' => null,
            ];
        }
    }

    /**
     * Get Redis client, connecting if necessary.
     *
     * @return \Redis
     * @throws \Exception If connection fails
     */
    public function getClient(): \Redis
    {
        if ($this->client === null) {
            $this->client = new \Redis();

            $connected = $this->client->connect(
                $this->config['host'],
                $this->config['port'],
                5.0 // timeout
            );

            if (!$connected) {
                throw new \Exception('Failed to connect to Redis');
            }

            if (!empty($this->config['password'])) {
                $this->client->auth($this->config['password']);
            }

            if (isset($this->config['db'])) {
                $this->client->select($this->config['db']);
            }
        }

        return $this->client;
    }

    /**
     * Publish message to Redis channel.
     *
     * @param string $channel Channel name
     * @param array $message Message data (will be JSON encoded)
     * @return int Number of subscribers that received the message
     */
    public function publish(string $channel, array $message): int
    {
        $json = json_encode($message, JSON_UNESCAPED_UNICODE);
        return $this->getClient()->publish($channel, $json);
    }

    /**
     * Get value by key.
     *
     * @param string $key Redis key
     * @return string|null Value or null if not found
     */
    public function get(string $key): ?string
    {
        $value = $this->getClient()->get($key);
        return $value === false ? null : $value;
    }

    /**
     * Get JSON value by key.
     *
     * @param string $key Redis key
     * @return array|null Decoded JSON or null
     */
    public function getJson(string $key): ?array
    {
        $value = $this->get($key);
        if ($value === null) {
            return null;
        }
        return json_decode($value, true);
    }

    /**
     * Get list range.
     *
     * @param string $key Redis list key
     * @param int $start Start index
     * @param int $end End index (-1 for all)
     * @return array List of values
     */
    public function lrange(string $key, int $start = 0, int $end = -1): array
    {
        return $this->getClient()->lRange($key, $start, $end);
    }

    /**
     * Get list as JSON decoded array.
     *
     * @param string $key Redis list key
     * @param int $limit Maximum items to return
     * @return array Array of decoded JSON items
     */
    public function getListJson(string $key, int $limit = 50): array
    {
        $items = $this->lrange($key, 0, $limit - 1);
        return array_map(function ($item) {
            return json_decode($item, true);
        }, $items);
    }

    /**
     * Check if Redis is connected.
     *
     * @return bool True if connected
     */
    public function isConnected(): bool
    {
        try {
            return $this->getClient()->ping() === true;
        } catch (\Exception $e) {
            return false;
        }
    }

    /**
     * Get channel name from config.
     *
     * @param string $name Channel identifier
     * @return string Full channel name
     */
    public function getChannel(string $name): string
    {
        return $this->config['channels'][$name] ?? "forex:{$name}";
    }

    /**
     * Get key name from config.
     *
     * @param string $name Key identifier
     * @return string Full key name
     */
    public function getKey(string $name): string
    {
        return $this->config['keys'][$name] ?? "forex:agent:{$name}";
    }

    /**
     * Close Redis connection.
     */
    public function close(): void
    {
        if ($this->client !== null) {
            $this->client->close();
            $this->client = null;
        }
    }
}
