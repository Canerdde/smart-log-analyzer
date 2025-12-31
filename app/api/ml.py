"""
ML/AI API endpoint'leri - Anomali tespiti
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LogEntry

# ML modülü opsiyonel
try:
    from app.ml.anomaly_detection import AnomalyDetector

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("ML modülü bulunamadı (scikit-learn eksik olabilir)")

router = APIRouter()


@router.get("/{file_id}/anomalies")
async def detect_anomalies(
    file_id: int, contamination: float = 0.1, db: Session = Depends(get_db)
):
    """
    Log dosyasında anomali tespit et

    Args:
        file_id: Log dosyası ID'si
        contamination: Anomali oranı tahmini (0.1 = %10)

    Returns:
        Anomali tespit sonuçları
    """
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ML modülü mevcut değil. scikit-learn paketi gerekli.",
        )

    # Log girişlerini getir
    entries = (
        db.query(LogEntry)
        .filter(LogEntry.log_file_id == file_id)
        .order_by(LogEntry.line_number)
        .all()
    )

    if not entries:
        raise HTTPException(status_code=404, detail="Log girişi bulunamadı")

    # Dict formatına çevir
    entries_dict = [
        {
            "line_number": e.line_number,
            "log_level": e.log_level,
            "timestamp": e.timestamp,
            "message": e.message,
            "raw_line": e.raw_line,
        }
        for e in entries
    ]

    # Anomali tespiti
    detector = AnomalyDetector(contamination=contamination)
    summary = detector.get_anomaly_summary(entries_dict)

    return summary
