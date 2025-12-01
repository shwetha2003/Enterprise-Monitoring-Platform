from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.database import get_db
from app.auth import get_current_user
from app.models import User, Asset, Alert, Metric, AssetType, AssetStatus
from app.schemas import DashboardStats, AssetPerformance

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics"""
    # Count assets
    total_assets = db.query(Asset).count()
    active_assets = db.query(Asset).filter(Asset.status == AssetStatus.ACTIVE).count()
    
    # Count alerts
    total_alerts = db.query(Alert).count()
    open_alerts = db.query(Alert).filter(Alert.status == "open").count()
    critical_alerts = db.query(Alert).filter(
        Alert.severity == "critical",
        Alert.status.in_(["open", "acknowledged"])
    ).count()
    
    # Calculate average health score
    avg_health_score = db.query(func.avg(Asset.health_score)).filter(
        Asset.status == AssetStatus.ACTIVE
    ).scalar() or 0
    
    # Count users
    total_users = db.query(User).filter
