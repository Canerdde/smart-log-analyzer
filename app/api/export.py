"""
Export API endpoint'leri
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import LogAnalysis, LogFile, LogEntry

# Export modülü opsiyonel
try:
    from app.export import (
        export_analysis_to_pdf, 
        export_analysis_to_csv, 
        export_analysis_to_excel,
        export_logs_to_json,
        export_logs_to_xml
    )
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    print("Export modülü bulunamadı (reportlab/openpyxl eksik), PDF/CSV/Excel export devre dışı")

router = APIRouter()

@router.get("/{file_id}/pdf")
async def export_pdf(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Analiz sonuçlarını PDF olarak export et"""
    if not EXPORT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF export mevcut değil. reportlab paketi gerekli."
        )
    
    # Analiz ve dosya bilgilerini getir
    analysis = db.query(LogAnalysis).filter(
        LogAnalysis.log_file_id == file_id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı")
    
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Log girişlerini getir
    entries = db.query(LogEntry).filter(
        LogEntry.log_file_id == file_id
    ).order_by(LogEntry.line_number).all()
    
    return export_analysis_to_pdf(analysis, log_file, entries)

@router.get("/{file_id}/csv")
async def export_csv(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Analiz sonuçlarını CSV olarak export et"""
    if not EXPORT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="CSV export mevcut değil. reportlab paketi gerekli."
        )
    
    # Analiz ve dosya bilgilerini getir
    analysis = db.query(LogAnalysis).filter(
        LogAnalysis.log_file_id == file_id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı")
    
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Log girişlerini getir
    entries = db.query(LogEntry).filter(
        LogEntry.log_file_id == file_id
    ).order_by(LogEntry.line_number).all()
    
    return export_analysis_to_csv(analysis, log_file, entries)

@router.get("/{file_id}/excel")
async def export_excel(
    file_id: int,
    db: Session = Depends(get_db)
):
    """Analiz sonuçlarını Excel olarak export et"""
    if not EXPORT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Excel export mevcut değil. openpyxl paketi gerekli."
        )
    
    # Analiz ve dosya bilgilerini getir
    analysis = db.query(LogAnalysis).filter(
        LogAnalysis.log_file_id == file_id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analiz bulunamadı")
    
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Log girişlerini getir
    entries = db.query(LogEntry).filter(
        LogEntry.log_file_id == file_id
    ).order_by(LogEntry.line_number).all()
    
    return export_analysis_to_excel(analysis, log_file, entries)

@router.get("/{file_id}/json")
async def export_json(
    file_id: int,
    include_analysis: bool = False,
    log_level: Optional[str] = None,
    search: Optional[str] = None,
    search_type: str = "normal",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Log girişlerini JSON formatında export et (filtrelenmiş olabilir)
    
    Query Parameters:
        include_analysis: Analiz sonuçlarını da dahil et (default: False)
        log_level: Log seviyesi filtresi (ERROR, WARNING, INFO, DEBUG)
        search: Mesaj içinde arama
        search_type: "normal" veya "regex"
        start_date: Başlangıç tarihi (ISO format)
        end_date: Bitiş tarihi (ISO format)
    """
    
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Filtrelenmiş log girişlerini getir
    query = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)
    
    if log_level:
        query = query.filter(LogEntry.log_level == log_level.upper())
    
    if search:
        if search_type == "regex":
            import re
            try:
                query = query.filter(LogEntry.message.op('~')(search))
            except:
                query = query.filter(LogEntry.message.ilike(f"%{search}%"))
        else:
            query = query.filter(LogEntry.message.ilike(f"%{search}%"))
    
    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)
    
    entries = query.order_by(LogEntry.line_number).all()
    
    # Analiz (opsiyonel)
    analysis = None
    if include_analysis:
        analysis = db.query(LogAnalysis).filter(
            LogAnalysis.log_file_id == file_id
        ).first()
    
    return export_logs_to_json(log_file, entries, include_analysis, analysis)

@router.get("/{file_id}/xml")
async def export_xml(
    file_id: int,
    include_analysis: bool = False,
    log_level: Optional[str] = None,
    search: Optional[str] = None,
    search_type: str = "normal",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """
    Log girişlerini XML formatında export et (filtrelenmiş olabilir)
    
    Query Parameters:
        include_analysis: Analiz sonuçlarını da dahil et (default: False)
        log_level: Log seviyesi filtresi (ERROR, WARNING, INFO, DEBUG)
        search: Mesaj içinde arama
        search_type: "normal" veya "regex"
        start_date: Başlangıç tarihi (ISO format)
        end_date: Bitiş tarihi (ISO format)
    """
    
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    
    # Filtrelenmiş log girişlerini getir
    query = db.query(LogEntry).filter(LogEntry.log_file_id == file_id)
    
    if log_level:
        query = query.filter(LogEntry.log_level == log_level.upper())
    
    if search:
        if search_type == "regex":
            import re
            try:
                query = query.filter(LogEntry.message.op('~')(search))
            except:
                query = query.filter(LogEntry.message.ilike(f"%{search}%"))
        else:
            query = query.filter(LogEntry.message.ilike(f"%{search}%"))
    
    if start_date:
        query = query.filter(LogEntry.timestamp >= start_date)
    if end_date:
        query = query.filter(LogEntry.timestamp <= end_date)
    
    entries = query.order_by(LogEntry.line_number).all()
    
    # Analiz (opsiyonel)
    analysis = None
    if include_analysis:
        analysis = db.query(LogAnalysis).filter(
            LogAnalysis.log_file_id == file_id
        ).first()
    
    return export_logs_to_xml(log_file, entries, include_analysis, analysis)

