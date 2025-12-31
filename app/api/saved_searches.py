"""
Saved Searches API - Kayıtlı aramalar yönetimi
Kullanıcı odaklı, pratik arama yönetimi
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import SavedSearch
from app.schemas import SavedSearchCreate, SavedSearchResponse

router = APIRouter()

@router.post("", response_model=SavedSearchResponse, status_code=201)
async def create_saved_search(
    search: SavedSearchCreate,
    db: Session = Depends(get_db)
):
    """
    Yeni bir kayıtlı arama oluştur
    
    search_params örneği:
    {
        "log_level": "ERROR",
        "search": "database",
        "file_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-31T23:59:59"
    }
    """
    # Aynı isimde arama var mı kontrol et
    existing = db.query(SavedSearch).filter(SavedSearch.name == search.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"'{search.name}' adında bir arama zaten mevcut"
        )
    
    saved_search = SavedSearch(
        name=search.name,
        description=search.description,
        search_params=search.search_params
    )
    
    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)
    
    return saved_search

@router.get("", response_model=List[SavedSearchResponse])
async def list_saved_searches(
    db: Session = Depends(get_db)
):
    """Tüm kayıtlı aramaları listele (kullanım sayısına göre sıralı)"""
    searches = db.query(SavedSearch).order_by(
        SavedSearch.use_count.desc(),
        SavedSearch.last_used_at.desc(),
        SavedSearch.created_at.desc()
    ).all()
    return searches

@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: int,
    db: Session = Depends(get_db)
):
    """Belirli bir kayıtlı aramayı getir"""
    search = db.query(SavedSearch).filter(SavedSearch.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Kayıtlı arama bulunamadı")
    return search

@router.put("/{search_id}/use")
async def use_saved_search(
    search_id: int,
    db: Session = Depends(get_db)
):
    """
    Kayıtlı aramayı kullan (use_count artır)
    Arama parametrelerini döndürür
    """
    search = db.query(SavedSearch).filter(SavedSearch.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Kayıtlı arama bulunamadı")
    
    # İstatistikleri güncelle
    search.use_count += 1
    search.last_used_at = datetime.utcnow()
    db.commit()
    
    return {
        "id": search.id,
        "name": search.name,
        "search_params": search.search_params
    }

@router.delete("/{search_id}")
async def delete_saved_search(
    search_id: int,
    db: Session = Depends(get_db)
):
    """Kayıtlı aramayı sil"""
    search = db.query(SavedSearch).filter(SavedSearch.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Kayıtlı arama bulunamadı")
    
    db.delete(search)
    db.commit()
    
    return {"message": "Kayıtlı arama silindi"}

@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    search: SavedSearchCreate,
    db: Session = Depends(get_db)
):
    """Kayıtlı aramayı güncelle"""
    saved_search = db.query(SavedSearch).filter(SavedSearch.id == search_id).first()
    if not saved_search:
        raise HTTPException(status_code=404, detail="Kayıtlı arama bulunamadı")
    
    # İsim değişiyorsa, yeni ismin benzersiz olduğunu kontrol et
    if search.name != saved_search.name:
        existing = db.query(SavedSearch).filter(
            SavedSearch.name == search.name,
            SavedSearch.id != search_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"'{search.name}' adında bir arama zaten mevcut"
            )
    
    saved_search.name = search.name
    saved_search.description = search.description
    saved_search.search_params = search.search_params
    saved_search.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(saved_search)
    
    return saved_search

