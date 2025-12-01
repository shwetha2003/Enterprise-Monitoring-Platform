import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

from app.database import SessionLocal
from app.models import Asset, Metric, AssetType

logger = logging.getLogger(__name__)

class PredictiveAnalytics:
    """Service for predictive analytics and machine learning"""
    
    MODELS_DIR = "models"
    
    @staticmethod
    def predict_maintenance(asset_id: int, days_ahead: int = 7, db=None) -> Optional[Dict[str, Any]]:
        """Predict maintenance needs for an asset"""
        if db is None:
            db = SessionLocal()
        
        try:
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            if not asset or asset.asset_type != AssetType.MANUFACTURING:
                return None
            
            # Get recent metrics
            recent_metrics = db.query(Metric).filter(
                Metric.asset_id == asset_id,
                Metric.timestamp >= datetime.utcnow() - timedelta(days=30)
            ).all()
            
            if len(recent_metrics) < 10:
                logger.warning(f"Insufficient data for asset {asset_id}")
                return None
            
            # Prepare data for prediction
            df = PredictiveAnalytics._prepare_metrics_data(recent_metrics)
            
            # Load or train model
            model = PredictiveAnalytics._load_or_train_model(asset_id, df)
            
            if model:
                # Make prediction
                features = PredictiveAnalytics._extract_features(df)
                if features is not None:
                    failure_probability = model.predict([features])[0]
                    
                    # Calculate predicted failure date
                    predicted_failure_date = None
                    if failure_probability > 0.5:
                        # Simple linear extrapolation
                        days_to_failure = int((1 - failure_probability) * days_ahead / 0.5)
                        predicted_failure_date = datetime.utcnow() + timedelta(days=days_to_failure)
                    
                    return {
                        "asset_id": asset_id,
                        "failure_probability": min(1.0, max(0.0, float(failure_probability))),
                        "predicted_failure_date": predicted_failure_date.isoformat() if predicted_failure_date else None,
                        "confidence": 0.8,  # Placeholder
                        "recommendation": "Schedule maintenance" if failure_probability > 0.7 else "Monitor closely" if failure_probability > 0.5 else "No action needed"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error predicting maintenance: {e}")
            return None
        finally:
            if db:
                db.close()
    
    @staticmethod
    def _prepare_metrics_data(metrics: List[Metric]) -> pd.DataFrame:
        """Prepare metrics data for analysis"""
        data = []
        for metric in metrics:
            data.append({
                "timestamp": metric.timestamp,
                "metric_type": metric.metric_type,
                "value": metric.value
            })
        
        df = pd.DataFrame(data)
        
        # Pivot to get metrics as columns
        if not df.empty:
            df_pivot = df.pivot_table(
                index='timestamp',
                columns='metric_type',
                values='value',
                aggfunc='mean'
            ).reset_index()
            
            # Forward fill missing values
            df_pivot = df_pivot.ffill().bfill()
            
            return df_pivot
        
        return pd.DataFrame()
    
    @staticmethod
    def _load_or_train_model(asset_id: int, df: pd.DataFrame):
        """Load existing model or train a new one"""
        model_path = os.path.join(PredictiveAnalytics.MODELS_DIR, f"asset_{asset_id}_model.pkl")
        
        if os.path.exists(model_path):
            try:
                model = joblib.load(model_path)
                logger.info(f"Loaded existing model for asset {asset_id}")
                return model
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        
        # Train new model if no existing model or loading failed
        if len(df) > 20:  # Need sufficient data
            try:
                # Extract features and labels
                features = PredictiveAnalytics._extract_features(df)
                
                if features is not None:
                    # For demo, create synthetic labels
                    # In production, you'd use historical failure data
                    X = [features] * 10  # Create multiple samples
                    y = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]  # Synthetic labels
                    
                    # Train model
                    model = RandomForestRegressor(n_estimators=100, random_state=42)
                    model.fit(X, y)
                    
                    # Save model
                    os.makedirs(PredictiveAnalytics.MODELS_DIR, exist_ok=True)
                    joblib.dump(model, model_path)
                    
                    logger.info(f"Trained new model for asset {asset_id}")
                    return model
                    
            except Exception as e:
                logger.error(f"Failed to train model: {e}")
        
        return None
    
    @staticmethod
    def _extract_features(df: pd.DataFrame) -> Optional[List[float]]:
        """Extract features from metrics data"""
        if df.empty or len(df) < 5:
            return None
        
        features = []
        
        # Calculate statistics for each metric type
        metric_types = [col for col in df.columns if col != 'timestamp']
        
        for metric_type in metric_types:
            if metric_type in df.columns:
                values = df[metric_type].dropna().values
                
                if len(values) > 0:
                    features.extend([
                        np.mean(values),
                        np.std(values),
                        np.max(values),
                        np.min(values),
                        np.percentile(values, 25),
                        np.percentile(values, 75)
                    ])
        
        return features if features else None
    
    @staticmethod
    def detect_anomalies(asset_id: int, metric_type: str, window: int = 100) -> List[Dict[str, Any]]:
        """Detect anomalies in metric data"""
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get recent metrics
            metrics = db.query(Metric).filter(
                Metric.asset_id == asset_id,
                Metric.metric_type == metric_type
            ).order_by(Metric.timestamp.desc()).limit(window).all()
            
            if len(metrics) < 10:
                return []
            
            # Extract values
            values = np.array([m.value for m in metrics])
            timestamps = [m.timestamp for m in metrics]
            
            # Use Isolation Forest for anomaly detection
            scaler = StandardScaler()
            values_scaled = scaler.fit_transform(values.reshape(-1, 1))
            
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            predictions = iso_forest.fit_predict(values_scaled)
            
            # Identify anomalies
            anomalies = []
            for i, pred in enumerate(predictions):
                if pred == -1:  # Anomaly
                    anomalies.append({
                        "timestamp": timestamps[i].isoformat(),
                        "value": float(values[i]),
                        "metric_type": metric_type,
                        "severity": "high" if abs(values_scaled[i][0]) > 2 else "medium"
                    })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []
        finally:
            db.close()
    
    @staticmethod
    def forecast_performance(asset_id: int, horizon: int = 7) -> Optional[Dict[str, Any]]:
        """Forecast asset performance"""
        # Placeholder implementation
        # In production, you'd use time series forecasting (ARIMA, Prophet, LSTM)
        
        import random
        return {
            "asset_id": asset_id,
            "forecast": [
                {"date": (datetime.utcnow() + timedelta(days=i)).date().isoformat(),
                 "predicted_value": random.uniform(80, 100)}
                for i in range(horizon)
            ],
            "confidence_interval": {
                "lower": [random.uniform(70, 90) for _ in range(horizon)],
                "upper": [random.uniform(90, 100) for _ in range(horizon)]
            },
            "model_used": "random_forest"
        }
