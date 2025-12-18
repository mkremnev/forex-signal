<?php
/**
 * Simple Redis client using sockets (no php-redis extension).
 *
 * Implements only the commands needed for Dashboard integration.
 */

namespace RedisIntegration\Helper;

class RedisClient
{
    private static ?RedisClient $instance = null;
    private $socket = null;
    private array $config = [];

    private function __construct()
    {
        $this->config = [
            'host' => getenv('REDIS_HOST') ?: 'redis',
            'port' => (int)(getenv('REDIS_PORT') ?: 6379),
            'timeout' => 5,
            'channels' => [
                'commands' => 'forex:commands',
                'config' => 'forex:config',
                'status' => 'forex:status',
                'signals' => 'forex:signals',
                'metrics' => 'forex:metrics',
            ],
            'keys' => [
                'last_status' => 'forex:agent:last_status',
                'signals_list' => 'forex:agent:signals',
            ],
        ];
    }

    public static function getInstance(): RedisClient
    {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function connect(): void
    {
        if ($this->socket !== null) {
            return;
        }

        $this->socket = @fsockopen(
            $this->config['host'],
            $this->config['port'],
            $errno,
            $errstr,
            $this->config['timeout']
        );

        if (!$this->socket) {
            throw new \Exception("Redis connection failed: $errstr ($errno)");
        }

        stream_set_timeout($this->socket, $this->config['timeout']);
    }

    private function sendCommand(array $args): string
    {
        $this->connect();

        // Build RESP protocol command
        $cmd = "*" . count($args) . "\r\n";
        foreach ($args as $arg) {
            $cmd .= "$" . strlen($arg) . "\r\n" . $arg . "\r\n";
        }

        fwrite($this->socket, $cmd);
        return $this->readResponse();
    }

    private function readResponse(): string
    {
        $line = fgets($this->socket);
        if ($line === false) {
            throw new \Exception("Redis read error");
        }

        $type = $line[0];
        $data = trim(substr($line, 1));

        switch ($type) {
            case '+': // Simple string
                return $data;
            case '-': // Error
                throw new \Exception("Redis error: $data");
            case ':': // Integer
                return $data;
            case '$': // Bulk string
                $len = (int)$data;
                if ($len === -1) {
                    return '';
                }
                $bulk = '';
                while (strlen($bulk) < $len) {
                    $bulk .= fread($this->socket, $len - strlen($bulk));
                }
                fgets($this->socket); // Read trailing \r\n
                return $bulk;
            case '*': // Array
                $count = (int)$data;
                if ($count === -1) {
                    return '';
                }
                $results = [];
                for ($i = 0; $i < $count; $i++) {
                    $results[] = $this->readResponse();
                }
                return json_encode($results);
            default:
                return $data;
        }
    }

    public function ping(): bool
    {
        try {
            $response = $this->sendCommand(['PING']);
            return $response === 'PONG';
        } catch (\Exception $e) {
            return false;
        }
    }

    public function get(string $key): ?string
    {
        try {
            $response = $this->sendCommand(['GET', $key]);
            return $response === '' ? null : $response;
        } catch (\Exception $e) {
            return null;
        }
    }

    public function getJson(string $key): ?array
    {
        $value = $this->get($key);
        if ($value === null) {
            return null;
        }
        return json_decode($value, true);
    }

    public function lrange(string $key, int $start = 0, int $end = -1): array
    {
        try {
            $response = $this->sendCommand(['LRANGE', $key, (string)$start, (string)$end]);
            return json_decode($response, true) ?? [];
        } catch (\Exception $e) {
            return [];
        }
    }

    public function getListJson(string $key, int $limit = 50): array
    {
        $items = $this->lrange($key, 0, $limit - 1);
        return array_map(function ($item) {
            return json_decode($item, true);
        }, $items);
    }

    public function publish(string $channel, array $message): int
    {
        $json = json_encode($message, JSON_UNESCAPED_UNICODE);
        try {
            $response = $this->sendCommand(['PUBLISH', $channel, $json]);
            return (int)$response;
        } catch (\Exception $e) {
            return 0;
        }
    }

    public function isConnected(): bool
    {
        return $this->ping();
    }

    public function getChannel(string $name): string
    {
        return $this->config['channels'][$name] ?? "forex:{$name}";
    }

    public function getKey(string $name): string
    {
        return $this->config['keys'][$name] ?? "forex:agent:{$name}";
    }

    public function close(): void
    {
        if ($this->socket !== null) {
            fclose($this->socket);
            $this->socket = null;
        }
    }

    public function __destruct()
    {
        $this->close();
    }
}
