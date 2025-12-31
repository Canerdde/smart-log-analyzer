from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, ForwardRef, List, Optional, Union

from pydantic import BaseModel


class LogFileBase(BaseModel):
    filename: str


class LogFileCreate(LogFileBase):
    pass


# Forward references - TagResponse ve CategoryResponse daha aşağıda tanımlı
TagResponseRef = ForwardRef("TagResponse")
CategoryResponseRef = ForwardRef("CategoryResponse")


class LogFileResponse(LogFileBase):
    id: int
    filename: str
    file_size: Optional[int]
    uploaded_at: datetime
    total_lines: int
    status: str
    tags: Optional[List[TagResponseRef]] = []
    category: Optional[CategoryResponseRef] = None

    class Config:
        from_attributes = True


class LogEntryResponse(BaseModel):
    id: int
    log_file_id: int
    line_number: int
    log_level: Optional[str]
    timestamp: Optional[datetime]
    message: str
    raw_line: str

    class Config:
        from_attributes = True


class LogAnalysisResponse(BaseModel):
    id: int
    log_file_id: int
    total_entries: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    top_errors: Optional[List[Dict[str, Any]]]
    top_warnings: Optional[List[Dict[str, Any]]]
    time_distribution: Optional[Dict[str, int]]
    ai_comment: Optional[str]
    ai_suggestions: Optional[Dict[str, Any]]
    analyzed_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_files: int
    total_entries: int
    total_errors: int
    total_warnings: int
    recent_files: List[LogFileResponse]
    error_trend: List[Dict[str, Any]]


class SavedSearchBase(BaseModel):
    name: str
    description: Optional[str] = None
    search_params: Dict[str, Any]


class SavedSearchCreate(SavedSearchBase):
    pass


class SavedSearchResponse(SavedSearchBase):
    id: int
    use_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Alert System Schemas
class AlertRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    condition_type: str  # "error_count", "pattern_match", "threshold"
    condition_params: Dict[str, Any]
    notification_channels: List[str]  # ["email", "slack", "webhook"]
    recipients: Dict[str, Any]
    is_active: Optional[str] = "active"
    cooldown_period: Optional[int] = 300


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleResponse(AlertRuleBase):
    id: int
    last_triggered_at: Optional[datetime]
    trigger_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertHistoryResponse(BaseModel):
    id: int
    alert_rule_id: int
    triggered_at: datetime
    condition_met: Dict[str, Any]
    notification_sent: Dict[str, Any]
    status: str

    class Config:
        from_attributes = True


# Log Entry Comments Schemas
class LogEntryCommentBase(BaseModel):
    comment: str
    author: Optional[str] = None


class LogEntryCommentCreate(LogEntryCommentBase):
    pass


class LogEntryCommentResponse(LogEntryCommentBase):
    id: int
    log_entry_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Favorites Schemas
class FavoriteLogFileCreate(BaseModel):
    log_file_id: int
    notes: Optional[str] = None


class FavoriteLogFileResponse(BaseModel):
    id: int
    log_file_id: int
    notes: Optional[str]
    created_at: datetime
    log_file: LogFileResponse

    class Config:
        from_attributes = True


# Log Comparison Schemas
class LogComparisonRequest(BaseModel):
    file_id_1: int
    file_id_2: int


class LogComparisonResponse(BaseModel):
    file_1: LogFileResponse
    file_2: LogFileResponse
    differences: Dict[str, Any]
    common_errors: List[Dict[str, Any]]
    unique_to_file_1: List[Dict[str, Any]]
    unique_to_file_2: List[Dict[str, Any]]


# Search History Schemas
class SearchHistoryCreate(BaseModel):
    search_query: str
    search_params: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = 0


class SearchHistoryResponse(BaseModel):
    id: int
    search_query: str
    search_params: Optional[Dict[str, Any]]
    result_count: int
    searched_at: datetime

    class Config:
        from_attributes = True


# User Schemas
class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# Token Schema
class Token(BaseModel):
    access_token: str
    token_type: str


# Login Schema
class LoginRequest(BaseModel):
    username: str
    password: str


# Tag Schemas
class TagBase(BaseModel):
    name: str
    color: Optional[str] = "#667eea"
    description: Optional[str] = None


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Category Schemas
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#667eea"
    icon: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Bulk Operations Schemas
class BulkDeleteRequest(BaseModel):
    file_ids: List[int]


class BulkExportRequest(BaseModel):
    file_ids: List[int]
    format: str  # "json" or "xml"
    include_analysis: bool = False


class BulkFavoriteRequest(BaseModel):
    file_ids: List[int]
    action: str  # "add" or "remove"


class BulkTagRequest(BaseModel):
    tag_ids: List[int]


# Forward reference'leri çöz (TagResponse ve CategoryResponse tanımlandıktan sonra)
LogFileResponse.model_rebuild()
