"""
Performance Metrics API - Response time, throughput, bottleneck tespiti
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import re

from app.database import get_db
from app.models import LogFile, LogEntry
from app.auth import get_current_active_user
from app.models import User

router = APIRouter()


@router.get("/metrics/{file_id}")
async def get_performance_metrics(
    file_id: int,
    start_date: Optional[datetime] = Query(None, description="Başlangıç tarihi"),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Log dosyasından performance metrikleri çıkar

    Metrikler:
    - Response time (ms cinsinden)
    - Throughput (requests/second)
    - Bottleneck detection
    - Error rate
    """
    # Dosya kontrolü
    file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    # Kullanıcı kontrolü
    if current_user.role != "admin" and file.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu dosyaya erişim yetkiniz yok")

    # Log entry'leri al
    query = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)
    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)

    entries = query.order_by(LogEntry.timestamp).all()

    if not entries:
        raise HTTPException(status_code=404, detail="Log girişi bulunamadı")

    # Metrikleri hesapla
    response_times = _extract_response_times(entries)
    throughput = _calculate_throughput(entries)
    error_rate = _calculate_error_rate(entries)
    bottlenecks = _detect_bottlenecks(entries, response_times)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "time_range": {
            "start": entries[0].timestamp.isoformat() if entries[0].timestamp else None,
            "end": entries[-1].timestamp.isoformat() if entries[-1].timestamp else None,
        },
        "response_time": {
            "avg_ms": (
                sum(response_times) / len(response_times) if response_times else 0
            ),
            "min_ms": min(response_times) if response_times else 0,
            "max_ms": max(response_times) if response_times else 0,
            "p50_ms": _percentile(response_times, 50) if response_times else 0,
            "p95_ms": _percentile(response_times, 95) if response_times else 0,
            "p99_ms": _percentile(response_times, 99) if response_times else 0,
            "samples": len(response_times),
        },
        "throughput": throughput,
        "error_rate": error_rate,
        "bottlenecks": bottlenecks,
    }


def _extract_response_times(entries: List[LogEntry]) -> List[float]:
    """Log mesajlarından response time değerlerini çıkar (ms cinsinden)"""
    response_times = []

    # Pattern'ler: "2300ms", "2.3s", "2300", "took 2300ms", "duration: 2.3s"
    patterns = [
        r"(\d+(?:\.\d+)?)\s*ms",  # 2300ms, 2.3 ms
        r"(\d+(?:\.\d+)?)\s*s(?!\w)",  # 2.3s, 1.5 s
        r"took\s+(\d+(?:\.\d+)?)\s*(?:ms|s)",
        r"duration[:\s]+(\d+(?:\.\d+)?)\s*(?:ms|s)",
        r"response[:\s]+(\d+(?:\.\d+)?)\s*(?:ms|s)",
        r"(\d{3,})\s*(?:ms|s)?",  # 3+ haneli sayılar (muhtemelen ms)
    ]

    for entry in entries:
        message = entry.message.lower()
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match)
                    # Eğer pattern'de 's' varsa ve değer küçükse, saniye olabilir
                    if "s" in pattern and value < 100:
                        value = value * 1000  # Saniyeyi ms'ye çevir
                    if 0 < value < 60000:  # Makul aralık (0-60 saniye)
                        response_times.append(value)
                        break  # İlk eşleşmeyi al
                except ValueError:
                    continue

    return response_times


def _calculate_throughput(entries: List[LogEntry]) -> Dict[str, Any]:
    """Throughput hesapla (requests/second)"""
    if not entries or not entries[0].timestamp or not entries[-1].timestamp:
        return {
            "requests_per_second": 0,
            "total_requests": len(entries),
            "time_span_seconds": 0,
        }

    time_span = (entries[-1].timestamp - entries[0].timestamp).total_seconds()
    if time_span == 0:
        time_span = 1  # Sıfıra bölme hatasını önle

    # HTTP request pattern'lerini say
    http_requests = sum(
        1
        for e in entries
        if any(
            keyword in e.message.lower()
            for keyword in [
                "http",
                "request",
                "get ",
                "post ",
                "put ",
                "delete ",
                "api",
            ]
        )
    )

    return {
        "requests_per_second": round(http_requests / time_span, 2),
        "total_requests": http_requests,
        "time_span_seconds": round(time_span, 2),
        "entries_per_second": round(len(entries) / time_span, 2),
    }


def _calculate_error_rate(entries: List[LogEntry]) -> Dict[str, Any]:
    """Error rate hesapla"""
    total = len(entries)
    errors = sum(1 for e in entries if e.log_level == "ERROR")
    warnings = sum(1 for e in entries if e.log_level == "WARNING")

    return {
        "error_count": errors,
        "warning_count": warnings,
        "total_count": total,
        "error_rate_percent": round((errors / total * 100) if total > 0 else 0, 2),
        "warning_rate_percent": round((warnings / total * 100) if total > 0 else 0, 2),
    }


def _detect_bottlenecks(
    entries: List[LogEntry], response_times: List[float]
) -> List[Dict[str, Any]]:
    """Bottleneck tespiti - yavaş işlemleri bul"""
    bottlenecks = []

    if not response_times:
        return []

    # P95 değerini threshold olarak kullan
    threshold = _percentile(response_times, 95)

    # Yavaş işlemleri bul
    slow_operations = []
    response_time_idx = 0

    for entry in entries:
        message = entry.message.lower()
        # Response time pattern'lerini kontrol et
        if any(
            keyword in message for keyword in ["ms", "duration", "took", "response"]
        ):
            if response_time_idx < len(response_times):
                rt = response_times[response_time_idx]
                if rt > threshold:
                    slow_operations.append(
                        {
                            "entry_id": entry.id,
                            "line_number": entry.line_number,
                            "timestamp": (
                                entry.timestamp.isoformat() if entry.timestamp else None
                            ),
                            "message": entry.message[:200],
                            "response_time_ms": rt,
                            "log_level": entry.log_level,
                        }
                    )
                response_time_idx += 1

    # En yavaş 10 işlemi döndür
    slow_operations.sort(key=lambda x: x["response_time_ms"], reverse=True)

    return slow_operations[:10]


def _percentile(data: List[float], percentile: int) -> float:
    """Percentile hesapla"""
    if not data:
        return 0.0

    sorted_data = sorted(data)
    index = int(len(sorted_data) * (percentile / 100))
    if index >= len(sorted_data):
        index = len(sorted_data) - 1
    return sorted_data[index]


@router.get("/comparison")
async def compare_performance(
    file_ids: List[int] = Query(..., description="Karşılaştırılacak dosya ID'leri"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Birden fazla dosyanın performance metriklerini karşılaştır"""
    if len(file_ids) < 2:
        raise HTTPException(status_code=400, detail="En az 2 dosya seçilmelidir")

    # Kullanıcı kontrolü
    if current_user.role != "admin":
        user_file_ids = (
            db.query(LogFile.id).filter(LogFile.user_id == current_user.id).all()
        )
        user_file_ids = [f[0] for f in user_file_ids]
        file_ids = [fid for fid in file_ids if fid in user_file_ids]
        if not file_ids:
            raise HTTPException(
                status_code=403, detail="Bu dosyalara erişim yetkiniz yok"
            )

    comparison = []
    for file_id in file_ids:
        try:
            file = db.query(LogFile).filter(LogFile.id == file_id).first()
            if not file:
                continue

            entries = db.query(LogEntry).filter(LogEntry.log_file_id == file_id).all()
            if not entries:
                continue

            response_times = _extract_response_times(entries)
            throughput = _calculate_throughput(entries)
            error_rate = _calculate_error_rate(entries)

            comparison.append(
                {
                    "file_id": file_id,
                    "filename": file.filename,
                    "avg_response_time_ms": (
                        sum(response_times) / len(response_times)
                        if response_times
                        else 0
                    ),
                    "throughput_rps": throughput["requests_per_second"],
                    "error_rate_percent": error_rate["error_rate_percent"],
                    "total_entries": len(entries),
                }
            )
        except Exception as e:
            continue

    return {
        "comparison": comparison,
        "best_performance": (
            min(comparison, key=lambda x: x["avg_response_time_ms"])
            if comparison
            else None
        ),
        "worst_performance": (
            max(comparison, key=lambda x: x["avg_response_time_ms"])
            if comparison
            else None
        ),
    }
