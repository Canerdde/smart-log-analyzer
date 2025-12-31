from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import logs, analysis, dashboard
from app.monitoring import get_metrics, http_requests_total, http_request_duration
from starlette.middleware.base import BaseHTTPMiddleware
import time

from app.database import engine, Base

# Veritabanı tablolarını oluştur
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Log Analyzer API",
    description="Akıllı log analiz ve izleme sistemi API dokümantasyonu",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static dosyalar için (frontend)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# API route'ları
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

# Export modülü opsiyonel
try:
    from app.api import export
    app.include_router(export.router, prefix="/api/export", tags=["Export"])
except ImportError:
    print("Export modülü bulunamadı, PDF/CSV export devre dışı")

# ML modülü opsiyonel
try:
    from app.api import ml
    app.include_router(ml.router, prefix="/api/ml", tags=["ML/AI"])
except ImportError:
    print("ML modülü bulunamadı, anomali tespiti devre dışı")

# Real-time streaming (WebSocket)
from app.api import stream
app.include_router(stream.router, prefix="/api", tags=["Streaming"])

# Saved searches
from app.api import saved_searches
from app.api import search_history
app.include_router(saved_searches.router, prefix="/api/saved-searches", tags=["Saved Searches"])
app.include_router(search_history.router, prefix="/api/search-history", tags=["Search History"])

# Alerts
from app.api import alerts
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])

# Comments
from app.api import comments
app.include_router(comments.router, prefix="/api", tags=["Comments"])

# Favorites
from app.api import favorites
app.include_router(favorites.router, prefix="/api/favorites", tags=["Favorites"])

# Comparison
from app.api import comparison
app.include_router(comparison.router, prefix="/api/analysis", tags=["Comparison"])

# Authentication
from app.api import auth
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])

# Log Aggregation
from app.api import aggregation
app.include_router(aggregation.router, prefix="/api/aggregation", tags=["Log Aggregation"])

# Log Correlation
from app.api import correlation
app.include_router(correlation.router, prefix="/api/correlation", tags=["Log Correlation"])

# Performance Metrics
from app.api import performance
app.include_router(performance.router, prefix="/api/performance", tags=["Performance Metrics"])

# Integrations
from app.api import integrations
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])

# Tags and Categories
from app.api import tags
app.include_router(tags.router, prefix="/api/tags", tags=["Tags & Categories"])

@app.get("/")
async def root():
    """Ana sayfa - frontend'i döndür"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "Smart Log Analyzer API", "docs": "/api/docs"}

@app.get("/health")
async def health_check():
    """Sağlık kontrolü"""
    return {"status": "healthy", "service": "Smart Log Analyzer"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return get_metrics()

# Monitoring middleware (opsiyonel - prometheus yoksa çalışmaz)
try:
    @app.middleware("http")
    async def monitoring_middleware(request, call_next):
        """HTTP isteklerini izle ve metrikleri topla"""
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status = response.status_code
        
        # Metrikleri kaydet (eğer prometheus mevcutsa)
        try:
            http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
            http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)
        except:
            pass  # Prometheus yoksa sessizce devam et
        
        return response
except:
    pass  # Monitoring modülü yoksa devam et


