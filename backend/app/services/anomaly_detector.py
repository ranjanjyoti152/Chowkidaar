"""
Chowkidaar NVR - Anomaly Detector
Unsupervised anomaly detection using Isolation Forest.
"""
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import numpy as np
from loguru import logger
import pickle
from pathlib import Path

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. Anomaly detection disabled.")


class AnomalyDetector:
    """
    Unsupervised anomaly detection using Isolation Forest.
    
    Learns normal patterns from historical data and scores new observations
    for how anomalous they are.
    
    Features used for anomaly detection:
    - Hour of day (cyclical encoding)
    - Day of week (cyclical encoding)
    - Detection count per minute
    - Object class distribution
    - Average confidence
    - Spatial distribution entropy
    """
    
    def __init__(self):
        self.models: Dict[int, IsolationForest] = {}  # Per-camera models
        self.scalers: Dict[int, StandardScaler] = {}  # Per-camera feature scalers
        self.model_metadata: Dict[int, Dict[str, Any]] = {}
        self._models_dir = Path(settings.models_path) / "anomaly_detectors"
        self._models_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        """Check if anomaly detection is available."""
        return SKLEARN_AVAILABLE
    
    def _cyclical_encode(self, value: float, max_value: float) -> Tuple[float, float]:
        """
        Encode cyclical features (hour, day) as sin/cos pair.
        This ensures 23:00 is close to 00:00.
        """
        angle = 2 * np.pi * value / max_value
        return np.sin(angle), np.cos(angle)
    
    def _extract_features(
        self,
        hour: int,
        day_of_week: int,
        detection_count: int,
        class_counts: Dict[str, int],
        avg_confidence: float,
        bbox_positions: List[Tuple[float, float]] = None
    ) -> np.ndarray:
        """
        Extract feature vector from detection data.
        
        Returns:
            Feature vector of shape (n_features,)
        """
        features = []
        
        # Cyclical hour encoding (24-hour cycle)
        hour_sin, hour_cos = self._cyclical_encode(hour, 24)
        features.extend([hour_sin, hour_cos])
        
        # Cyclical day encoding (7-day cycle)
        day_sin, day_cos = self._cyclical_encode(day_of_week, 7)
        features.extend([day_sin, day_cos])
        
        # Detection count (log-scaled to handle variance)
        features.append(np.log1p(detection_count))
        
        # Class distribution features
        main_classes = ['person', 'vehicle', 'animal', 'object']
        total = sum(class_counts.values()) if class_counts else 1
        for cls in main_classes:
            count = class_counts.get(cls, 0)
            features.append(count / total)  # Normalized count
        
        # Average confidence
        features.append(avg_confidence)
        
        # Spatial entropy (how spread out are detections)
        if bbox_positions and len(bbox_positions) > 1:
            positions = np.array(bbox_positions)
            # Calculate variance as measure of spread
            spatial_variance = np.var(positions, axis=0).sum()
            features.append(np.log1p(spatial_variance))
        else:
            features.append(0.0)
        
        return np.array(features, dtype=np.float32)
    
    async def train_model(
        self,
        camera_id: int,
        days: int = 7,
        contamination: float = 0.05,
        min_samples: int = 100
    ) -> bool:
        """
        Train an Isolation Forest model for a camera.
        
        Args:
            camera_id: Camera to train model for
            days: Number of days of historical data to use
            contamination: Expected proportion of anomalies (0.01-0.1)
            min_samples: Minimum samples required for training
        
        Returns:
            True if training successful
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available for training")
            return False
        
        try:
            # Fetch historical events
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("""
                        SELECT 
                            timestamp,
                            detected_objects,
                            confidence_score,
                            detection_metadata
                        FROM events
                        WHERE camera_id = :camera_id
                            AND timestamp > :cutoff
                        ORDER BY timestamp
                    """),
                    {
                        "camera_id": camera_id,
                        "cutoff": datetime.now() - timedelta(days=days)
                    }
                )
                events = result.fetchall()
            
            if len(events) < min_samples:
                logger.warning(f"Not enough samples for camera {camera_id}: "
                              f"{len(events)} < {min_samples}")
                return False
            
            # Extract features from each event
            feature_vectors = []
            for event in events:
                ts = event.timestamp
                detected = event.detected_objects or {}
                
                # Count classes
                class_counts = {}
                objects = detected.get("objects", detected) if isinstance(detected, dict) else detected
                if isinstance(objects, list):
                    for obj in objects:
                        cls = obj.get("class", obj.get("class_name", "object")).lower()
                        # Map to main categories
                        if cls in ["person", "people"]:
                            cls = "person"
                        elif cls in ["car", "truck", "bus", "motorcycle", "vehicle"]:
                            cls = "vehicle"
                        elif cls in ["dog", "cat", "bird", "animal"]:
                            cls = "animal"
                        else:
                            cls = "object"
                        class_counts[cls] = class_counts.get(cls, 0) + 1
                
                # Extract bbox positions
                positions = []
                if isinstance(objects, list):
                    for obj in objects:
                        bbox = obj.get("bbox", [])
                        if len(bbox) >= 4:
                            center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                            positions.append(center)
                
                features = self._extract_features(
                    hour=ts.hour,
                    day_of_week=ts.weekday(),
                    detection_count=len(objects) if isinstance(objects, list) else 1,
                    class_counts=class_counts,
                    avg_confidence=event.confidence_score or 0.5,
                    bbox_positions=positions
                )
                feature_vectors.append(features)
            
            X = np.array(feature_vectors)
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train Isolation Forest
            model = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
                max_samples='auto',
                n_jobs=-1
            )
            model.fit(X_scaled)
            
            # Store model and scaler
            self.models[camera_id] = model
            self.scalers[camera_id] = scaler
            self.model_metadata[camera_id] = {
                "trained_at": datetime.now().isoformat(),
                "training_days": days,
                "sample_count": len(events),
                "contamination": contamination,
                "feature_count": X.shape[1]
            }
            
            # Save model to disk
            self._save_model(camera_id)
            
            logger.info(f"✅ Trained anomaly detector for camera {camera_id} "
                       f"with {len(events)} samples")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to train anomaly detector for camera {camera_id}: {e}")
            return False
    
    def score(
        self,
        camera_id: int,
        hour: int,
        day_of_week: int,
        detection_count: int,
        class_counts: Dict[str, int],
        avg_confidence: float,
        bbox_positions: List[Tuple[float, float]] = None
    ) -> Tuple[float, bool]:
        """
        Score current state for anomaly.
        
        Returns:
            (anomaly_score, is_anomaly) where:
            - anomaly_score: 0 (normal) to 1 (highly anomalous)
            - is_anomaly: True if classified as anomaly
        """
        if camera_id not in self.models:
            # Try to load model from disk
            if not self._load_model(camera_id):
                return 0.0, False
        
        try:
            model = self.models[camera_id]
            scaler = self.scalers[camera_id]
            
            # Extract and scale features
            features = self._extract_features(
                hour, day_of_week, detection_count,
                class_counts, avg_confidence, bbox_positions
            ).reshape(1, -1)
            
            features_scaled = scaler.transform(features)
            
            # Get anomaly score (-1 = anomaly, 1 = normal)
            raw_score = model.decision_function(features_scaled)[0]
            prediction = model.predict(features_scaled)[0]
            
            # Convert to 0-1 scale (higher = more anomalous)
            # decision_function returns negative for anomalies
            # Normalize using typical range [-0.5, 0.5]
            anomaly_score = max(0, min(1, 0.5 - raw_score))
            
            is_anomaly = prediction == -1
            
            return anomaly_score, is_anomaly
            
        except Exception as e:
            logger.error(f"Anomaly scoring failed: {e}")
            return 0.0, False
    
    def _save_model(self, camera_id: int):
        """Save model and scaler to disk."""
        try:
            model_path = self._models_dir / f"anomaly_camera_{camera_id}.pkl"
            
            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': self.models[camera_id],
                    'scaler': self.scalers[camera_id],
                    'metadata': self.model_metadata[camera_id]
                }, f)
            
            logger.debug(f"Saved anomaly model for camera {camera_id}")
            
        except Exception as e:
            logger.error(f"Failed to save anomaly model: {e}")
    
    def _load_model(self, camera_id: int) -> bool:
        """Load model and scaler from disk."""
        try:
            model_path = self._models_dir / f"anomaly_camera_{camera_id}.pkl"
            
            if not model_path.exists():
                return False
            
            with open(model_path, 'rb') as f:
                data = pickle.load(f)
            
            self.models[camera_id] = data['model']
            self.scalers[camera_id] = data['scaler']
            self.model_metadata[camera_id] = data['metadata']
            
            logger.debug(f"Loaded anomaly model for camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load anomaly model: {e}")
            return False
    
    def get_model_status(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get training status for a camera's model."""
        if camera_id in self.model_metadata:
            return self.model_metadata[camera_id]
        
        # Try to load from disk
        if self._load_model(camera_id):
            return self.model_metadata.get(camera_id)
        
        return None
    
    async def train_all_cameras(
        self,
        days: int = 7,
        min_samples: int = 100
    ) -> Dict[int, bool]:
        """
        Train models for all cameras with sufficient data.
        
        Returns:
            Dict mapping camera_id to success status
        """
        results = {}
        
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("""
                        SELECT DISTINCT camera_id
                        FROM events
                        WHERE timestamp > :cutoff
                        GROUP BY camera_id
                        HAVING COUNT(*) >= :min_samples
                    """),
                    {
                        "cutoff": datetime.now() - timedelta(days=days),
                        "min_samples": min_samples
                    }
                )
                camera_ids = [row.camera_id for row in result.fetchall()]
            
            for camera_id in camera_ids:
                success = await self.train_model(camera_id, days=days, min_samples=min_samples)
                results[camera_id] = success
            
            logger.info(f"Trained anomaly detectors for {sum(results.values())}/{len(results)} cameras")
            
        except Exception as e:
            logger.error(f"Failed to train all cameras: {e}")
        
        return results


# Singleton instance
_anomaly_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get the singleton anomaly detector instance."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector
