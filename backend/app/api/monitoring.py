from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import random

from app.database import get_db
from app.auth import get_current_user, require_role
from app.models import User, Asset, Metric, AssetType
from app.schemas import MetricResponse
from app.services.asset_monitor import AssetMonitor
from app.services.predictive_analytics import PredictiveAnalytics
from app.services.websocket_manager import websocket_manager

router = APIRouter()

@router.get("/health/overview")
def get_health_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get health overview of all assets"""
    # Get asset counts by status
    status_counts = {}
    for status in ["active", "inactive", "maintenance", "failed"]:
        count = db.query(Asset).filter(Asset.status == status).count()
        status_counts[status] = count
    
    # Get average health score by asset type
    health_scores = {}
    for asset_type in AssetType:
        avg_score = db.query(func.avg(Asset.health_score)).filter(
            Asset.asset_type == asset_type,
            Asset.status == "active"
        ).scalar()
        health_scores[asset_type.value] = round(avg_score or 0, 2)
    
    # Get assets needing attention (health score < 70)
    attention_needed = db.query(Asset).filter(
        Asset.health_score < 70,
        Asset.status == "active"
    ).count()
    
    # Get recent metrics count
    last_hour = datetime.utcnow() - timedelta(hours=1)
    recent_metrics = db.query(Metric).filter(
        Metric.timestamp >= last_hour
    ).count()
    
    return {
        "status_counts": status_counts,
        "health_scores": health_scores,
        "attention_needed": attention_needed,
        "recent_metrics": recent_metrics,
        "total_assets": sum(status_counts.values())
    }

@router.get("/metrics/realtime")
async def get_realtime_metrics(
    asset_ids: List[int] = None,
    metric_types: List[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get real-time metrics for specified assets"""
    query = db.query(Metric)
    
    if asset_ids:
        query = query.filter(Metric.asset_id.in_(asset_ids))
    if metric_types:
        query = query.filter(Metric.metric_type.in_(metric_types))
    
    # Get metrics from last 5 minutes
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    query = query.filter(Metric.timestamp >= five_minutes_ago)
    
    metrics = query.order_by(desc(Metric.timestamp)).limit(1000).all()
    
    # Group by asset and metric type
    grouped_metrics = {}
    for metric in metrics:
        if metric.asset_id not in grouped_metrics:
            grouped_metrics[metric.asset_id] = {}
        if metric.metric_type not in grouped_metrics[metric.asset_id]:
            grouped_metrics[metric.asset_id][metric.metric_type] = []
        
        grouped_metrics[metric.asset_id][metric.metric_type].append({
            "value": metric.value,
            "timestamp": metric.timestamp.isoformat(),
            "unit": metric.unit
        })
    
    return grouped_metrics

@router.get("/predictive/maintenance")
def get_predictive_maintenance(
    days_ahead: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get predictive maintenance schedule"""
    # Get manufacturing assets
    assets = db.query(Asset).filter(
        Asset.asset_type == AssetType.MANUFACTURING,
        Asset.status == "active"
    ).all()
    
    predictions = []
    for asset in assets:
        # Use predictive analytics service
        prediction = PredictiveAnalytics.predict_maintenance(
            asset_id=asset.id,
            days_ahead=days_ahead,
            db=db
        )
        
        if prediction:
            predictions.append({
                "asset_id": asset.id,
                "asset_name": asset.name,
                "prediction": prediction,
                "recommended_action": "Schedule maintenance" if prediction["failure_probability"] > 0.7 else "Monitor",
                "urgency": "high" if prediction["failure_probability"] > 0.8 else "medium" if prediction["failure_probability"] > 0.6 else "low"
            })
    
    # Sort by failure probability (descending)
    predictions.sort(key=lambda x: x["prediction"]["failure_probability"], reverse=True)
    
    return {
        "predictions": predictions,
        "total_assets": len(assets),
        "high_risk_count": sum(1 for p in predictions if p["prediction"]["failure_probability"] > 0.7)
    }

@router.get("/trends/{asset_id}")
def get_asset_trends(
    asset_id: int,
    metric_type: str,
    period: str = "24h",  # 24h, 7d, 30d
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get trend data for a specific asset and metric"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Determine time range
    now = datetime.utcnow()
    if period == "24h":
        start_time = now - timedelta(hours=24)
        interval = "1 hour"
    elif period == "7d":
        start_time = now - timedelta(days=7)
        interval = "1 day"
    elif period == "30d":
        start_time = now - timedelta(days=30)
        interval = "1 day"
    else:
        start_time = now - timedelta(hours=24)
        interval = "1 hour"
    
    # Get aggregated metrics
    # Note: In production, you'd use TimescaleDB hyperfunctions for time_bucket
    metrics = db.query(Metric).filter(
        Metric.asset_id == asset_id,
        Metric.metric_type == metric_type,
        Metric.timestamp >= start_time
    ).order_by(Metric.timestamp).all()
    
    # Calculate basic statistics
    values = [m.value for m in metrics]
    
    if values:
        stats = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0,
            "std_dev": (sum((x - sum(values)/len(values))**2 for x in values) / len(values))**0.5 if len(values) > 1 else 0
        }
    else:
        stats = {
            "min": 0,
            "max": 0,
            "avg": 0,
            "current": 0,
            "std_dev": 0
        }
    
    # Prepare data for chart
    chart_data = []
    for metric in metrics[-100:]:  # Limit to 100 points for chart
        chart_data.append({
            "timestamp": metric.timestamp.isoformat(),
            "value": metric.value
        })
    
    # Detect anomalies
    anomalies = []
    if values and len(values) > 10:
        mean = stats["avg"]
        std = stats["std_dev"]
        for i, value in enumerate(values):
            if abs(value - mean) > 3 * std:
                anomalies.append({
                    "index": i,
                    "value": value,
                    "timestamp": metrics[i].timestamp.isoformat() if i < len(metrics) else None
                })
    
    return {
        "asset": {
            "id": asset.id,
            "name": asset.name,
            "type": asset.asset_type
        },
        "metric_type": metric_type,
        "period": period,
        "statistics": stats,
        "chart_data": chart_data,
        "anomalies": anomalies[:10],  # Limit anomalies
        "total_metrics": len(metrics)
    }

@router.post("/webhook/simulate")
async def simulate_webhook_data(
    background_tasks: BackgroundTasks,
    asset_count: int = 10,
    metric_count: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    """Simulate incoming webhook data (for testing)"""
    # Get random assets
    assets = db.query(Asset).limit(asset_count).all()
    
    if not assets:
        raise HTTPException(status_code=404, detail="No assets found")
    
    # Generate simulated metrics in background
    background_tasks.add_task(
        _generate_simulated_metrics,
        assets,
        metric_count,
        db
    )
    
    return {
        "message": f"Started simulating metrics for {len(assets)} assets",
        "expected_metrics": len(assets) * metric_count
    }

async def _generate_simulated_metrics(assets, metric_count, db):
    """Background task to generate simulated metrics"""
    from app.models import Metric
    from datetime import datetime, timedelta
    
    for asset in assets:
        for i in range(metric_count):
            timestamp = datetime.utcnow() - timedelta(minutes=i)
            
            if asset.asset_type == AssetType.FINANCIAL:
                metric_type = "stock_price"
                value = random.uniform(100, 500)
                unit = "USD"
            else:
                metric_type = random.choice(["temperature", "vibration", "pressure"])
                if metric_type == "temperature":
                    value = random.uniform(20, 100)
                    unit = "°C"
                elif metric_type == "vibration":
                    value = random.uniform(0, 10)
                    unit = "mm/s"
                else:  # pressure
                    value = random.uniform(0, 100)
                    unit = "psi"
            
            metric = Metric(
                asset_id=asset.id,
                metric_type=metric_type,
                value=value,
                unit=unit,
                timestamp=timestamp,
                metadata={"simulated": True, "batch": "webhook_sim"}
            )
            
            db.add(metric)
        
        # Commit every 100 metrics
        if i % 100 == 0:
            db.commit()
    
    db.commit()
    
    # Send WebSocket notification
    websocket_manager.broadcast({
        "type": "batch_update",
        "data": {
            "message": f"Simulated {len(assets) * metric_count} metrics",
            "timestamp": datetime.utcnow().isoformat()
        }
    })
