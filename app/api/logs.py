from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import aiofiles
import os
from pathlib import Path

from app.database import get_db
from app.models import LogFile, LogEntry, LogAnalysis, FavoriteLogFile
from app.schemas import (
    LogFileResponse,
    BulkDeleteRequest,
    BulkExportRequest,
    BulkFavoriteRequest,
)
from app.auth import get_current_active_user
from app.models import User
from app.log_parser import LogParser
from app.analyzer import LogAnalyzer
from app.ai_service import AIService
from app.monitoring import logs_uploaded_total
from app.cache import invalidate_cache
import os

# Celery opsiyonel - yoksa normal işleme devam eder
try:
    from app.tasks import process_large_log_file

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    print("Celery bulunamadı, büyük dosyalar normal işlenecek")

router = APIRouter()

# Upload dizini
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

parser = LogParser()
analyzer = LogAnalyzer()
ai_service = AIService()


@router.post("/upload", response_model=LogFileResponse)
async def upload_log_file(
    file: UploadFile = File(...), use_ai: bool = False, db: Session = Depends(get_db)
):
    """Log dosyasını yükle ve analiz et"""

    # Dosyayı kaydet
    file_path = UPLOAD_DIR / file.filename
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    file_size = len(content)

    # Log dosyası kaydı oluştur
    db_log_file = LogFile(
        filename=file.filename,
        file_path=str(file_path),
        file_size=file_size,
        status="processing",
    )
    db.add(db_log_file)
    db.commit()
    db.refresh(db_log_file)

    try:
        # Dosyayı parse et
        file_content = content.decode("utf-8", errors="ignore")
        parsed_entries = parser.parse_file(file_content)

        # Parse edilmiş girişleri veritabanına kaydet
        for entry_data in parsed_entries:
            db_entry = LogEntry(
                log_file_id=db_log_file.id,
                line_number=entry_data["line_number"],
                log_level=entry_data["log_level"],
                timestamp=entry_data["timestamp"],
                message=entry_data["message"],
                raw_line=entry_data["raw_line"],
            )
            db.add(db_entry)

        db_log_file.total_lines = len(parsed_entries)

        # Büyük dosyalar için Celery kullan (10MB+) - eğer mevcutsa
        if CELERY_AVAILABLE and file_size > 10_000_000:  # 10MB'dan büyükse
            db_log_file.status = "processing"
            db.commit()

            # Arka planda işle
            try:
                process_large_log_file.delay(db_log_file.id, str(file_path), use_ai)
                logs_uploaded_total.inc()
                return db_log_file
            except Exception as e:
                # Celery hatası varsa normal işleme devam et
                print(f"Celery hatası (normal işleme devam ediyor): {e}")
                db_log_file.status = "completed"
        else:
            db_log_file.status = "completed"

        # Analiz yap
        analysis_result = analyzer.analyze(parsed_entries)

        # AI analizi (isteğe bağlı)
        ai_result = {}
        if use_ai:
            print(f"AI analizi başlatılıyor... (use_ai={use_ai})")
            sample_entries = parsed_entries[:20]  # İlk 20 örnek
            ai_result = ai_service.analyze_logs(analysis_result, sample_entries)
            print(
                f"AI analiz sonucu: ai_comment={ai_result.get('ai_comment') is not None}, ai_suggestions={ai_result.get('ai_suggestions') is not None}"
            )

        # Analiz sonucunu kaydet
        db_analysis = LogAnalysis(
            log_file_id=db_log_file.id,
            total_entries=analysis_result["total_entries"],
            error_count=analysis_result["error_count"],
            warning_count=analysis_result["warning_count"],
            info_count=analysis_result["info_count"],
            debug_count=analysis_result["debug_count"],
            top_errors=analysis_result["top_errors"],
            top_warnings=analysis_result["top_warnings"],
            time_distribution=analysis_result["time_distribution"],
            ai_comment=ai_result.get("ai_comment"),
            ai_suggestions=ai_result.get("ai_suggestions"),
        )
        db.add(db_analysis)

        db.commit()
        db.refresh(db_log_file)

        # Cache'i temizle
        invalidate_cache(db_log_file.id)

        # Metrikleri güncelle
        logs_uploaded_total.inc()

        return db_log_file

    except Exception as e:
        db_log_file.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Log analiz hatası: {str(e)}")


@router.get("/", response_model=List[LogFileResponse])
async def get_log_files(
    skip: int = 0,
    limit: int = 100,
    tags: str = None,  # Virgülle ayrılmış tag isimleri
    category_id: int = None,
    db: Session = Depends(get_db),
):
    """Yüklenmiş log dosyalarını listele"""
    query = db.query(LogFile)

    # Tag filtresi
    if tags:
        tag_names = [t.strip() for t in tags.split(",")]
        from app.models import Tag

        tag_objects = db.query(Tag).filter(Tag.name.in_(tag_names)).all()
        if tag_objects:
            tag_ids = [t.id for t in tag_objects]
            query = query.join(LogFile.tags).filter(Tag.id.in_(tag_ids))

    # Kategori filtresi
    if category_id:
        query = query.filter(LogFile.category_id == category_id)

    from sqlalchemy.orm import joinedload

    files = (
        query.options(joinedload(LogFile.tags), joinedload(LogFile.category))
        .order_by(LogFile.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return files


@router.get("/{file_id}", response_model=LogFileResponse)
async def get_log_file(file_id: int, db: Session = Depends(get_db)):
    """Belirli bir log dosyasının detaylarını getir"""
    from sqlalchemy.orm import joinedload

    log_file = (
        db.query(LogFile)
        .options(joinedload(LogFile.tags), joinedload(LogFile.category))
        .filter(LogFile.id == file_id)
        .first()
    )
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")
    return log_file


@router.delete("/{file_id}")
async def delete_log_file(file_id: int, db: Session = Depends(get_db)):
    """Log dosyasını ve ilişkili verilerini sil"""
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    # Dosyayı diskten sil
    if log_file.file_path and os.path.exists(log_file.file_path):
        os.remove(log_file.file_path)

    # Veritabanından sil (cascade ile ilişkili veriler de silinecek)
    db.delete(log_file)
    db.commit()

    return {"message": "Log dosyası silindi"}


# Bulk Operations
@router.post("/bulk-delete")
async def bulk_delete_files(
    request: BulkDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Birden fazla log dosyasını toplu olarak sil"""
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="En az bir dosya ID'si gerekli")

    deleted_count = 0
    errors = []

    for file_id in request.file_ids:
        log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
        if not log_file:
            errors.append(f"Dosya {file_id} bulunamadı")
            continue

        # Dosyayı diskten sil
        if log_file.file_path and os.path.exists(log_file.file_path):
            try:
                os.remove(log_file.file_path)
            except Exception as e:
                errors.append(f"Dosya {file_id} diskten silinemedi: {str(e)}")

        # Veritabanından sil
        db.delete(log_file)
        deleted_count += 1

    db.commit()

    return {
        "message": f"{deleted_count} dosya silindi",
        "deleted_count": deleted_count,
        "errors": errors,
    }


@router.post("/bulk-export")
async def bulk_export_files(request: BulkExportRequest, db: Session = Depends(get_db)):
    """Birden fazla log dosyasını toplu olarak export et"""
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="En az bir dosya ID'si gerekli")

    if request.format not in ["json", "xml"]:
        raise HTTPException(status_code=400, detail="Format 'json' veya 'xml' olmalı")

    from app.export import export_logs_to_json, export_logs_to_xml
    from app.models import LogEntry, LogAnalysis
    import zipfile
    import io
    from datetime import datetime

    # Zip dosyası oluştur
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_id in request.file_ids:
            log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
            if not log_file:
                continue

            try:
                # Log girişlerini getir
                entries = (
                    db.query(LogEntry)
                    .filter(LogEntry.log_file_id == file_id)
                    .order_by(LogEntry.line_number)
                    .all()
                )

                # Analiz (opsiyonel)
                analysis = None
                if request.include_analysis:
                    analysis = (
                        db.query(LogAnalysis)
                        .filter(LogAnalysis.log_file_id == file_id)
                        .first()
                    )

                # Export fonksiyonunu çağır
                if request.format == "json":
                    export_response = export_logs_to_json(
                        log_file, entries, request.include_analysis, analysis
                    )
                else:
                    export_response = export_logs_to_xml(
                        log_file, entries, request.include_analysis, analysis
                    )

                # Response content'ini al
                content = export_response.content

                # Zip'e ekle
                filename = f"log_export_{file_id}.{request.format}"
                zip_file.writestr(filename, content)
            except Exception as e:
                print(f"Export hatası (file_id={file_id}): {e}")
                continue

    zip_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    from fastapi.responses import Response

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=bulk_export_{timestamp}.zip"
        },
    )


@router.post("/bulk-favorite")
async def bulk_favorite_files(
    request: BulkFavoriteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Birden fazla log dosyasını toplu olarak favorilere ekle/çıkar"""
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="En az bir dosya ID'si gerekli")

    if request.action not in ["add", "remove"]:
        raise HTTPException(status_code=400, detail="Action 'add' veya 'remove' olmalı")

    processed_count = 0
    errors = []

    for file_id in request.file_ids:
        log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
        if not log_file:
            errors.append(f"Dosya {file_id} bulunamadı")
            continue

        if request.action == "add":
            # Favoriye ekle (zaten varsa atla)
            existing = (
                db.query(FavoriteLogFile)
                .filter(
                    FavoriteLogFile.log_file_id == file_id,
                    FavoriteLogFile.user_id == current_user.id,
                )
                .first()
            )

            if not existing:
                favorite = FavoriteLogFile(log_file_id=file_id, user_id=current_user.id)
                db.add(favorite)
                processed_count += 1
        else:
            # Favoriden çıkar
            favorite = (
                db.query(FavoriteLogFile)
                .filter(
                    FavoriteLogFile.log_file_id == file_id,
                    FavoriteLogFile.user_id == current_user.id,
                )
                .first()
            )

            if favorite:
                db.delete(favorite)
                processed_count += 1

    db.commit()

    return {
        "message": f"{processed_count} dosya işlendi",
        "processed_count": processed_count,
        "action": request.action,
        "errors": errors,
    }
