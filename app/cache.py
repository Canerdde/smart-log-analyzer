"""
Redis caching sistemi
Performans iyileştirmesi için analiz sonuçlarını cache'ler
"""

import json
import os
from datetime import timedelta
from typing import Any, Dict, Optional

# Redis opsiyonel
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis modülü bulunamadı, cache devre dışı")
    redis = None

# Redis bağlantısı
redis_client = None


def get_redis_client():
    """Redis client'ı singleton pattern ile döndürür"""
    if not REDIS_AVAILABLE:
        return None

    global redis_client
    if redis_client is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))

        try:
            redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=False,  # Binary mode for JSON
                socket_connect_timeout=5,
            )
            # Bağlantıyı test et
            redis_client.ping()
        except Exception as e:
            print(f"Redis bağlantı hatası: {e}. Cache devre dışı.")
            return None
    return redis_client


def get_cached_analysis(file_id: int) -> Optional[Dict[str, Any]]:
    """
    Cache'den analiz sonuçlarını getir

    Args:
        file_id: Log dosyası ID'si

    Returns:
        Cache'de varsa analiz verisi, yoksa None
    """
    client = get_redis_client()
    if client is None:
        return None

    try:
        cache_key = f"analysis:{file_id}"
        cached_data = client.get(cache_key)

        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Cache okuma hatası: {e}")

    return None


def cache_analysis(file_id: int, analysis_data: Dict[str, Any], ttl: int = 3600):
    """
    Analiz sonuçlarını cache'e kaydet

    Args:
        file_id: Log dosyası ID'si
        analysis_data: Analiz verisi
        ttl: Time to live (saniye), varsayılan 1 saat
    """
    if not REDIS_AVAILABLE:
        return

    client = get_redis_client()
    if client is None:
        return

    try:
        cache_key = f"analysis:{file_id}"
        serialized_data = json.dumps(
            analysis_data, default=str
        )  # datetime için default=str
        client.setex(cache_key, ttl, serialized_data)
    except Exception as e:
        print(f"Cache yazma hatası: {e}")


def invalidate_cache(file_id: int):
    """
    Belirli bir dosyanın cache'ini temizle

    Args:
        file_id: Log dosyası ID'si
    """
    if not REDIS_AVAILABLE:
        return

    client = get_redis_client()
    if client is None:
        return

    try:
        cache_key = f"analysis:{file_id}"
        client.delete(cache_key)
    except Exception as e:
        print(f"Cache silme hatası: {e}")


def get_cached_dashboard_stats() -> Optional[Dict[str, Any]]:
    """Dashboard istatistiklerini cache'den getir"""
    if not REDIS_AVAILABLE:
        return None

    client = get_redis_client()
    if client is None:
        return None

    try:
        cached_data = client.get("dashboard:stats")
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        print(f"Dashboard cache okuma hatası: {e}")

    return None


def cache_dashboard_stats(stats_data: Dict[str, Any], ttl: int = 300):
    """Dashboard istatistiklerini cache'e kaydet (5 dakika)"""
    if not REDIS_AVAILABLE:
        return

    client = get_redis_client()
    if client is None:
        return

    try:
        serialized_data = json.dumps(stats_data, default=str)
        client.setex("dashboard:stats", ttl, serialized_data)
    except Exception as e:
        print(f"Dashboard cache yazma hatası: {e}")


def clear_all_cache():
    """Tüm cache'i temizle (dikkatli kullan!)"""
    if not REDIS_AVAILABLE:
        return

    client = get_redis_client()
    if client is None:
        return

    try:
        client.flushdb()
    except Exception as e:
        print(f"Cache temizleme hatası: {e}")
