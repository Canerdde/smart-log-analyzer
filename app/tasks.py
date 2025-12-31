"""
Celery background tasks
Büyük dosyalar ve uzun süren işlemler için async görevler
"""

import os

from celery import Celery
from sqlalchemy.orm import Session

from app.ai_service import AIService
from app.analyzer import LogAnalyzer
from app.cache import invalidate_cache
from app.database import SessionLocal
from app.log_parser import LogParser
from app.models import LogAnalysis, LogEntry, LogFile

# Celery app oluştur
celery_app = Celery(
    "loganalyzer",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

parser = LogParser()
analyzer = LogAnalyzer()
ai_service = AIService()


@celery_app.task(bind=True)
def process_large_log_file(self, file_id: int, file_path: str, use_ai: bool = False):
    """
    Büyük log dosyalarını arka planda işle

    Args:
        file_id: Log dosyası ID'si
        file_path: Dosya yolu
        use_ai: AI analizi yapılsın mı
    """
    db = SessionLocal()

    try:
        log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
        if not log_file:
            return {"status": "error", "message": "Log file not found"}

        # Durumu güncelle
        log_file.status = "processing"
        db.commit()

        # Dosyayı oku ve parse et (streaming ile)
        total_lines = 0
        parsed_entries = []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_number, line in enumerate(f, start=1):
                parsed = parser.parse_line(line, line_number)
                if parsed:
                    parsed_entries.append(parsed)
                    total_lines += 1

                    # Her 100 satırda bir batch kaydet
                    if len(parsed_entries) >= 100:
                        _save_entries_batch(db, file_id, parsed_entries)
                        parsed_entries = []

                        # İlerleme güncelle
                        self.update_state(
                            state="PROGRESS",
                            meta={"current": line_number, "total": "unknown"},
                        )

        # Kalan kayıtları kaydet
        if parsed_entries:
            _save_entries_batch(db, file_id, parsed_entries)

        # Toplam satır sayısını güncelle
        log_file.total_lines = total_lines

        # Analiz yap
        all_entries = db.query(LogEntry).filter(LogEntry.log_file_id == file_id).all()

        entries_dict = [
            {
                "log_level": e.log_level,
                "timestamp": e.timestamp,
                "message": e.message,
                "line_number": e.line_number,
            }
            for e in all_entries
        ]

        analysis_result = analyzer.analyze(entries_dict)

        # AI analizi
        ai_result = {}
        if use_ai:
            sample_entries = entries_dict[:20]
            ai_result = ai_service.analyze_logs(analysis_result, sample_entries)

        # Analiz sonucunu kaydet
        db_analysis = LogAnalysis(
            log_file_id=file_id,
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

        log_file.status = "completed"
        db.commit()

        # Cache'i temizle
        invalidate_cache(file_id)

        return {
            "status": "completed",
            "file_id": file_id,
            "total_lines": total_lines,
            "analysis_id": db_analysis.id,
        }

    except Exception as e:
        log_file.status = "failed"
        db.commit()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def _save_entries_batch(db: Session, file_id: int, entries: list):
    """Log girişlerini batch olarak kaydet"""
    for entry_data in entries:
        db_entry = LogEntry(
            log_file_id=file_id,
            line_number=entry_data["line_number"],
            log_level=entry_data["log_level"],
            timestamp=entry_data["timestamp"],
            message=entry_data["message"],
            raw_line=entry_data["raw_line"],
        )
        db.add(db_entry)
    db.commit()


@celery_app.task
def cleanup_old_logs(days: int = 30):
    """Eski log dosyalarını temizle"""
    from datetime import datetime, timedelta

    db = SessionLocal()

    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        old_files = db.query(LogFile).filter(LogFile.uploaded_at < cutoff_date).all()

        deleted_count = 0
        for file in old_files:
            # Dosyayı diskten sil
            if file.file_path and os.path.exists(file.file_path):
                os.remove(file.file_path)
            # Veritabanından sil (cascade ile ilişkili veriler de silinecek)
            db.delete(file)
            deleted_count += 1

        db.commit()
        return {"deleted_count": deleted_count}
    finally:
        db.close()
