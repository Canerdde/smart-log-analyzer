"""
Favorites API - Önemli log dosyalarını favorilere ekleme
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import FavoriteLogFile, LogFile
from app.schemas import FavoriteLogFileCreate, FavoriteLogFileResponse

router = APIRouter()


@router.post("", response_model=FavoriteLogFileResponse, status_code=201)
async def add_favorite(favorite: FavoriteLogFileCreate, db: Session = Depends(get_db)):
    """Log dosyasını favorilere ekle"""
    # Dosya var mı kontrol et
    log_file = db.query(LogFile).filter(LogFile.id == favorite.log_file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    # Zaten favori mi kontrol et
    existing = (
        db.query(FavoriteLogFile)
        .filter(FavoriteLogFile.log_file_id == favorite.log_file_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Bu dosya zaten favorilerde")

    fav = FavoriteLogFile(log_file_id=favorite.log_file_id, notes=favorite.notes)

    db.add(fav)
    db.commit()
    db.refresh(fav)

    # Log file bilgisini de ekle
    return FavoriteLogFileResponse(
        id=fav.id,
        log_file_id=fav.log_file_id,
        notes=fav.notes,
        created_at=fav.created_at,
        log_file=log_file,
    )


@router.get("", response_model=List[FavoriteLogFileResponse])
async def list_favorites(db: Session = Depends(get_db)):
    """Tüm favorileri listele"""
    favorites = (
        db.query(FavoriteLogFile).order_by(FavoriteLogFile.created_at.desc()).all()
    )

    # Her favorite için log_file bilgisini ekle
    result = []
    for fav in favorites:
        log_file = db.query(LogFile).filter(LogFile.id == fav.log_file_id).first()
        result.append(
            FavoriteLogFileResponse(
                id=fav.id,
                log_file_id=fav.log_file_id,
                notes=fav.notes,
                created_at=fav.created_at,
                log_file=log_file,
            )
        )

    return result


@router.delete("/{favorite_id}")
async def remove_favorite(favorite_id: int, db: Session = Depends(get_db)):
    """Favoriden kaldır"""
    favorite = (
        db.query(FavoriteLogFile).filter(FavoriteLogFile.id == favorite_id).first()
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favori bulunamadı")

    db.delete(favorite)
    db.commit()

    return {"message": "Favori kaldırıldı"}


@router.get("/check/{file_id}")
async def check_is_favorite(file_id: int, db: Session = Depends(get_db)):
    """Dosyanın favori olup olmadığını kontrol et"""
    favorite = (
        db.query(FavoriteLogFile).filter(FavoriteLogFile.log_file_id == file_id).first()
    )

    return {
        "is_favorite": favorite is not None,
        "favorite_id": favorite.id if favorite else None,
    }
