from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Enum, JSON, BigInteger, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    TECHNICIAN = "technician"
    VIEWER = "viewer"

class AssetType(str, enum.Enum):
    FINANCIAL = "financial"
    MANUFACTURING = "manufacturing"

class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    FAILED = "failed"

class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class MetricType(str, enum.Enum):
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    PRESSURE = "pressure"
    VOLTAGE = "voltage"
    CURRENT = "current"
    STOCK_PRICE = "stock_price"
    PORTFOLIO_VALUE = "portfolio_value"
    RISK_SCORE = "risk_score"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    alerts = relationship("Alert", back_populates="user")
    reports = relationship("Report", back_populates="user")

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    asset_type = Column(Enum(AssetType), nullable=False)
    status = Column(Enum(AssetStatus), default=AssetStatus.ACTIVE)
    location = Column(String(255))
    
    # Financial asset fields
    symbol = Column(String(50), nullable=True)  # For stocks: AAPL, TSLA
    current_price = Column(Numeric(10, 2), default=0)
    quantity = Column(Integer, default=0)
    purchase_price = Column(Numeric(10, 2), default=0)
    purchase_date = Column(DateTime(timezone=True))
    
    # Manufacturing asset fields
    model = Column(String(100))
    serial_number = Column(String(100), unique=True)
    manufacturer = Column(String(100))
    installation_date = Column(DateTime(timezone=True))
    last_maintenance_date = Column(DateTime(timezone=True))
    next_maintenance_date = Column(DateTime(timezone=True))
    
    # Performance metrics
    health_score = Column(Float, default=100.0)  # 0-100%
    uptime_percentage = Column(Float, default=100.0)
    
    # Metadata
    tags = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    metrics = relationship("Metric", back_populates="asset")
    alerts = relationship("Alert", back_populates="asset")

class Metric(Base):
    __tablename__ = "metrics"

    id = Column(BigInteger, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    metric_type = Column(Enum(MetricType), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50))
    
    # Additional data
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata = Column(JSON, default=dict)
    
    # Relationships
    asset = relationship("Asset", back_populates="metrics")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.MEDIUM)
    status = Column(String(50), default="open")  # open, acknowledged, resolved, closed
    
    # Alert data
    metric_type = Column(Enum(MetricType))
    threshold_value = Column(Float)
    actual_value = Column(Float)
    
    # Resolution
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolution_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    asset = relationship("Asset", back_populates="alerts")
    user = relationship("User", back_populates="alerts")
    resolver = relationship("User", foreign_keys=[resolved_by])

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    report_type = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Report data
    parameters = Column(JSON, default=dict)
    data = Column(JSON, default=dict)
    file_path = Column(String(500))
    file_format = Column(String(10))  # pdf, csv, json, xlsx
    
    # Schedule
    is_scheduled = Column(Boolean, default=False)
    schedule_cron = Column(String(50))  # Cron expression
    last_generated_at = Column(DateTime(timezone=True))
    next_generation_at = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(50), default="pending")  # pending, generating, completed, failed
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="reports")
