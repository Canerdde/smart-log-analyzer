"""
Log Comparison API - İki log dosyasını karşılaştırma
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from collections import Counter

from app.database import get_db
from app.models import LogFile, LogEntry, LogAnalysis
from app.schemas import LogComparisonRequest, LogComparisonResponse, LogFileResponse

router = APIRouter()

@router.post("/compare", response_model=LogComparisonResponse)
async def compare_logs(
    request: LogComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    İki log dosyasını karşılaştır
    
    Karşılaştırma:
    - Toplam satır sayısı farkı
    - Hata/uyarı sayıları
    - Ortak hatalar
    - Sadece bir dosyada olan hatalar
    - Pattern değişiklikleri
    """
    file_1 = db.query(LogFile).filter(LogFile.id == request.file_id_1).first()
    file_2 = db.query(LogFile).filter(LogFile.id == request.file_id_2).first()
    
    if not file_1 or not file_2:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Analizleri getir
    analysis_1 = db.query(LogAnalysis).filter(
        LogAnalysis.log_file_id == request.file_id_1
    ).first()
    analysis_2 = db.query(LogAnalysis).filter(
        LogAnalysis.log_file_id == request.file_id_2
    ).first()
    
    if not analysis_1 or not analysis_2:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı")
    
    # Hata mesajlarını getir
    errors_1 = db.query(LogEntry).filter(
        LogEntry.log_file_id == request.file_id_1,
        LogEntry.log_level == "ERROR"
    ).all()
    
    errors_2 = db.query(LogEntry).filter(
        LogEntry.log_file_id == request.file_id_2,
        LogEntry.log_level == "ERROR"
    ).all()
    
    # Hata mesajlarını normalize et (ilk 100 karakter)
    errors_1_normalized = [e.message[:100].strip() for e in errors_1]
    errors_2_normalized = [e.message[:100].strip() for e in errors_2]
    
    errors_1_set = set(errors_1_normalized)
    errors_2_set = set(errors_2_normalized)
    
    # Ortak hatalar
    common_errors = list(errors_1_set & errors_2_set)
    common_errors_with_count = []
    for error in common_errors:
        count_1 = errors_1_normalized.count(error)
        count_2 = errors_2_normalized.count(error)
        common_errors_with_count.append({
            "message": error,
            "count_in_file_1": count_1,
            "count_in_file_2": count_2,
            "difference": count_2 - count_1
        })
    
    # Sadece file_1'de olanlar
    unique_to_file_1 = list(errors_1_set - errors_2_set)
    unique_to_file_1_with_count = []
    for error in unique_to_file_1[:20]:  # İlk 20
        count = errors_1_normalized.count(error)
        unique_to_file_1_with_count.append({
            "message": error,
            "count": count
        })
    
    # Sadece file_2'de olanlar
    unique_to_file_2 = list(errors_2_set - errors_1_set)
    unique_to_file_2_with_count = []
    for error in unique_to_file_2[:20]:  # İlk 20
        count = errors_2_normalized.count(error)
        unique_to_file_2_with_count.append({
            "message": error,
            "count": count
        })
    
    # Farklar
    differences = {
        "total_lines_diff": file_2.total_lines - file_1.total_lines,
        "error_count_diff": analysis_2.error_count - analysis_1.error_count,
        "warning_count_diff": analysis_2.warning_count - analysis_1.warning_count,
        "total_entries_diff": analysis_2.total_entries - analysis_1.total_entries,
        "common_errors_count": len(common_errors),
        "unique_to_file_1_count": len(unique_to_file_1),
        "unique_to_file_2_count": len(unique_to_file_2)
    }
    
    return LogComparisonResponse(
        file_1=file_1,
        file_2=file_2,
        differences=differences,
        common_errors=common_errors_with_count[:20],  # İlk 20
        unique_to_file_1=unique_to_file_1_with_count,
        unique_to_file_2=unique_to_file_2_with_count
    )

