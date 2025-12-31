from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import LogFile, LogEntry, LogAnalysis
from app.schemas import DashboardStats, LogFileResponse

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Dashboard için genel istatistikleri getir"""

    # Toplam dosya sayısı
    total_files = db.query(func.count(LogFile.id)).scalar() or 0

    # Toplam log girişi sayısı
    total_entries = db.query(func.count(LogEntry.id)).scalar() or 0

    # Toplam hata ve uyarı sayıları
    total_errors = db.query(func.sum(LogAnalysis.error_count)).scalar() or 0
    total_warnings = db.query(func.sum(LogAnalysis.warning_count)).scalar() or 0

    # Son yüklenen dosyalar
    recent_files = (
        db.query(LogFile).order_by(LogFile.uploaded_at.desc()).limit(10).all()
    )

    # Hata trendi (son 10 dosyanın hata sayıları)
    recent_analyses = (
        db.query(LogAnalysis)
        .join(LogFile)
        .order_by(LogFile.uploaded_at.desc())
        .limit(10)
        .all()
    )

    error_trend = [
        {
            "file_id": analysis.log_file_id,
            "filename": analysis.log_file.filename,
            "error_count": analysis.error_count,
            "uploaded_at": (
                analysis.log_file.uploaded_at.isoformat()
                if analysis.log_file.uploaded_at
                else None
            ),
        }
        for analysis in recent_analyses
    ]

    return DashboardStats(
        total_files=total_files,
        total_entries=total_entries,
        total_errors=total_errors,
        total_warnings=total_warnings,
        recent_files=recent_files,
        error_trend=error_trend,
    )
