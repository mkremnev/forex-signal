<kiss-container class="kiss-margin-large">
    <ul class="kiss-breadcrumbs">
        <li><a href="<?= $this->route('/') ?>">Home</a></li>
        <li><span>Agent Monitor</span></li>
    </ul>

    <div class="kiss-margin-large-top kiss-flex kiss-flex-middle">
        <div class="kiss-flex-1">
            <div class="kiss-size-4 kiss-text-bold">Agent Monitor</div>
            <div class="kiss-color-muted kiss-margin-small-top">
                Real-time monitoring and control of Forex Signal Agent
            </div>
        </div>
        <div>
            <span id="connection-status" class="kiss-badge kiss-badge-outline">Disconnected</span>
        </div>
    </div>

    <!-- Status Card -->
    <kiss-card class="kiss-margin-large-top kiss-padding">
        <div class="kiss-flex kiss-flex-middle kiss-margin-bottom">
            <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/activity.svg') ?>" width="24" height="24"></kiss-svg>
            <span class="kiss-size-5 kiss-text-bold kiss-margin-small-left">Agent Status</span>
        </div>

        <div id="agent-status" class="kiss-grid kiss-grid-match" gap="small" cols="4">
            <div>
                <div class="kiss-color-muted kiss-size-small">State</div>
                <div id="status-state" class="kiss-size-4 kiss-text-bold">-</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Uptime</div>
                <div id="status-uptime" class="kiss-size-4">-</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Last Cycle</div>
                <div id="status-last-cycle" class="kiss-size-4">-</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Errors</div>
                <div id="status-errors" class="kiss-size-4">0</div>
            </div>
        </div>

        <div class="kiss-margin-top kiss-flex kiss-flex-middle" gap="small">
            <button id="btn-pause" class="kiss-button kiss-button-small kiss-button-outline" onclick="agentMonitor.sendCommand('pause')">
                <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/pause.svg') ?>" width="16" height="16"></kiss-svg>
                Pause
            </button>
            <button id="btn-resume" class="kiss-button kiss-button-small kiss-button-primary" onclick="agentMonitor.sendCommand('resume')">
                <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/play.svg') ?>" width="16" height="16"></kiss-svg>
                Resume
            </button>
            <button id="btn-reload" class="kiss-button kiss-button-small kiss-button-outline" onclick="agentMonitor.sendCommand('reload')">
                <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/refresh-cw.svg') ?>" width="16" height="16"></kiss-svg>
                Reload Config
            </button>
            <button id="btn-status" class="kiss-button kiss-button-small kiss-button-outline" onclick="agentMonitor.sendCommand('status')">
                Request Status
            </button>
        </div>
    </kiss-card>

    <!-- Metrics Card -->
    <kiss-card class="kiss-margin-large-top kiss-padding">
        <div class="kiss-flex kiss-flex-middle kiss-margin-bottom">
            <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/bar-chart.svg') ?>" width="24" height="24"></kiss-svg>
            <span class="kiss-size-5 kiss-text-bold kiss-margin-small-left">Performance Metrics</span>
        </div>

        <div id="agent-metrics" class="kiss-grid kiss-grid-match" gap="small" cols="4">
            <div>
                <div class="kiss-color-muted kiss-size-small">Pairs Processed</div>
                <div id="metrics-pairs" class="kiss-size-4 kiss-text-bold">0</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Cycle Duration</div>
                <div id="metrics-duration" class="kiss-size-4">-</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Signals Generated</div>
                <div id="metrics-signals" class="kiss-size-4">0</div>
            </div>
            <div>
                <div class="kiss-color-muted kiss-size-small">Errors in Cycle</div>
                <div id="metrics-errors" class="kiss-size-4">0</div>
            </div>
        </div>
    </kiss-card>

    <!-- Recent Signals Card -->
    <kiss-card class="kiss-margin-large-top kiss-padding">
        <div class="kiss-flex kiss-flex-middle kiss-margin-bottom">
            <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/bell.svg') ?>" width="24" height="24"></kiss-svg>
            <span class="kiss-size-5 kiss-text-bold kiss-margin-small-left">Recent Signals</span>
            <span id="signals-count" class="kiss-badge kiss-margin-small-left">0</span>
        </div>

        <div id="signals-list" class="kiss-margin-top">
            <div class="kiss-color-muted kiss-text-center kiss-padding">
                No signals yet. Waiting for data...
            </div>
        </div>
    </kiss-card>

    <!-- Redis Connection Card -->
    <kiss-card class="kiss-margin-large-top kiss-padding">
        <div class="kiss-flex kiss-flex-middle kiss-margin-bottom">
            <kiss-svg src="<?= $this->pathToUrl('system:assets/icons/database.svg') ?>" width="24" height="24"></kiss-svg>
            <span class="kiss-size-5 kiss-text-bold kiss-margin-small-left">Redis Connection</span>
        </div>

        <div id="redis-status" class="kiss-color-muted">
            Checking connection...
        </div>
    </kiss-card>
</kiss-container>

<script>
    // Initialize Agent Monitor when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        window.agentMonitor = new AgentMonitor({
            sseUrl: '<?= $this->routeUrl('/redis-integration/stream') ?>',
            apiBaseUrl: '<?= $this->routeUrl('/api/redis-integration') ?>',
            onStatus: updateStatus,
            onSignal: addSignal,
            onMetrics: updateMetrics,
            onConnectionChange: updateConnectionStatus,
            onError: handleError
        });

        // Connect to SSE stream
        agentMonitor.connect();

        // Load initial data
        agentMonitor.loadInitialData();

        // Check Redis health
        agentMonitor.checkHealth();
    });

    function updateStatus(data) {
        const payload = data.payload || data;

        document.getElementById('status-state').textContent = payload.state || '-';
        document.getElementById('status-state').className = getStateClass(payload.state);

        if (payload.uptime_seconds) {
            document.getElementById('status-uptime').textContent = formatUptime(payload.uptime_seconds);
        }

        if (payload.last_cycle_at) {
            document.getElementById('status-last-cycle').textContent = formatTime(payload.last_cycle_at);
        }

        document.getElementById('status-errors').textContent = payload.error_count || '0';

        // Update button states
        updateButtons(payload.state);
    }

    function updateMetrics(data) {
        const payload = data.payload || data;

        document.getElementById('metrics-pairs').textContent = payload.pairs_processed || '0';
        document.getElementById('metrics-duration').textContent =
            payload.cycle_duration_ms ? `${payload.cycle_duration_ms.toFixed(0)}ms` : '-';
        document.getElementById('metrics-signals').textContent = payload.signals_generated || '0';
        document.getElementById('metrics-errors').textContent = payload.errors_in_cycle || '0';
    }

    function addSignal(data) {
        const payload = data.payload || data;
        const list = document.getElementById('signals-list');
        const count = document.getElementById('signals-count');

        // Remove placeholder if present
        if (list.querySelector('.kiss-color-muted')) {
            list.innerHTML = '';
        }

        // Create signal element
        const item = document.createElement('div');
        item.className = 'kiss-flex kiss-flex-middle kiss-padding-small kiss-margin-small-bottom';
        item.style.background = 'var(--kiss-color-muted-contrast)';
        item.style.borderRadius = '4px';
        item.style.borderLeft = payload.importance >= 2 ? '3px solid var(--kiss-color-danger)' : '3px solid var(--kiss-color-primary)';

        item.innerHTML = `
            <div class="kiss-flex-1">
                <div class="kiss-text-bold">${escapeHtml(payload.symbol)} (${escapeHtml(payload.timeframe)})</div>
                <div class="kiss-color-muted kiss-size-small">${escapeHtml(payload.message)}</div>
            </div>
            <div class="kiss-size-small kiss-color-muted">
                ${formatTime(data.timestamp)}
            </div>
        `;

        // Prepend to list
        list.insertBefore(item, list.firstChild);

        // Limit to 20 items
        while (list.children.length > 20) {
            list.removeChild(list.lastChild);
        }

        // Update count
        count.textContent = list.children.length;
    }

    function updateConnectionStatus(connected) {
        const badge = document.getElementById('connection-status');
        if (connected) {
            badge.textContent = 'Connected';
            badge.className = 'kiss-badge kiss-badge-success';
        } else {
            badge.textContent = 'Disconnected';
            badge.className = 'kiss-badge kiss-badge-outline';
        }
    }

    function updateButtons(state) {
        const pauseBtn = document.getElementById('btn-pause');
        const resumeBtn = document.getElementById('btn-resume');

        if (state === 'paused') {
            pauseBtn.disabled = true;
            resumeBtn.disabled = false;
        } else if (state === 'running') {
            pauseBtn.disabled = false;
            resumeBtn.disabled = true;
        } else {
            pauseBtn.disabled = false;
            resumeBtn.disabled = false;
        }
    }

    function handleError(error) {
        console.error('Agent Monitor error:', error);
        App.ui.notify('Connection error. Retrying...', 'warning');
    }

    function getStateClass(state) {
        const classes = {
            'running': 'kiss-size-4 kiss-text-bold kiss-color-success',
            'paused': 'kiss-size-4 kiss-text-bold kiss-color-warning',
            'error': 'kiss-size-4 kiss-text-bold kiss-color-danger',
            'starting': 'kiss-size-4 kiss-text-bold kiss-color-primary',
            'stopping': 'kiss-size-4 kiss-text-bold kiss-color-muted',
        };
        return classes[state] || 'kiss-size-4 kiss-text-bold';
    }

    function formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        }
        return `${minutes}m`;
    }

    function formatTime(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
</script>
