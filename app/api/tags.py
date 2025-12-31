"""
Tags and Categories API endpoints
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, get_optional_user, require_role
from app.database import get_db
from app.models import Category, LogFile, Tag, User, log_file_tags
from app.schemas import (BulkTagRequest, CategoryCreate, CategoryResponse,
                         CategoryUpdate, TagCreate, TagResponse)

router = APIRouter()

# ========== TAGS ==========


@router.get("/", response_model=List[TagResponse])
async def list_tags(db: Session = Depends(get_db)):
    """Tüm tag'leri listele"""
    tags = db.query(Tag).order_by(Tag.name).all()
    return tags


@router.post("/", response_model=TagResponse, status_code=201)
async def create_tag(
    tag_data: TagCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Yeni tag oluştur"""
    # Aynı isimde tag var mı kontrol et
    existing = db.query(Tag).filter(Tag.name == tag_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu isimde bir tag zaten var")

    tag = Tag(
        name=tag_data.name,
        color=tag_data.color or "#667eea",
        description=tag_data.description,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(tag_id: int, db: Session = Depends(get_db)):
    """Tag detaylarını getir"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag bulunamadı")
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: int,
    tag_data: TagCreate,
    current_user: User = Depends(require_role(["admin", "user"])),
    db: Session = Depends(get_db),
):
    """Tag güncelle"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag bulunamadı")

    # İsim değişiyorsa kontrol et
    if tag_data.name != tag.name:
        existing = db.query(Tag).filter(Tag.name == tag_data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu isimde bir tag zaten var")

    tag.name = tag_data.name
    tag.color = tag_data.color or tag.color
    tag.description = tag_data.description
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Tag sil (sadece admin)"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag bulunamadı")

    db.delete(tag)
    db.commit()
    return {"message": "Tag silindi"}


@router.post("/{tag_id}/files/{file_id}")
async def add_tag_to_file(
    tag_id: int,
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Dosyaya tag ekle"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag bulunamadı")

    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    # Zaten ekli mi kontrol et
    if tag in log_file.tags:
        return {"message": "Tag zaten ekli"}

    log_file.tags.append(tag)
    db.commit()
    return {"message": "Tag eklendi"}


@router.delete("/{tag_id}/files/{file_id}")
async def remove_tag_from_file(
    tag_id: int,
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Dosyadan tag kaldır"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag bulunamadı")

    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    if tag not in log_file.tags:
        raise HTTPException(status_code=400, detail="Tag dosyada yok")

    log_file.tags.remove(tag)
    db.commit()
    return {"message": "Tag kaldırıldı"}


@router.post("/files/{file_id}/bulk")
async def add_tags_to_file(
    file_id: int,
    request: BulkTagRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Dosyaya birden fazla tag ekle (authentication optional)"""
    tag_ids = request.tag_ids

    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    # Kullanıcı kontrolü (opsiyonel - eğer user varsa ve admin değilse sadece kendi dosyalarını düzenleyebilir)
    if current_user and current_user.role != "admin":
        if log_file.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Bu dosyayı düzenleme yetkiniz yok"
            )

    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=400, detail="Bazı tag'ler bulunamadı")

    # Mevcut tag'leri temizle ve yeni tag'leri ekle
    log_file.tags.clear()
    for tag in tags:
        log_file.tags.append(tag)

    db.commit()
    db.refresh(log_file)
    return {"message": f"{len(tags)} tag eklendi"}


# ========== CATEGORIES ==========


@router.get("/categories/", response_model=List[CategoryResponse])
async def list_categories(db: Session = Depends(get_db)):
    """Tüm kategorileri listele"""
    categories = db.query(Category).order_by(Category.name).all()
    return categories


@router.post("/categories/", response_model=CategoryResponse, status_code=201)
async def create_category(
    category_data: CategoryCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Yeni kategori oluştur"""
    # Aynı isimde kategori var mı kontrol et
    existing = db.query(Category).filter(Category.name == category_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu isimde bir kategori zaten var")

    category = Category(
        name=category_data.name,
        description=category_data.description,
        color=category_data.color or "#667eea",
        icon=category_data.icon,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: int, db: Session = Depends(get_db)):
    """Kategori detaylarını getir"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Kategori güncelle"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")

    # İsim değişiyorsa kontrol et
    if category_data.name and category_data.name != category.name:
        existing = (
            db.query(Category).filter(Category.name == category_data.name).first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="Bu isimde bir kategori zaten var"
            )
        category.name = category_data.name

    if category_data.description is not None:
        category.description = category_data.description
    if category_data.color:
        category.color = category_data.color
    if category_data.icon is not None:
        category.icon = category_data.icon

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Kategori sil (sadece admin)"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")

    # Kategorideki dosyaların category_id'sini null yap
    db.query(LogFile).filter(LogFile.category_id == category_id).update(
        {"category_id": None}
    )

    db.delete(category)
    db.commit()
    return {"message": "Kategori silindi"}


@router.put("/files/{file_id}/category")
async def set_file_category(
    file_id: int,
    category_id: Optional[int] = Query(None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Dosyanın kategori'sini ayarla (category_id=None ise kategori kaldırılır) (authentication optional)"""
    log_file = db.query(LogFile).filter(LogFile.id == file_id).first()
    if not log_file:
        raise HTTPException(status_code=404, detail="Log dosyası bulunamadı")

    # Kullanıcı kontrolü (opsiyonel - eğer user varsa ve admin değilse sadece kendi dosyalarını düzenleyebilir)
    if current_user and current_user.role != "admin":
        if log_file.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Bu dosyayı düzenleme yetkiniz yok"
            )

    if category_id is not None:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Kategori bulunamadı")
        log_file.category_id = category_id
    else:
        log_file.category_id = None

    db.commit()
    db.refresh(log_file)
    return {"message": "Kategori güncellendi"}
