from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

from app.models import (
    UserRole, AssetType, AssetStatus, 
    AlertSeverity, MetricType
)

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    pass

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None

# Asset Schemas
class AssetBase(BaseModel):
    name: str
    description: Optional[str] = None
    asset_type: AssetType
    status: AssetStatus = AssetStatus.ACTIVE
    location: Optional[str] = None
    
    # Financial fields
    symbol: Optional[str] = None
    current_price: Optional[float] = None
    quantity: Optional[int] = 0
    purchase_price: Optional[float] = None
    purchase_date: Optional[date] = None
    
    # Manufacturing fields
    model: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    installation_date: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    
    # Performance
    health_score: Optional[float] = Field(100.0, ge=0.0, le=100.0)
    uptime_percentage: Optional[float] = Field(100.0, ge=0.0, le=100.0)
    
    # Metadata
    tags: Optional[Dict[str, Any]] = {}
    metadata: Optional[Dict[str, Any]] = {}

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[AssetStatus] = None
    location: Optional[str] = None
    current_price: Optional[float] = None
    quantity: Optional[int] = None
    health_score: Optional[float] = None
    tags: Optional[Dict[str, Any]] = None

class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Metric Schemas
class MetricBase(BaseModel):
    asset_id: int
    metric_type: MetricType
    value: float
    unit: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class MetricCreate(MetricBase):
    timestamp: Optional[datetime] = None

class MetricResponse(MetricBase):
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

# Alert Schemas
class AlertBase(BaseModel):
    asset_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: str = "open"
    metric_type: Optional[MetricType] = None
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None

class AlertCreate(AlertBase):
    pass

class AlertUpdate(BaseModel):
    status: Optional[str] = None
    resolved_by: Optional[int] = None
    resolution_notes: Optional[str] = None

class AlertResponse(AlertBase):
    id: int
    user_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Relationships
    asset: Optional[AssetResponse] = None
    user: Optional[UserResponse] = None
    
    class Config:
        from_attributes = True

# Report Schemas
class ReportBase(BaseModel):
    report_type: str
    title: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = {}
    file_format: Optional[str] = "pdf"
    is_scheduled: bool = False
    schedule_cron: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    status: Optional[str] = None
    file_path: Optional[str] = None
    last_generated_at: Optional[datetime] = None
    next_generation_at: Optional[datetime] = None

class ReportResponse(ReportBase):
    id: int
    user_id: int
    data: Optional[Dict[str, Any]] = {}
    file_path: Optional[str] = None
    status: str
    last_generated_at: Optional[datetime]
    next_generation_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Dashboard Schemas
class DashboardStats(BaseModel):
    total_assets: int
    active_assets: int
    total_alerts: int
    open_alerts: int
    critical_alerts: int
    avg_health_score: float
    total_users: int

class AssetPerformance(BaseModel):
    asset_id: int
    asset_name: str
    asset_type: str
    current_value: float
    daily_change: float
    weekly_change: float
    health_score: float
    alerts_count: int

# WebSocket Schemas
class WebSocketMessage(BaseModel):
    type: str  # alert, metric_update, status_change
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
