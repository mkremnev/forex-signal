"""Health monitoring module for the forex signal agent."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any
import threading


@dataclass
class ProcessingMetrics:
    symbol: str
    timeframe: str
    processing_time: float
    events_generated: int
    timestamp: datetime


class HealthMonitor:
    """Monitors the health status of the forex signal agent."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.last_successful_cycle = None
        self.error_count = 0
        self.metrics = []
        self.lock = threading.Lock()
        
    def record_successful_cycle(self):
        """Record a successful processing cycle."""
        self.last_successful_cycle = datetime.now()
        
    def record_error(self):
        """Record an error occurrence."""
        self.error_count += 1
        
    def add_metrics(self, metrics: ProcessingMetrics):
        """Add processing metrics."""
        with self.lock:
            self.metrics.append(metrics)
            
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        uptime = datetime.now() - self.start_time
        with self.lock:
            if not self.metrics:
                avg_processing_time = 0
                total_events = 0
            else:
                total_processing_time = sum(m.processing_time for m in self.metrics)
                avg_processing_time = total_processing_time / len(self.metrics)
                total_events = sum(m.events_generated for m in self.metrics)
        
        return {
            "status": "healthy" if self.error_count < 10 else "degraded",
            "uptime": uptime.total_seconds(),
            "last_successful_cycle": self.last_successful_cycle.isoformat() if self.last_successful_cycle else None,
            "error_count": self.error_count,
            "avg_processing_time": avg_processing_time,
            "total_events_generated": total_events,
            "timestamp": datetime.now().isoformat()
        }