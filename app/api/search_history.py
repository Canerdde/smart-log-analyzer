"""
Search History API - Arama geçmişi yönetimi
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import SearchHistory
from app.schemas import SearchHistoryCreate, SearchHistoryResponse

router = APIRouter()

@router.post("", response_model=SearchHistoryResponse, status_code=201)
async def create_search_history(
    history: SearchHistoryCreate,
    db: Session = Depends(get_db)
):
    """Yeni bir arama geçmişi kaydı oluştur"""
    search_history = SearchHistory(
        search_query=history.search_query,
        search_params=history.search_params,
        result_count=history.result_count
    )
    
    db.add(search_history)
    db.commit()
    db.refresh(search_history)
    
    return search_history

@router.get("", response_model=List[SearchHistoryResponse])
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    days: Optional[int] = Query(30, description="Son kaç günün geçmişi"),
    db: Session = Depends(get_db)
):
    """Arama geçmişini getir (en son yapılanlar)"""
    query = db.query(SearchHistory)
    
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(SearchHistory.searched_at >= cutoff_date)
    
    searches = query.order_by(
        SearchHistory.searched_at.desc()
    ).limit(limit).all()
    
    return searches

@router.delete("/{history_id}")
async def delete_search_history(
    history_id: int,
    db: Session = Depends(get_db)
):
    """Arama geçmişi kaydını sil"""
    history = db.query(SearchHistory).filter(SearchHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="Arama geçmişi bulunamadı")
    
    db.delete(history)
    db.commit()
    
    return {"message": "Arama geçmişi silindi"}

@router.delete("")
async def clear_search_history(
    days: Optional[int] = Query(None, description="Belirli günden eski kayıtları sil"),
    db: Session = Depends(get_db)
):
    """Tüm arama geçmişini temizle veya belirli günden eski kayıtları sil"""
    query = db.query(SearchHistory)
    
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(SearchHistory.searched_at < cutoff_date)
    
    deleted_count = query.delete()
    db.commit()
    
    return {"message": f"{deleted_count} arama geçmişi kaydı silindi"}

