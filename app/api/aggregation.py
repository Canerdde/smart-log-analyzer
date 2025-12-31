"""
Log Aggregation API - Birden fazla kaynaktan log toplama ve merkezi yönetim
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import LogFile, LogEntry
from app.schemas import LogFileResponse
from app.auth import get_current_active_user, require_role
from app.models import User

router = APIRouter()


@router.get("/sources", response_model=List[Dict[str, Any]])
async def list_log_sources(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Tüm log kaynaklarını listele (dosya bazlı)"""
    # Kullanıcı bazlı filtreleme (admin tüm dosyaları görebilir)
    if current_user.role == "admin":
        files = db.query(LogFile).all()
    else:
        files = db.query(LogFile).filter(LogFile.user_id == current_user.id).all()

    # Kaynakları grupla (şimdilik dosya bazlı, gelecekte remote source eklenebilir)
    sources = {}
    for file in files:
        source_key = f"file_{file.id}"
        if source_key not in sources:
            sources[source_key] = {
                "source_id": source_key,
                "source_type": "file",
                "name": file.filename,
                "file_id": file.id,
                "total_entries": file.total_lines,
                "last_updated": file.uploaded_at.isoformat(),
                "status": file.status,
            }

    return list(sources.values())


@router.get("/aggregated", response_model=Dict[str, Any])
async def get_aggregated_logs(
    source_ids: Optional[str] = Query(
        None, description="Virgülle ayrılmış source ID'ler (örn: file_1,file_2)"
    ),
    log_level: Optional[str] = Query(None, description="Log seviyesi filtresi"),
    start_date: Optional[datetime] = Query(None, description="Başlangıç tarihi"),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi"),
    limit: int = Query(1000, ge=1, le=10000, description="Maksimum log sayısı"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Birden fazla kaynaktan logları topla ve birleştir"""

    # Source ID'leri parse et
    source_list = []
    if source_ids:
        source_list = [s.strip() for s in source_ids.split(",")]

    # Dosya ID'lerini çıkar
    file_ids = []
    for source_id in source_list:
        if source_id.startswith("file_"):
            try:
                file_id = int(source_id.replace("file_", ""))
                file_ids.append(file_id)
            except ValueError:
                continue

    # Kullanıcı bazlı filtreleme
    query = db.query(LogEntry)
    if current_user.role != "admin":
        # Kullanıcının dosyalarını filtrele
        user_file_ids = (
            db.query(LogFile.id).filter(LogFile.user_id == current_user.id).all()
        )
        user_file_ids = [f[0] for f in user_file_ids]
        if file_ids:
            file_ids = [fid for fid in file_ids if fid in user_file_ids]
        else:
            file_ids = user_file_ids

    if file_ids:
        query = query.filter(LogEntry.log_file_id.in_(file_ids))

    # Log seviyesi filtresi
    if log_level:
        query = query.filter(LogEntry.log_level == log_level.upper())

    # Tarih aralığı filtresi
    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)

    # Logları al ve sırala
    entries = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()

    # Kaynak bazlı istatistikler
    source_stats = {}
    for entry in entries:
        source_key = f"file_{entry.log_file_id}"
        if source_key not in source_stats:
            source_stats[source_key] = {
                "source_id": source_key,
                "total_entries": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "debug_count": 0,
            }

        source_stats[source_key]["total_entries"] += 1
        if entry.log_level == "ERROR":
            source_stats[source_key]["error_count"] += 1
        elif entry.log_level == "WARNING":
            source_stats[source_key]["warning_count"] += 1
        elif entry.log_level == "INFO":
            source_stats[source_key]["info_count"] += 1
        elif entry.log_level == "DEBUG":
            source_stats[source_key]["debug_count"] += 1

    # Response formatı
    return {
        "total_entries": len(entries),
        "sources": list(source_stats.values()),
        "entries": [
            {
                "id": entry.id,
                "source_id": f"file_{entry.log_file_id}",
                "log_level": entry.log_level,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "message": entry.message,
                "line_number": entry.line_number,
                "raw_line": entry.raw_line,
            }
            for entry in entries
        ],
        "filters": {
            "source_ids": source_list,
            "log_level": log_level,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }


@router.get("/stats", response_model=Dict[str, Any])
async def get_aggregation_stats(
    source_ids: Optional[str] = Query(
        None, description="Virgülle ayrılmış source ID'ler"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Toplanan loglar için istatistikler"""

    # Source ID'leri parse et
    file_ids = []
    if source_ids:
        for source_id in source_ids.split(","):
            source_id = source_id.strip()
            if source_id.startswith("file_"):
                try:
                    file_id = int(source_id.replace("file_", ""))
                    file_ids.append(file_id)
                except ValueError:
                    continue

    # Kullanıcı bazlı filtreleme
    if current_user.role != "admin":
        user_file_ids = (
            db.query(LogFile.id).filter(LogFile.user_id == current_user.id).all()
        )
        user_file_ids = [f[0] for f in user_file_ids]
        if file_ids:
            file_ids = [fid for fid in file_ids if fid in user_file_ids]
        else:
            file_ids = user_file_ids

    # İstatistikleri hesapla
    query = db.query(LogEntry)
    if file_ids:
        query = query.filter(LogEntry.log_file_id.in_(file_ids))

    total_entries = query.count()
    error_count = query.filter(LogEntry.log_level == "ERROR").count()
    warning_count = query.filter(LogEntry.log_level == "WARNING").count()
    info_count = query.filter(LogEntry.log_level == "INFO").count()
    debug_count = query.filter(LogEntry.log_level == "DEBUG").count()

    # Zaman bazlı dağılım
    time_distribution = {}
    entries_with_time = query.filter(LogEntry.timestamp.isnot(None)).all()
    for entry in entries_with_time:
        if entry.timestamp:
            hour = entry.timestamp.hour
            time_distribution[str(hour)] = time_distribution.get(str(hour), 0) + 1

    return {
        "total_entries": total_entries,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "debug_count": debug_count,
        "time_distribution": time_distribution,
        "sources_count": len(file_ids) if file_ids else 0,
    }
