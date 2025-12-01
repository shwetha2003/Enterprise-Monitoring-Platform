import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from datetime import datetime

from app.config import settings
from app.models import Alert, Asset, User
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

class AlertService:
    """Service for managing alert notifications"""
    
    @staticmethod
    def send_email_notification(alert: Alert, user: User = None):
        """Send email notification for an alert"""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured, skipping email notification")
            return
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"
            msg["From"] = settings.SMTP_USER
            msg["To"] = user.email if user else "admin@example.com"
            
            # Create HTML content
            html = f"""
            <html>
            <body>
                <h2>Alert Notification</h2>
                <p><strong>Title:</strong> {alert.title}</p>
                <p><strong>Severity:</strong> {alert.severity}</p>
                <p><strong>Description:</strong> {alert.description or 'No description'}</p>
                <p><strong>Asset:</strong> {alert.asset.name if alert.asset else 'N/A'}</p>
                <p><strong>Time:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <br>
                <p>Please log in to the monitoring platform to view and manage this alert.</p>
                <p><a href="http://localhost:3000/alerts/{alert.id}">View Alert</a></p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html, "html"))
            
            # Send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email notification sent for alert {alert.id}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    @staticmethod
    def send_alert_notifications(alert: Alert, asset: Asset = None):
        """Send all notifications for an alert"""
        # Send WebSocket notification
        websocket_manager.broadcast({
            "type": "alert",
            "data": {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity.value,
                "asset_id": alert.asset_id,
                "asset_name": asset.name if asset else None,
                "timestamp": alert.created_at.isoformat(),
                "description": alert.description
            }
        })
        
        # TODO: Send SMS notifications for critical alerts
        # TODO: Send Slack/Teams notifications
        # TODO: Send push notifications
        
        logger.info(f"Notifications sent for alert {alert.id}")
    
    @staticmethod
    def get_users_to_notify(alert: Alert) -> List[User]:
        """Get list of users to notify for an alert"""
        # In a real implementation, this would:
        # 1. Get users based on alert severity and asset
        # 2. Check user notification preferences
        # 3. Filter users who should receive notifications
        
        # For now, return empty list
        return []
    
    @staticmethod
    def create_maintenance_alert(asset: Asset, reason: str, severity: str = "medium"):
        """Create a maintenance alert for an asset"""
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            alert = Alert(
                asset_id=asset.id,
                title=f"Maintenance Required: {asset.name}",
                description=f"Maintenance required: {reason}",
                severity=severity,
                status="open"
            )
            
            db.add(alert)
            db.commit()
            
            # Send notifications
            AlertService.send_alert_notifications(alert, asset)
            
            return alert
            
        except Exception as e:
            logger.error(f"Failed to create maintenance alert: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def check_scheduled_maintenance():
        """Check for scheduled maintenance and create alerts"""
        from app.database import SessionLocal
        from datetime import datetime, timedelta
        
        db = SessionLocal()
        
        try:
            # Get assets with upcoming maintenance
            upcoming_maintenance = db.query(Asset).filter(
                Asset.next_maintenance_date.isnot(None),
                Asset.next_maintenance_date <= datetime.utcnow() + timedelta(days=7),
                Asset.status == "active"
            ).all()
            
            alerts_created = []
            for asset in upcoming_maintenance:
                days_until = (asset.next_maintenance_date - datetime.utcnow()).days
                
                # Create alert if maintenance is due in 3 days or less
                if days_until <= 3:
                    severity = "high" if days_until <= 1 else "medium"
                    reason = f"Maintenance scheduled for {asset.next_maintenance_date.date()}"
                    
                    alert = AlertService.create_maintenance_alert(asset, reason, severity)
                    if alert:
                        alerts_created.append(alert)
            
            logger.info(f"Created {len(alerts_created)} maintenance alerts")
            return alerts_created
            
        except Exception as e:
            logger.error(f"Error checking scheduled maintenance: {e}")
            return []
        finally:
            db.close()
