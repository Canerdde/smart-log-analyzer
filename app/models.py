from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Float,
    JSON,
    Boolean,
    Table,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import bcrypt

# Bcrypt doğrudan kullanılıyor (passlib yerine)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="user")  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # İlişkiler
    log_files = relationship(
        "LogFile", back_populates="owner", cascade="all, delete-orphan"
    )
    saved_searches = relationship(
        "SavedSearch", back_populates="user", cascade="all, delete-orphan"
    )
    favorites = relationship(
        "FavoriteLogFile", back_populates="user", cascade="all, delete-orphan"
    )
    search_history = relationship(
        "SearchHistory", back_populates="user", cascade="all, delete-orphan"
    )
    alerts = relationship(
        "AlertRule", back_populates="user", cascade="all, delete-orphan"
    )
    comments = relationship(
        "LogEntryComment", back_populates="user", cascade="all, delete-orphan"
    )

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Şifre doğrulama"""
        try:
            if not plain_password or not hashed_password:
                return False

            password_bytes = plain_password.encode("utf-8")
            # Bcrypt 72 byte limiti var
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]

            # Hash zaten string olarak saklanıyor, bytes'a çevir
            hash_bytes = hashed_password.encode("utf-8")

            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as e:
            print(f"Password verification error: {e}")
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Şifre hash'leme - bcrypt 72 byte limiti var"""
        # Bcrypt 72 byte limiti var, şifreyi encode edip kontrol et
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            # 72 byte'dan uzunsa truncate et (güvenlik için ilk 72 byte'ı al)
            password_bytes = password_bytes[:72]
        # Bcrypt ile hash'le
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")


# Many-to-many ilişki tablosu: LogFile <-> Tag
log_file_tags = Table(
    "log_file_tags",
    Base.metadata,
    Column("log_file_id", Integer, ForeignKey("log_files.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class LogFile(Base):
    __tablename__ = "log_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    file_size = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    total_lines = Column(Integer, default=0)
    status = Column(
        String(50), default="uploaded"
    )  # uploaded, processing, completed, failed
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # Dosyayı yükleyen kullanıcı
    category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=True, index=True
    )  # Kategori

    # İlişkiler
    owner = relationship("User", back_populates="log_files")
    log_entries = relationship(
        "LogEntry", back_populates="log_file", cascade="all, delete-orphan"
    )
    analysis = relationship(
        "LogAnalysis",
        back_populates="log_file",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tags = relationship("Tag", secondary=log_file_tags, back_populates="log_files")
    category = relationship("Category", back_populates="log_files")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    log_file_id = Column(Integer, ForeignKey("log_files.id"), nullable=False)
    line_number = Column(Integer, nullable=False)
    log_level = Column(String(20), index=True)  # ERROR, WARNING, INFO, DEBUG
    timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    message = Column(Text, nullable=False)
    raw_line = Column(Text, nullable=False)
    parsed_data = Column(JSON)  # Ekstra parse edilmiş veriler

    # İlişkiler
    log_file = relationship("LogFile", back_populates="log_entries")


class LogAnalysis(Base):
    __tablename__ = "log_analyses"

    id = Column(Integer, primary_key=True, index=True)
    log_file_id = Column(
        Integer, ForeignKey("log_files.id"), unique=True, nullable=False
    )
    total_entries = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    info_count = Column(Integer, default=0)
    debug_count = Column(Integer, default=0)

    # En sık tekrar eden hatalar
    top_errors = Column(JSON)  # [{"message": "...", "count": 10}, ...]
    top_warnings = Column(JSON)

    # Zaman serisi verileri
    time_distribution = Column(JSON)  # {"hour": count} formatında

    # AI yorumu (isteğe bağlı)
    ai_comment = Column(Text, nullable=True)
    ai_suggestions = Column(JSON, nullable=True)

    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    log_file = relationship("LogFile", back_populates="analysis")


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Arama adı (örn: "Database Hataları")
    description = Column(Text, nullable=True)  # Açıklama (opsiyonel)

    # Arama parametreleri (JSON)
    search_params = Column(
        JSON, nullable=False
    )  # {"log_level": "ERROR", "search": "database", "file_id": 1, ...}

    # İstatistikler
    use_count = Column(Integer, default=0)  # Kaç kez kullanıldı
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # İlişkiler
    user = relationship("User", back_populates="saved_searches")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Alert kuralı adı
    description = Column(Text, nullable=True)

    # Koşullar
    condition_type = Column(
        String(50), nullable=False
    )  # "error_count", "pattern_match", "threshold"
    condition_params = Column(
        JSON, nullable=False
    )  # {"threshold": 10, "time_window": 300, "log_level": "ERROR"}

    # Bildirim kanalları
    notification_channels = Column(
        JSON, nullable=False
    )  # ["email", "slack", "webhook"]
    recipients = Column(
        JSON, nullable=False
    )  # {"email": ["user@example.com"], "slack_webhook": "url"}

    # Ayarlar
    is_active = Column(String(10), default="active")  # active, paused, disabled
    cooldown_period = Column(Integer, default=300)  # Saniye (5 dakika)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # İlişkiler
    user = relationship("User", back_populates="alerts")


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    condition_met = Column(JSON)  # Hangi koşul tetiklendi
    notification_sent = Column(JSON)  # Hangi kanallara gönderildi
    status = Column(String(50), default="sent")  # sent, failed, pending


class LogEntryComment(Base):
    __tablename__ = "log_entry_comments"

    id = Column(Integer, primary_key=True, index=True)
    log_entry_id = Column(Integer, ForeignKey("log_entries.id"), nullable=False)
    comment = Column(Text, nullable=False)
    author = Column(String(100), nullable=True)  # Deprecated - user_id kullanılacak
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # İlişkiler
    log_entry = relationship("LogEntry", backref="comments")
    user = relationship("User", back_populates="comments")


class FavoriteLogFile(Base):
    __tablename__ = "favorite_log_files"

    id = Column(Integer, primary_key=True, index=True)
    log_file_id = Column(Integer, ForeignKey("log_files.id"), nullable=False)
    notes = Column(Text, nullable=True)  # Neden favorilendi
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    log_file = relationship("LogFile")
    user = relationship("User", back_populates="favorites")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    search_query = Column(String(500), nullable=False)  # Arama metni
    search_params = Column(
        JSON, nullable=True
    )  # {"log_level": "ERROR", "file_id": 1, ...}
    result_count = Column(Integer, default=0)  # Kaç sonuç bulundu
    searched_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # İlişkiler
    user = relationship("User", back_populates="search_history")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100), unique=True, nullable=False, index=True
    )  # Tag adı (örn: "production", "backend")
    color = Column(String(7), default="#667eea")  # Hex renk kodu
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    log_files = relationship("LogFile", secondary=log_file_tags, back_populates="tags")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100), unique=True, nullable=False, index=True
    )  # Kategori adı (örn: "Production", "Development")
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#667eea")  # Hex renk kodu
    icon = Column(String(50), nullable=True)  # Emoji veya icon
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    log_files = relationship("LogFile", back_populates="category")
