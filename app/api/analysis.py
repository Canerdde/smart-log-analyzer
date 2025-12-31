from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.cache import cache_analysis, get_cached_analysis
from app.database import get_db
from app.models import LogAnalysis, LogEntry
from app.pattern_detection import detect_patterns
from app.schemas import LogAnalysisResponse, LogEntryResponse

router = APIRouter()


@router.get("/{file_id}", response_model=LogAnalysisResponse)
async def get_analysis(file_id: int, db: Session = Depends(get_db)):
    """Belirli bir log dosyasının analiz sonuçlarını getir (cache'li)"""
    # Önce cache'den kontrol et
    cached = get_cached_analysis(file_id)
    if cached:
        return cached

    # Cache'de yoksa DB'den getir
    analysis = db.query(LogAnalysis).filter(LogAnalysis.log_file_id == file_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı")

    # Response'a çevir ve cache'le
    analysis_dict = {
        "id": analysis.id,
        "log_file_id": analysis.log_file_id,
        "total_entries": analysis.total_entries,
        "error_count": analysis.error_count,
        "warning_count": analysis.warning_count,
        "info_count": analysis.info_count,
        "debug_count": analysis.debug_count,
        "top_errors": analysis.top_errors,
        "top_warnings": analysis.top_warnings,
        "time_distribution": analysis.time_distribution,
        "ai_comment": analysis.ai_comment,
        "ai_suggestions": analysis.ai_suggestions,
        "analyzed_at": analysis.analyzed_at,
    }
    cache_analysis(file_id, analysis_dict)

    return analysis


@router.get("/{file_id}/entries", response_model=List[LogEntryResponse])
async def get_log_entries(
    file_id: int,
    log_level: Optional[str] = None,
    search: Optional[str] = Query(
        None, description="Mesaj içinde arama (normal veya regex)"
    ),
    search_type: Optional[str] = Query(
        "normal", description="Arama tipi: normal, regex"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Başlangıç tarihi (ISO format)"
    ),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi (ISO format)"),
    and_conditions: Optional[str] = Query(
        None, description="AND koşulları (JSON string)"
    ),
    or_conditions: Optional[str] = Query(
        None, description="OR koşulları (JSON string)"
    ),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Log girişlerini getir - Gelişmiş filtreleme ile
    - log_level: ERROR, WARNING, INFO, DEBUG
    - search: Mesaj içinde arama (normal veya regex)
    - search_type: "normal" veya "regex"
    - start_date: Başlangıç tarihi
    - end_date: Bitiş tarihi
    - and_conditions: JSON string, örn: '{"log_level": "ERROR", "search": "database"}'
    - or_conditions: JSON string, örn: '{"log_level": ["ERROR", "WARNING"]}'
    """
    import json
    import re

    query = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)

    # Log seviyesi filtresi
    if log_level:
        query = query.filter(LogEntry.log_level == log_level.upper())

    # Mesaj içinde arama (normal veya regex)
    if search:
        if search_type == "regex":
            try:
                # Regex pattern'i compile et
                pattern = re.compile(search, re.IGNORECASE)
                # PostgreSQL'de regex kullan (SQLAlchemy ile)
                query = query.filter(LogEntry.message.op("~")(search))
            except re.error:
                # Geçersiz regex ise normal arama yap
                query = query.filter(LogEntry.message.ilike(f"%{search}%"))
        else:
            query = query.filter(LogEntry.message.ilike(f"%{search}%"))

    # AND koşulları
    if and_conditions:
        try:
            conditions = json.loads(and_conditions)
            if isinstance(conditions, dict):
                if "log_level" in conditions:
                    query = query.filter(
                        LogEntry.log_level == conditions["log_level"].upper()
                    )
                if "search" in conditions:
                    search_term = conditions["search"]
                    if conditions.get("search_type") == "regex":
                        try:
                            query = query.filter(LogEntry.message.op("~")(search_term))
                        except:
                            query = query.filter(
                                LogEntry.message.ilike(f"%{search_term}%")
                            )
                    else:
                        query = query.filter(LogEntry.message.ilike(f"%{search_term}%"))
        except (json.JSONDecodeError, Exception) as e:
            print(f"AND conditions parse hatası: {e}")

    # OR koşulları
    if or_conditions:
        try:
            conditions = json.loads(or_conditions)
            if isinstance(conditions, dict):
                from sqlalchemy import or_

                or_filters = []
                if "log_level" in conditions:
                    levels = conditions["log_level"]
                    if isinstance(levels, list):
                        or_filters.append(
                            LogEntry.log_level.in_([l.upper() for l in levels])
                        )
                    else:
                        or_filters.append(LogEntry.log_level == levels.upper())
                if or_filters:
                    query = query.filter(or_(*or_filters))
        except (json.JSONDecodeError, Exception) as e:
            print(f"OR conditions parse hatası: {e}")

    # Tarih aralığı filtresi
    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)

    entries = query.order_by(LogEntry.line_number).offset(skip).limit(limit).all()
    return entries


@router.get("/{file_id}/errors", response_model=List[LogEntryResponse])
async def get_errors(
    file_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Sadece hata loglarını getir"""
    return await get_log_entries(
        file_id, log_level="ERROR", skip=skip, limit=limit, db=db
    )


@router.get("/{file_id}/warnings", response_model=List[LogEntryResponse])
async def get_warnings(
    file_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Sadece uyarı loglarını getir"""
    return await get_log_entries(
        file_id, log_level="WARNING", skip=skip, limit=limit, db=db
    )


@router.get("/{file_id}/patterns")
async def get_patterns(
    file_id: int,
    min_similarity: float = Query(
        0.7, ge=0.0, le=1.0, description="Minimum benzerlik oranı"
    ),
    db: Session = Depends(get_db),
):
    """
    Log dosyasındaki pattern'leri tespit et ve benzer hataları grupla

    Returns:
        - patterns: Tespit edilen pattern'ler (URL, IP, HTTP status, SQL, API endpoint, Exception)
        - groups: Benzer hataların grupları
        - total_patterns: Toplam pattern sayısı
        - total_groups: Toplam grup sayısı
    """
    # Log entries'leri al
    entries = db.query(LogEntry).filter(LogEntry.log_file_id == file_id).all()

    if not entries:
        return {
            "patterns": [],
            "groups": [],
            "total_patterns": 0,
            "total_groups": 0,
            "analyzed_logs": 0,
        }

    # Dict formatına çevir
    entries_dict = [
        {
            "id": entry.id,
            "log_level": entry.log_level,
            "message": entry.message,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "line_number": entry.line_number,
        }
        for entry in entries
    ]

    # Pattern detection
    result = detect_patterns(entries_dict, min_similarity)

    return result


@router.get("/{file_id}/timeline")
async def get_timeline(
    file_id: int,
    start_date: Optional[datetime] = Query(
        None, description="Başlangıç tarihi (ISO format)"
    ),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi (ISO format)"),
    log_level: Optional[str] = Query(None, description="Log seviyesi filtresi"),
    group_by: str = Query("minute", description="Gruplama: second, minute, hour, day"),
    db: Session = Depends(get_db),
):
    """
    Log entry'lerini timeline formatında getir
    - Zaman çizelgesi görünümü için timestamp'lere göre gruplandırılmış veri
    - Olaylar arası ilişki analizi
    """
    from collections import defaultdict
    from datetime import timedelta

    # Log entries'leri al
    query = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)

    if log_level:
        query = query.filter(LogEntry.log_level == log_level.upper())

    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)

    entries = query.order_by(LogEntry.timestamp).all()

    if not entries:
        return {
            "timeline_data": [],
            "events": [],
            "relationships": [],
            "time_range": {"start": None, "end": None},
        }

    # Timeline data - timestamp'lere göre grupla
    timeline_data = defaultdict(
        lambda: {
            "timestamp": None,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "debug_count": 0,
            "total_count": 0,
            "events": [],
        }
    )

    # Events listesi
    events = []

    # Timestamp range
    timestamps = [e.timestamp for e in entries if e.timestamp]
    time_range = {
        "start": min(timestamps).isoformat() if timestamps else None,
        "end": max(timestamps).isoformat() if timestamps else None,
    }

    for entry in entries:
        if not entry.timestamp:
            continue

        # Gruplama için timestamp'i yuvarla
        ts = entry.timestamp
        if group_by == "second":
            rounded_ts = ts.replace(microsecond=0)
        elif group_by == "minute":
            rounded_ts = ts.replace(second=0, microsecond=0)
        elif group_by == "hour":
            rounded_ts = ts.replace(minute=0, second=0, microsecond=0)
        elif group_by == "day":
            rounded_ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            rounded_ts = ts.replace(second=0, microsecond=0)

        ts_key = rounded_ts.isoformat()

        # Timeline data'yı güncelle
        if ts_key not in timeline_data:
            timeline_data[ts_key]["timestamp"] = rounded_ts.isoformat()

        timeline_data[ts_key][f"{entry.log_level.lower()}_count"] += 1
        timeline_data[ts_key]["total_count"] += 1

        # Event ekle
        event = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "log_level": entry.log_level,
            "message": (
                entry.message[:100] + "..."
                if len(entry.message) > 100
                else entry.message
            ),
            "full_message": entry.message,
            "line_number": entry.line_number,
        }
        timeline_data[ts_key]["events"].append(event)
        events.append(event)

    # Timeline data'yı listeye çevir ve sırala
    timeline_list = sorted(
        [
            {"timestamp": v["timestamp"], **{k: v[k] for k in v if k != "timestamp"}}
            for v in timeline_data.values()
        ],
        key=lambda x: x["timestamp"],
    )

    # Relationships - benzer mesajları grupla (basit bir yaklaşım)
    relationships = []
    message_groups = defaultdict(list)

    for entry in entries:
        if entry.timestamp:
            # Mesajın ilk 50 karakterini key olarak kullan (basit gruplama)
            message_key = entry.message[:50].strip()
            if message_key:
                message_groups[message_key].append(
                    {
                        "id": entry.id,
                        "timestamp": entry.timestamp.isoformat(),
                        "log_level": entry.log_level,
                        "line_number": entry.line_number,
                    }
                )

    # 2'den fazla benzer mesaj varsa relationship olarak ekle
    for message_key, occurrences in message_groups.items():
        if len(occurrences) >= 2:
            relationships.append(
                {
                    "pattern": message_key,
                    "count": len(occurrences),
                    "log_level": occurrences[0]["log_level"],
                    "occurrences": sorted(occurrences, key=lambda x: x["timestamp"]),
                }
            )

    # Relationships'i count'a göre sırala
    relationships.sort(key=lambda x: x["count"], reverse=True)

    return {
        "timeline_data": timeline_list,
        "events": events[:1000],  # İlk 1000 event (performans için)
        "relationships": relationships[:50],  # İlk 50 relationship
        "time_range": time_range,
        "total_events": len(events),
    }
