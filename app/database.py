from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # PostgreSQL (production için)
    # DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/loganalyzer"
    # SQLite (hızlı test için - Docker/PostgreSQL kurmadan)
    DATABASE_URL: str = "sqlite:///./loganalyzer.db"

    # OpenAI API Key (opsiyonel)
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # .env dosyasındaki ekstra alanları yok say


settings = Settings()

# SQLite için connect_args ekle
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL için
    engine = create_engine(
        settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Veritabanı session'ı için dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
