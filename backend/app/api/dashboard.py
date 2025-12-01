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
    total_users = db.query(User).filter(User.is_active == True).count()
    
    return DashboardStats(
        total_assets=total_assets,
        active_assets=active_assets,
        total_alerts=total_alerts,
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        avg_health_score=round(avg_health_score, 2),
        total_users=total_users
    )

@router.get("/performance/top")
def get_top_performing_assets(
    limit: int = 10,
    asset_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top performing assets"""
    query = db.query(Asset)
    
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    
    # Get assets with highest health score
    assets = query.order_by(desc(Asset.health_score)).limit(limit).all()
    
    performance_data = []
    for asset in assets:
        # Get recent metrics for performance calculation
        recent_metrics = db.query(Metric).filter(
            Metric.asset_id == asset.id
        ).order_by(desc(Metric.timestamp)).limit(10).all()
        
        if asset.asset_type == AssetType.FINANCIAL:
            daily_change = 0
            if asset.current_price and asset.purchase_price:
                daily_change = ((asset.current_price - asset.purchase_price) / asset.purchase_price) * 100
        else:
            # For manufacturing, calculate based on recent metrics
            daily_change = 0
            if len(recent_metrics) >= 2:
                daily_change = ((recent_metrics[0].value - recent_metrics[-1].value) / recent_metrics[-1].value) * 100
        
        # Count active alerts
        alerts_count = db.query(Alert).filter(
            Alert.asset_id == asset.id,
            Alert.status.in_(["open", "acknowledged"])
        ).count()
        
        performance_data.append({
            "asset_id": asset.id,
            "asset_name": asset.name,
            "asset_type": asset.asset_type.value,
            "current_value": asset.current_price * asset.quantity if asset.current_price else asset.health_score,
            "daily_change": round(daily_change, 2),
            "weekly_change": round(daily_change * 7, 2),  # Simplified
            "health_score": asset.health_score,
            "alerts_count": alerts_count,
            "status": asset.status.value
        })
    
    return performance_data

@router.get("/activity/recent")
def get_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent activity across the platform"""
    activities = []
    
    # Get recent alerts
    recent_alerts = db.query(Alert).order_by(desc(Alert.created_at)).limit(limit // 2).all()
    for alert in recent_alerts:
        activities.append({
            "type": "alert",
            "id": alert.id,
            "title": alert.title,
            "severity": alert.severity.value,
            "asset_id": alert.asset_id,
            "timestamp": alert.created_at.isoformat(),
            "user": alert.user.full_name if alert.user else None
        })
    
    # Get recent metrics (grouped by asset)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_metrics = db.query(Metric).filter(
        Metric.timestamp >= one_hour_ago
    ).order_by(desc(Metric.timestamp)).limit(limit // 2).all()
    
    # Group metrics by asset
    asset_metrics = {}
    for metric in recent_metrics:
        if metric.asset_id not in asset_metrics:
            asset = db.query(Asset).filter(Asset.id == metric.asset_id).first()
            asset_metrics[metric.asset_id] = {
                "asset_name": asset.name if asset else f"Asset {metric.asset_id}",
                "metrics": [],
                "last_update": metric.timestamp
            }
        
        asset_metrics[metric.asset_id]["metrics"].append({
            "type": metric.metric_type,
            "value": metric.value,
            "unit": metric.unit
        })
    
    # Add metric activities
    for asset_id, data in list(asset_metrics.items())[:limit // 2]:
        activities.append({
            "type": "metric_update",
            "asset_id": asset_id,
            "asset_name": data["asset_name"],
            "metric_count": len(data["metrics"]),
            "timestamp": data["last_update"].isoformat(),
            "sample_metrics": data["metrics"][:3]  # Show first 3 metrics
        })
    
    # Sort activities by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return activities[:limit]

@router.get("/predictions/overview")
def get_predictions_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overview of predictions and forecasts"""
    from app.services.predictive_analytics import PredictiveAnalytics
    
    # Get assets that need maintenance prediction
    manufacturing_assets = db.query(Asset).filter(
        Asset.asset_type == AssetType.MANUFACTURING,
        Asset.status == AssetStatus.ACTIVE
    ).limit(5).all()
    
    maintenance_predictions = []
    for asset in manufacturing_assets:
        prediction = PredictiveAnalytics.predict_maintenance(
            asset_id=asset.id,
            days_ahead=7,
            db=db
        )
        
        if prediction and prediction["failure_probability"] > 0.5:
            maintenance_predictions.append({
                "asset_id": asset.id,
                "asset_name": asset.name,
                "failure_probability": prediction["failure_probability"],
                "predicted_failure_date": prediction.get("predicted_failure_date"),
                "recommendation": "Schedule maintenance" if prediction["failure_probability"] > 0.7 else "Monitor closely"
            })
    
    # Get financial performance predictions (simulated)
    financial_assets = db.query(Asset).filter(
        Asset.asset_type == AssetType.FINANCIAL,
        Asset.status == AssetStatus.ACTIVE
    ).limit(5).all()
    
    performance_predictions = []
    for asset in financial_assets:
        # Simulate prediction
        import random
        performance_predictions.append({
            "asset_id": asset.id,
            "asset_name": asset.name,
            "symbol": asset.symbol,
            "predicted_return": random.uniform(-10, 20),
            "confidence": random.uniform(0.6, 0.95),
            "recommendation": "Buy" if random.random() > 0.5 else "Hold" if random.random() > 0.3 else "Sell"
        })
    
    return {
        "maintenance_predictions": maintenance_predictions,
        "performance_predictions": performance_predictions,
        "total_predictions": len(maintenance_predictions) + len(performance_predictions)
    }

@router.get("/geographic/overview")
def get_geographic_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get geographic distribution of assets"""
    # Group assets by location
    locations = db.query(
        Asset.location,
        func.count(Asset.id).label('count'),
        func.avg(Asset.health_score).label('avg_health'),
        Asset.asset_type
    ).filter(
        Asset.location.isnot(None)
    ).group_by(
        Asset.location, Asset.asset_type
    ).all()
    
    # Format data for map
    map_data = []
    for loc in locations:
        if loc.location:
            # Parse location (assuming format: "City, Country" or coordinates)
            map_data.append({
                "location": loc.location,
                "count": loc.count,
                "avg_health": round(loc.avg_health, 2),
                "asset_type": loc.asset_type.value,
                "coordinates": _geocode_location(loc.location)  # Mock function
            })
    
    return {
        "locations": map_data,
        "total_locations": len(map_data),
        "assets_with_location": sum(loc.count for loc in locations)
    }

def _geocode_location(location: str) -> Dict[str, float]:
    """Mock geocoding function - in production, use a geocoding service"""
    # This is a mock implementation
    import hashlib
    import random
    
    # Generate deterministic but random coordinates based on location string
    hash_obj = hashlib.md5(location.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    
    # Generate coordinates within reasonable ranges
    lat = 20 + (hash_int % 50)  # 20-70 degrees
    lng = -120 + (hash_int % 120)  # -120 to 0 degrees
    
    # Add some randomness
    lat += random.uniform(-0.5, 0.5)
    lng += random.uniform(-0.5, 0.5)
    
    return {"lat": lat, "lng": lng}
