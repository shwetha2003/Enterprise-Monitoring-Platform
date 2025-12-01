from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
import random
from datetime import datetime, timedelta

from app.database import get_db
from app.auth import get_current_user, require_role
from app.models import User, Asset, AssetType, AssetStatus, Metric
from app.schemas import (
    AssetCreate, AssetUpdate, AssetResponse,
    MetricCreate, MetricResponse
)
from app.services.asset_monitor import AssetMonitor
from app.services.websocket_manager import websocket_manager

router = APIRouter()

@router.get("/", response_model=List[AssetResponse])
def get_assets(
    skip: int = 0,
    limit: int = 100,
    asset_type: Optional[AssetType] = None,
    status: Optional[AssetStatus] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all assets with filtering"""
    query = db.query(Asset)
    
    # Apply filters
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    if status:
        query = query.filter(Asset.status == status)
    if search:
        query = query.filter(
            or_(
                Asset.name.ilike(f"%{search}%"),
                Asset.description.ilike(f"%{search}%"),
                Asset.symbol.ilike(f"%{search}%")
            )
        )
    
    # Apply pagination
    assets = query.offset(skip).limit(limit).all()
    return assets

@router.post("/", response_model=AssetResponse)
def create_asset(
    asset_data: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("manager"))
):
    """Create a new asset"""
    # Check for duplicate serial number if provided
    if asset_data.serial_number:
        existing = db.query(Asset).filter(
            Asset.serial_number == asset_data.serial_number
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Serial number already exists")
    
    # Create asset
    db_asset = Asset(**asset_data.dict())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    
    return db_asset

@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get asset by ID"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    asset_data: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("manager"))
):
    """Update asset"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Update fields
    update_data = asset_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
    
    db.commit()
    db.refresh(asset)
    
    return asset

@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Delete asset"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    db.delete(asset)
    db.commit()
    
    return {"message": "Asset deleted successfully"}

@router.get("/{asset_id}/metrics", response_model=List[MetricResponse])
def get_asset_metrics(
    asset_id: int,
    metric_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get metrics for an asset"""
    # Check if asset exists
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    query = db.query(Metric).filter(Metric.asset_id == asset_id)
    
    # Apply filters
    if metric_type:
        query = query.filter(Metric.metric_type == metric_type)
    if start_time:
        query = query.filter(Metric.timestamp >= start_time)
    if end_time:
        query = query.filter(Metric.timestamp <= end_time)
    
    # Order by timestamp and limit
    metrics = query.order_by(Metric.timestamp.desc()).limit(limit).all()
    return metrics

@router.post("/{asset_id}/metrics", response_model=MetricResponse)
def create_asset_metric(
    asset_id: int,
    metric_data: MetricCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("technician"))
):
    """Create a new metric for an asset"""
    # Check if asset exists
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Create metric
    db_metric = Metric(**metric_data.dict())
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    
    # Check for alerts in background
    background_tasks.add_task(
        AssetMonitor.check_thresholds,
        db_metric.asset_id,
        db_metric.metric_type,
        db_metric.value
    )
    
    # Send WebSocket update
    websocket_manager.broadcast({
        "type": "metric_update",
        "data": {
            "asset_id": asset_id,
            "metric_type": metric_data.metric_type,
            "value": metric_data.value,
            "timestamp": db_metric.timestamp.isoformat()
        }
    })
    
    return db_metric

@router.get("/{asset_id}/performance")
def get_asset_performance(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get asset performance data"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Get recent metrics
    recent_metrics = db.query(Metric).filter(
        Metric.asset_id == asset_id
    ).order_by(Metric.timestamp.desc()).limit(100).all()
    
    # Calculate performance metrics
    if asset.asset_type == AssetType.FINANCIAL:
        performance = {
            "current_value": asset.current_price * asset.quantity if asset.current_price else 0,
            "daily_change": random.uniform(-5, 5),  # Mock data
            "weekly_change": random.uniform(-15, 15),
            "monthly_change": random.uniform(-30, 30),
            "yearly_change": random.uniform(-50, 100),
            "volatility": random.uniform(0.1, 0.5),
            "sharpe_ratio": random.uniform(0.5, 2.0),
            "max_drawdown": random.uniform(-20, -5),
        }
    else:  # Manufacturing
        performance = {
            "uptime": asset.uptime_percentage,
            "efficiency": random.uniform(80, 100),
            "quality_rate": random.uniform(95, 100),
            "throughput": random.uniform(100, 500),
            "energy_consumption": random.uniform(100, 1000),
            "maintenance_cost": random.uniform(1000, 10000),
            "oee": random.uniform(70, 90),  # Overall Equipment Effectiveness
        }
    
    return {
        "asset": asset,
        "performance": performance,
        "recent_metrics": recent_metrics[-10:] if recent_metrics else []
    }

@router.post("/{asset_id}/simulate")
def simulate_asset_data(
    asset_id: int,
    duration_hours: int = 24,
    interval_minutes: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("technician"))
):
    """Simulate metrics for an asset (for testing)"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    metrics_created = []
    start_time = datetime.utcnow() - timedelta(hours=duration_hours)
    
    for i in range(duration_hours * 60 // interval_minutes):
        timestamp = start_time + timedelta(minutes=i * interval_minutes)
        
        if asset.asset_type == AssetType.FINANCIAL:
            # Simulate stock price
            metric = Metric(
                asset_id=asset_id,
                metric_type="stock_price",
                value=random.uniform(asset.current_price * 0.9, asset.current_price * 1.1) if asset.current_price else random.uniform(100, 500),
                unit="USD",
                timestamp=timestamp,
                metadata={"simulated": True}
            )
        else:
            # Simulate manufacturing metrics
            metric_type = random.choice(["temperature", "vibration", "pressure", "voltage"])
            if metric_type == "temperature":
                value = random.uniform(20, 100)
                unit = "°C"
            elif metric_type == "vibration":
                value = random.uniform(0, 10)
                unit = "mm/s"
            elif metric_type == "pressure":
                value = random.uniform(0, 100)
                unit = "psi"
            else:  # voltage
                value = random.uniform(200, 240)
                unit = "V"
            
            metric = Metric(
                asset_id=asset_id,
                metric_type=metric_type,
                value=value,
                unit=unit,
                timestamp=timestamp,
                metadata={"simulated": True}
            )
        
        db.add(metric)
        metrics_created.append(metric)
    
    db.commit()
    
    return {
        "message": f"Simulated {len(metrics_created)} metrics",
        "metrics_created": len(metrics_created)
    }
