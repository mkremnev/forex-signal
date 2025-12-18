/**
 * AgentMonitor - Client-side class for monitoring Forex Signal Agent.
 *
 * Features:
 * - Server-Sent Events (SSE) connection for real-time updates
 * - REST API integration for sending commands
 * - Automatic reconnection on connection loss
 * - Initial data loading from Redis
 */

class AgentMonitor {
    /**
     * Initialize Agent Monitor.
     *
     * @param {Object} options Configuration options
     * @param {string} options.sseUrl SSE endpoint URL
     * @param {string} options.apiBaseUrl API base URL
     * @param {Function} options.onStatus Status update callback
     * @param {Function} options.onSignal Signal received callback
     * @param {Function} options.onMetrics Metrics update callback
     * @param {Function} options.onConnectionChange Connection status callback
     * @param {Function} options.onError Error callback
     */
    constructor(options = {}) {
        this.sseUrl = options.sseUrl || '/redis-integration/stream';
        this.apiBaseUrl = options.apiBaseUrl || '/api/redis-integration';

        this.onStatus = options.onStatus || (() => {});
        this.onSignal = options.onSignal || (() => {});
        this.onMetrics = options.onMetrics || (() => {});
        this.onConnectionChange = options.onConnectionChange || (() => {});
        this.onError = options.onError || (() => {});

        this.eventSource = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
    }

    /**
     * Connect to SSE stream.
     */
    connect() {
        if (this.eventSource) {
            this.disconnect();
        }

        try {
            this.eventSource = new EventSource(this.sseUrl);

            this.eventSource.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                this.onConnectionChange(true);
                console.log('AgentMonitor: Connected to SSE stream');
            };

            this.eventSource.onerror = (e) => {
                this.connected = false;
                this.onConnectionChange(false);
                console.warn('AgentMonitor: SSE connection error', e);

                // Close current connection
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }

                // Attempt reconnection
                this.scheduleReconnect();
            };

            // Listen for specific event types
            this.eventSource.addEventListener('connected', (e) => {
                console.log('AgentMonitor: Received connected event', JSON.parse(e.data));
            });

            this.eventSource.addEventListener('status', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.onStatus(data);
                } catch (err) {
                    console.error('AgentMonitor: Failed to parse status', err);
                }
            });

            this.eventSource.addEventListener('signal', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.onSignal(data);
                } catch (err) {
                    console.error('AgentMonitor: Failed to parse signal', err);
                }
            });

            this.eventSource.addEventListener('metrics', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.onMetrics(data);
                } catch (err) {
                    console.error('AgentMonitor: Failed to parse metrics', err);
                }
            });

            this.eventSource.addEventListener('error', (e) => {
                try {
                    const data = JSON.parse(e.data);
                    this.onError(data);
                } catch (err) {
                    // Generic error event
                }
            });

        } catch (err) {
            console.error('AgentMonitor: Failed to create EventSource', err);
            this.scheduleReconnect();
        }
    }

    /**
     * Disconnect from SSE stream.
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.connected = false;
        this.onConnectionChange(false);
    }

    /**
     * Schedule reconnection with exponential backoff.
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('AgentMonitor: Max reconnection attempts reached');
            this.onError({ message: 'Connection lost. Please refresh the page.' });
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`AgentMonitor: Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Send command to Agent.
     *
     * @param {string} action Command action (reload, pause, resume, status)
     * @param {Object} params Optional parameters
     * @returns {Promise<Object>} Response data
     */
    async sendCommand(action, params = {}) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/command`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ action, params }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to send command');
            }

            console.log(`AgentMonitor: Command '${action}' sent`, data);

            // Show notification
            if (window.App && App.ui) {
                App.ui.notify(`Command '${action}' sent successfully`, 'success');
            }

            return data;

        } catch (err) {
            console.error(`AgentMonitor: Failed to send command '${action}'`, err);
            this.onError(err);

            if (window.App && App.ui) {
                App.ui.notify(`Failed to send command: ${err.message}`, 'error');
            }

            throw err;
        }
    }

    /**
     * Update Agent configuration.
     *
     * @param {Object} config Configuration data
     * @returns {Promise<Object>} Response data
     */
    async updateConfig(config) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ config }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to update config');
            }

            console.log('AgentMonitor: Config updated', data);

            if (window.App && App.ui) {
                App.ui.notify('Configuration updated', 'success');
            }

            return data;

        } catch (err) {
            console.error('AgentMonitor: Failed to update config', err);
            this.onError(err);

            if (window.App && App.ui) {
                App.ui.notify(`Failed to update config: ${err.message}`, 'error');
            }

            throw err;
        }
    }

    /**
     * Load initial data from API.
     */
    async loadInitialData() {
        try {
            // Load status
            const statusResponse = await fetch(`${this.apiBaseUrl}/status`);
            if (statusResponse.ok) {
                const status = await statusResponse.json();
                if (status.state !== 'unknown') {
                    this.onStatus(status);
                }
            }

            // Load recent signals
            const signalsResponse = await fetch(`${this.apiBaseUrl}/signals?limit=20`);
            if (signalsResponse.ok) {
                const data = await signalsResponse.json();
                if (data.signals && data.signals.length > 0) {
                    // Process signals in reverse order (oldest first)
                    data.signals.reverse().forEach(signal => {
                        this.onSignal(signal);
                    });
                }
            }

        } catch (err) {
            console.warn('AgentMonitor: Failed to load initial data', err);
        }
    }

    /**
     * Check Redis connection health.
     */
    async checkHealth() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            const data = await response.json();

            const statusEl = document.getElementById('redis-status');
            if (statusEl) {
                if (data.redis === 'connected') {
                    statusEl.innerHTML = '<span class="kiss-color-success">Connected</span>';
                } else {
                    statusEl.innerHTML = `<span class="kiss-color-danger">${data.redis}</span>`;
                    if (data.message) {
                        statusEl.innerHTML += `<div class="kiss-size-small kiss-color-muted">${data.message}</div>`;
                    }
                }
            }

            return data;

        } catch (err) {
            console.error('AgentMonitor: Health check failed', err);

            const statusEl = document.getElementById('redis-status');
            if (statusEl) {
                statusEl.innerHTML = '<span class="kiss-color-danger">Connection Error</span>';
            }
        }
    }
}

// Export for global use
window.AgentMonitor = AgentMonitor;