"""
Prometheus monitoring metrics
"""
from fastapi import Response

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("Prometheus client bulunamadı, monitoring devre dışı")
    # Dummy classes
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Gauge:
        def __init__(self, *args, **kwargs): pass
    def generate_latest(): return b""

import time

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Business metrics
logs_uploaded_total = Counter(
    'logs_uploaded_total',
    'Total log files uploaded'
)

logs_analyzed_total = Counter(
    'logs_analyzed_total',
    'Total log files analyzed'
)

errors_detected_total = Counter(
    'errors_detected_total',
    'Total errors detected in logs',
    ['log_file_id']
)

# System metrics
active_connections = Gauge(
    'active_connections',
    'Number of active database connections'
)

cache_hits = Counter(
    'cache_hits_total',
    'Total cache hits'
)

cache_misses = Counter(
    'cache_misses_total',
    'Total cache misses'
)

def get_metrics() -> Response:
    """Prometheus metrics endpoint"""
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="# Prometheus client not available",
            media_type="text/plain"
        )
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )

