from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.auth import get_current_user, require_role
from app.models import User, Alert, Asset, AlertSeverity
from app.schemas import AlertCreate, AlertUpdate, AlertResponse
from app.services.alert_service import AlertService
from app.services.websocket_manager import websocket_manager

router = APIRouter()

@router.get("/", response_model=List[AlertResponse])
def get_alerts(
    skip: int = 0,
    limit: int = 100,
    severity: Optional[AlertSeverity] = None,
    status: Optional[str] = None,
    asset_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all alerts with filtering"""
    query = db.query(Alert)
    
    # Apply filters
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)
    if asset_id:
        query = query.filter(Alert.asset_id == asset_id)
    if start_date:
        query = query.filter(Alert.created_at >= start_date)
    if end_date:
        query = query.filter(Alert.created_at <= end_date)
    
    # For non-admin users, only show their alerts or alerts for their assets
    if current_user.role.value not in ["admin", "manager"]:
        # TODO: Implement asset ownership/permission check
        pass
    
    # Order by creation date (newest first)
    alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
    return alerts

@router.post("/", response_model=AlertResponse)
def create_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("analyst"))
):
    """Create a new alert"""
    # Check if asset exists if asset_id is provided
    if alert_data.asset_id:
        asset = db.query(Asset).filter(Asset.id == alert_data.asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
    
    # Create alert
    db_alert = Alert(
        **alert_data.dict(),
        user_id=current_user.id
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    
    # Send WebSocket notification
    websocket_manager.broadcast({
        "type": "alert",
        "data": {
            "id": db_alert.id,
            "title": db_alert.title,
            "severity": db_alert.severity,
            "asset_id": db_alert.asset_id,
            "created_at": db_alert.created_at.isoformat()
        }
    })
    
    # Send email notification for critical alerts
    if db_alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
        AlertService.send_email_notification(db_alert, current_user)
    
    return db_alert

@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get alert by ID"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Check permissions
    if (current_user.role.value not in ["admin", "manager"] and 
        alert.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return alert

@router.put("/{alert_id}", response_model=AlertResponse)
def update_alert(
    alert_id: int,
    alert_data: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("analyst"))
):
    """Update alert"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Check permissions
    if (current_user.role.value not in ["admin", "manager"] and 
        alert.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update fields
    update_data = alert_data.dict(exclude_unset=True)
    
    # If resolving alert
    if update_data.get("status") in ["resolved", "closed"]:
        update_data["resolved_at"] = datetime.utcnow()
        update_data["resolved_by"] = current_user.id
    
    for field, value in update_data.items():
        setattr(alert, field, value)
    
    db.commit()
    db.refresh(alert)
    
    # Send WebSocket update
    websocket_manager.broadcast({
        "type": "alert_update",
        "data": {
            "id": alert.id,
            "status": alert.status,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None
        }
    })
    
    return alert

@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Delete alert"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    db.delete(alert)
    db.commit()
    
    return {"message": "Alert deleted successfully"}

@router.get("/stats/summary")
def get_alert_summary(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get alert statistics summary"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get alert counts by severity
    severity_counts = {}
    for severity in AlertSeverity:
        count = db.query(Alert).filter(
            Alert.severity == severity,
            Alert.created_at >= start_date
        ).count()
        severity_counts[severity.value] = count
    
    # Get alert counts by status
    status_counts = {}
    statuses = ["open", "acknowledged", "resolved", "closed"]
    for status in statuses:
        count = db.query(Alert).filter(
            Alert.status == status,
            Alert.created_at >= start_date
        ).count()
        status_counts[status] = count
    
    # Get alerts by asset type
    asset_type_counts = {}
    for asset_type in ["financial", "manufacturing"]:
        count = db.query(Alert).join(Asset).filter(
            Asset.asset_type == asset_type,
            Alert.created_at >= start_date
        ).count()
        asset_type_counts[asset_type] = count
    
    # Get trend data (alerts per day)
    trend_data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        next_date = date + timedelta(days=1)
        
        count = db.query(Alert).filter(
            Alert.created_at >= date,
            Alert.created_at < next_date
        ).count()
        
        trend_data.append({
            "date": date.date().isoformat(),
            "count": count
        })
    
    return {
        "severity_counts": severity_counts,
        "status_counts": status_counts,
        "asset_type_counts": asset_type_counts,
        "trend_data": trend_data,
        "total_alerts": sum(severity_counts.values()),
        "time_period_days": days
    }

@router.post("/bulk/acknowledge")
def acknowledge_alerts(
    alert_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("analyst"))
):
    """Acknowledge multiple alerts"""
    alerts = db.query(Alert).filter(Alert.id.in_(alert_ids)).all()
    
    for alert in alerts:
        alert.status = "acknowledged"
    
    db.commit()
    
    # Send WebSocket updates
    for alert in alerts:
        websocket_manager.broadcast({
            "type": "alert_update",
            "data": {
                "id": alert.id,
                "status": alert.status
            }
        })
    
    return {"message": f"{len(alerts)} alerts acknowledged"}

@router.post("/test/trigger")
def trigger_test_alert(
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Trigger a test alert (for testing notifications)"""
    alert = Alert(
        title="Test Alert",
        description=f"This is a test alert with {severity} severity",
        severity=severity,
        user_id=current_user.id,
        status="open"
    )
    
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    # Send WebSocket notification
    websocket_manager.broadcast({
        "type": "alert",
        "data": {
            "id": alert.id,
            "title": alert.title,
            "severity": alert.severity,
            "created_at": alert.created_at.isoformat()
        }
    })
    
    return {
        "message": "Test alert triggered",
        "alert": alert
    }
