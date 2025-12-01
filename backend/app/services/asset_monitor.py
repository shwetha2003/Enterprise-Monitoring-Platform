import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Asset, Metric, Alert, AlertSeverity, AssetType
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)

class AssetMonitor:
    """Service for monitoring assets and checking thresholds"""
    
    # Threshold configurations
    THRESHOLDS = {
        "temperature": {"min": 20, "max": 80, "critical": 90},
        "vibration": {"min": 0, "max": 5, "critical": 8},
        "pressure": {"min": 0, "max": 80, "critical": 95},
        "voltage": {"min": 210, "max": 230, "critical": 240},
        "current": {"min": 0, "max": 10, "critical": 15},
        "stock_price": {"change_percent": 5, "critical_change": 10},
    }
    
    @staticmethod
    def check_thresholds(asset_id: int, metric_type: str, value: float):
        """Check if a metric value exceeds thresholds"""
        logger.info(f"Checking thresholds for asset {asset_id}, metric {metric_type}, value {value}")
        
        # Get asset
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            if not asset:
                logger.warning(f"Asset {asset_id} not found")
                return
            
            # Check thresholds based on metric type
            thresholds = AssetMonitor.THRESHOLDS.get(metric_type)
            if not thresholds:
                logger.debug(f"No thresholds defined for metric type: {metric_type}")
                return
            
            # Check different types of thresholds
            if metric_type in ["temperature", "vibration", "pressure", "voltage", "current"]:
                AssetMonitor._check_numeric_threshold(
                    db, asset, metric_type, value, thresholds
                )
            elif metric_type == "stock_price":
                AssetMonitor._check_stock_threshold(
                    db, asset, metric_type, value, thresholds
                )
            
            # Update asset health score
            AssetMonitor._update_health_score(db, asset)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error checking thresholds: {e}")
            db.rollback()
        finally:
            db.close()
    
    @staticmethod
    def _check_numeric_threshold(
        db: Session, 
        asset: Asset, 
        metric_type: str, 
        value: float, 
        thresholds: Dict[str, float]
    ):
        """Check numeric thresholds (min/max)"""
        alert_triggered = False
        severity = AlertSeverity.MEDIUM
        description = ""
        
        # Check critical threshold
        if "critical" in thresholds and value > thresholds["critical"]:
            alert_triggered = True
            severity = AlertSeverity.CRITICAL
            description = f"Critical {metric_type}: {value} exceeds critical threshold {thresholds['critical']}"
        
        # Check max threshold
        elif "max" in thresholds and value > thresholds["max"]:
            alert_triggered = True
            severity = AlertSeverity.HIGH
            description = f"High {metric_type}: {value} exceeds maximum threshold {thresholds['max']}"
        
        # Check min threshold
        elif "min" in thresholds and value < thresholds["min"]:
            alert_triggered = True
            severity = AlertSeverity.MEDIUM
            description = f"Medium {metric_type}: {value} below minimum threshold {thresholds['min']}"
        
        # Create alert if threshold exceeded
        if alert_triggered:
            alert = Alert(
                asset_id=asset.id,
                title=f"{metric_type.capitalize()} Alert for {asset.name}",
                description=description,
                severity=severity,
                metric_type=metric_type,
                threshold_value=thresholds.get("max") or thresholds.get("min") or thresholds.get("critical"),
                actual_value=value,
                status="open"
            )
            
            db.add(alert)
            
            # Send notifications
            AlertService.send_alert_notifications(alert, asset)
    
    @staticmethod
    def _check_stock_threshold(
        db: Session,
        asset: Asset,
        metric_type: str,
        value: float,
        thresholds: Dict[str, float]
    ):
        """Check stock price change thresholds"""
        # Get previous price for comparison
        prev_metric = db.query(Metric).filter(
            Metric.asset_id == asset.id,
            Metric.metric_type == metric_type
        ).order_by(Metric.timestamp.desc()).offset(1).first()
        
        if not prev_metric or asset.current_price is None:
            return
        
        # Calculate percentage change
        prev_value = prev_metric.value
        change_percent = abs((value - prev_value) / prev_value * 100)
        
        alert_triggered = False
        severity = AlertSeverity.MEDIUM
        description = ""
        
        # Check critical change
        if change_percent > thresholds.get("critical_change", 10):
            alert_triggered = True
            severity = AlertSeverity.CRITICAL
            direction = "increased" if value > prev_value else "decreased"
            description = f"Critical stock movement: {asset.symbol} {direction} by {change_percent:.2f}%"
        
        # Check significant change
        elif change_percent > thresholds.get("change_percent", 5):
            alert_triggered = True
            severity = AlertSeverity.HIGH
            direction = "increased" if value > prev_value else "decreased"
            description = f"Significant stock movement: {asset.symbol} {direction} by {change_percent:.2f}%"
        
        # Create alert if threshold exceeded
        if alert_triggered:
            alert = Alert(
                asset_id=asset.id,
                title=f"Stock Price Alert for {asset.symbol}",
                description=description,
                severity=severity,
                metric_type=metric_type,
                threshold_value=thresholds.get("change_percent"),
                actual_value=change_percent,
                status="open"
            )
            
            db.add(alert)
            
            # Send notifications
            AlertService.send_alert_notifications(alert, asset)
    
    @staticmethod
    def _update_health_score(db: Session, asset: Asset):
        """Update asset health score based on recent alerts and metrics"""
        # Get recent alerts (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_alerts = db.query(Alert).filter(
            Alert.asset_id == asset.id,
            Alert.created_at >= week_ago,
            Alert.status.in_(["open", "acknowledged"])
        ).all()
        
        # Calculate health score penalty based on alerts
        penalty = 0
        for alert in recent_alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                penalty += 20
            elif alert.severity == AlertSeverity.HIGH:
                penalty += 10
            elif alert.severity == AlertSeverity.MEDIUM:
                penalty += 5
            elif alert.severity == AlertSeverity.LOW:
                penalty += 2
        
        # Get recent metrics to check for anomalies
        recent_metrics = db.query(Metric).filter(
            Metric.asset_id == asset.id,
            Metric.timestamp >= week_ago
        ).all()
        
        # Calculate health score (100 - penalty, minimum 0)
        health_score = max(0, 100 - penalty)
        
        # Apply additional adjustments based on asset type
        if asset.asset_type == AssetType.MANUFACTURING:
            # Check if maintenance is overdue
            if asset.next_maintenance_date and asset.next_maintenance_date < datetime.utcnow():
                health_score = max(0, health_score - 30)
        
        # Update asset health score
        asset.health_score = min(100, health_score)
        
        # Update asset status based on health score
        if health_score < 30:
            asset.status = "failed"
        elif health_score < 70:
            asset.status = "maintenance"
        elif asset.status == "failed" and health_score >= 70:
            asset.status = "active"
    
    @staticmethod
    def calculate_asset_value(asset: Asset) -> float:
        """Calculate current value of an asset"""
        if asset.asset_type == AssetType.FINANCIAL:
            if asset.current_price and asset.quantity:
                return asset.current_price * asset.quantity
            elif asset.purchase_price and asset.quantity:
                return asset.purchase_price * asset.quantity
        else:
            # For manufacturing assets, value is based on health score and purchase price
            base_value = 100000  # Default base value
            depreciation_factor = asset.health_score / 100
            
            # Get age in years
            if asset.installation_date:
                from datetime import datetime
                age_years = (datetime.utcnow() - asset.installation_date).days / 365
                age_depreciation = max(0.1, 1 - (age_years * 0.1))  # 10% per year
            else:
                age_depreciation = 0.7  # Default if no installation date
            
            return base_value * depreciation_factor * age_depreciation
        
        return 0
