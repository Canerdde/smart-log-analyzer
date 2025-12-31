"""
Authentication API endpoints - Login, Register, User management
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token,
                      get_current_active_user, require_role)
from app.database import get_db
from app.models import User
from app.schemas import (LoginRequest, Token, UserCreate, UserResponse,
                         UserUpdate)

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Yeni kullanıcı kaydı"""
    # Kullanıcı adı kontrolü
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Email kontrolü
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Yeni kullanıcı oluştur
    hashed_password = User.get_password_hash(user_data.password)
    print(f"Registering user: {user_data.username}")
    print(f"Hash prefix: {hashed_password[:20]}...")
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=(
            user_data.role if hasattr(user_data, "role") and user_data.role else "user"
        ),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Kullanıcı girişi - JWT token döndürür"""
    user = db.query(User).filter(User.username == login_data.username).first()

    if not user:
        print(f"User not found: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Şifre doğrulama
    print(f"Verifying password for user: {login_data.username}")
    print(
        f"Hash prefix: {user.hashed_password[:20] if user.hashed_password else 'None'}..."
    )
    is_valid = User.verify_password(login_data.password, user.hashed_password)
    print(f"Password verification result: {is_valid}")

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    # Last login güncelle
    user.last_login = datetime.utcnow()
    db.commit()

    # Access token oluştur
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Mevcut kullanıcı bilgilerini getir"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mevcut kullanıcı bilgilerini güncelle"""
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.email is not None:
        # Email kontrolü
        existing = (
            db.query(User)
            .filter(User.email == user_update.email, User.id != current_user.id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_update.email
    if user_update.password is not None:
        current_user.hashed_password = User.get_password_hash(user_update.password)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_role(["admin"])), db: Session = Depends(get_db)
):
    """Tüm kullanıcıları listele (sadece admin)"""
    users = db.query(User).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Kullanıcı detaylarını getir (sadece admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Kullanıcı güncelle (sadece admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        existing = (
            db.query(User)
            .filter(User.email == user_update.email, User.id != user_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = user_update.email
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    if user_update.password is not None:
        user.hashed_password = User.get_password_hash(user_update.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Kullanıcı sil (sadece admin)"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
