"""
Log Entry Comments API
Log satırlarına not ekleme, ekip işbirliği
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import LogEntryComment, LogEntry
from app.schemas import LogEntryCommentCreate, LogEntryCommentResponse

router = APIRouter()


@router.post(
    "/entries/{entry_id}/comments",
    response_model=LogEntryCommentResponse,
    status_code=201,
)
async def create_comment(
    entry_id: int, comment: LogEntryCommentCreate, db: Session = Depends(get_db)
):
    """Log entry'ye yorum ekle"""
    # Entry var mı kontrol et
    entry = db.query(LogEntry).filter(LogEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Log entry bulunamadı")

    log_comment = LogEntryComment(
        log_entry_id=entry_id,
        comment=comment.comment,
        author=comment.author or "Anonymous",
    )

    db.add(log_comment)
    db.commit()
    db.refresh(log_comment)

    return log_comment


@router.get(
    "/entries/{entry_id}/comments", response_model=List[LogEntryCommentResponse]
)
async def get_entry_comments(entry_id: int, db: Session = Depends(get_db)):
    """Bir log entry'nin tüm yorumlarını getir"""
    entry = db.query(LogEntry).filter(LogEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Log entry bulunamadı")

    comments = (
        db.query(LogEntryComment)
        .filter(LogEntryComment.log_entry_id == entry_id)
        .order_by(LogEntryComment.created_at.desc())
        .all()
    )

    return comments


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    """Yorumu sil"""
    comment = db.query(LogEntryComment).filter(LogEntryComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı")

    db.delete(comment)
    db.commit()

    return {"message": "Yorum silindi"}


@router.put("/comments/{comment_id}", response_model=LogEntryCommentResponse)
async def update_comment(
    comment_id: int, comment: LogEntryCommentCreate, db: Session = Depends(get_db)
):
    """Yorumu güncelle"""
    log_comment = (
        db.query(LogEntryComment).filter(LogEntryComment.id == comment_id).first()
    )
    if not log_comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı")

    log_comment.comment = comment.comment
    log_comment.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(log_comment)

    return log_comment
