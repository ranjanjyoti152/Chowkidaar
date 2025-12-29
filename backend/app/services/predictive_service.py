"""
Chowkidaar NVR - Predictive Incident Service
Predict potential incidents BEFORE they happen using pattern analysis.
"""
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np
from loguru import logger
from collections import defaultdict

from app.core.database import AsyncSessionLocal
from sqlalchemy import select, text


@dataclass
class RiskAssessment:
    """Risk assessment result from predictive analysis."""
    risk_score: float  # 0-100
    risk_level: str  # low, medium, high, critical
    contributing_factors: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    analysis_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 2),
            "risk_level": self.risk_level,
            "contributing_factors": self.contributing_factors,
            "recommended_actions": self.recommended_actions,
            "confidence": round(self.confidence, 3),
            "analysis_time": self.analysis_time.isoformat()
        }


@dataclass
class LoiteringEvent:
    """Detected loitering behavior."""
    camera_id: int
    track_id: int
    duration_seconds: float
    last_position: Tuple[float, float]
    first_seen: datetime
    risk_score: float


class PredictiveIncidentService:
    """
    Predictive incident detection using multi-signal analysis.
    
    Prediction Signals:
    
    1. BEHAVIORAL PATTERNS
       - Loitering detection (person in area > threshold time)
       - Unusual path patterns (erratic movement)
       - Object interactions (person approaching vehicle repeatedly)
       
    2. TEMPORAL ANOMALIES
       - Activity at unusual hours (learn normal patterns)
       - Sudden spike in detections
       - Missing expected activity (guard not doing rounds)
       
    3. SPATIAL ANOMALIES  
       - Objects in unusual locations
       - Crowd formation detection
       - Perimeter breach patterns
       
    4. SEQUENCE PATTERNS
       - Pre-incident signatures (e.g., person + vehicle + looking around)
       - Historical pattern matching
    """
    
    # Risk thresholds
    RISK_LEVELS = {
        (0, 25): "low",
        (25, 50): "medium",
        (50, 75): "high",
        (75, 100): "critical"
    }
    
    # Loitering thresholds by location type
    LOITERING_THRESHOLDS = {
        "entrance": 60,      # 1 minute at entrance is concerning
        "parking": 180,      # 3 minutes in parking lot
        "perimeter": 45,     # 45 seconds at perimeter
        "default": 120       # 2 minutes default
    }
    
    # High-risk detection patterns
    PRE_INCIDENT_PATTERNS = {
        "burglary_risk": {
            "pattern": ["person", "vehicle", "person"],
            "behaviors": ["loitering", "looking_around", "approaching_entrance"],
            "time_window": 300,  # 5 minutes
            "risk_boost": 40
        },
        "theft_risk": {
            "pattern": ["person", "backpack", "person"],
            "behaviors": ["approaching_item", "picking_up", "leaving_quickly"],
            "time_window": 180,
            "risk_boost": 35
        },
        "violence_risk": {
            "pattern": ["person", "person", "crowd"],
            "behaviors": ["confrontation", "gathering", "running"],
            "time_window": 120,
            "risk_boost": 50
        }
    }
    
    def __init__(self):
        # Track objects across frames per camera
        self._track_history: Dict[int, Dict[int, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        # Camera baseline patterns
        self._camera_baselines: Dict[int, Dict[str, Any]] = {}
        # Last analysis time per camera
        self._last_analysis: Dict[int, datetime] = {}
    
    async def analyze_risk(
        self, 
        camera_id: int,
        current_detections: List[dict],
        frame_embedding: Optional[np.ndarray] = None,
        location_type: str = "default"
    ) -> RiskAssessment:
        """
        Real-time risk assessment combining all signals.
        
        Args:
            camera_id: Camera ID
            current_detections: List of current frame detections
            frame_embedding: Optional CLIP embedding of current frame
            location_type: Type of location for threshold adjustment
        
        Returns:
            RiskAssessment with risk score, level, and recommendations
        """
        risk_score = 0.0
        factors = []
        recommendations = []
        confidence_scores = []
        
        current_time = datetime.now()
        hour = current_time.hour
        
        # 1. TEMPORAL ANALYSIS - Time-based risk
        temporal_risk, temporal_factor = self._analyze_temporal_risk(hour, current_detections)
        if temporal_risk > 0:
            risk_score += temporal_risk
            factors.append(temporal_factor)
            confidence_scores.append(0.8)
        
        # 2. BEHAVIORAL ANALYSIS - Loitering, patterns
        behavioral_risk, behavioral_factors = await self._analyze_behavioral_risk(
            camera_id, current_detections, location_type
        )
        if behavioral_risk > 0:
            risk_score += behavioral_risk
            factors.extend(behavioral_factors)
            confidence_scores.append(0.7)
        
        # 3. DETECTION COMPOSITION - What's in the frame
        composition_risk, composition_factors = self._analyze_detection_composition(
            current_detections, hour
        )
        if composition_risk > 0:
            risk_score += composition_risk
            factors.extend(composition_factors)
            confidence_scores.append(0.85)
        
        # 4. SEQUENCE PATTERN MATCHING
        sequence_risk, sequence_factor = await self._analyze_sequence_patterns(
            camera_id, current_detections
        )
        if sequence_risk > 0:
            risk_score += sequence_risk
            if sequence_factor:
                factors.append(sequence_factor)
            confidence_scores.append(0.6)
        
        # 5. ANOMALY DETECTION - Compare to baseline
        if camera_id in self._camera_baselines:
            anomaly_risk, anomaly_factor = await self._detect_anomalies(
                camera_id, current_detections
            )
            if anomaly_risk > 0:
                risk_score += anomaly_risk
                if anomaly_factor:
                    factors.append(anomaly_factor)
                confidence_scores.append(0.65)
        
        # Cap risk score at 100
        risk_score = min(100.0, risk_score)
        
        # Determine risk level
        risk_level = "low"
        for (low, high), level in self.RISK_LEVELS.items():
            if low <= risk_score < high:
                risk_level = level
                break
        if risk_score >= 75:
            risk_level = "critical"
        
        # Generate recommendations based on risk level
        recommendations = self._generate_recommendations(risk_level, factors)
        
        # Calculate overall confidence
        confidence = np.mean(confidence_scores) if confidence_scores else 0.5
        
        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            contributing_factors=factors,
            recommended_actions=recommendations,
            confidence=confidence,
            analysis_time=current_time
        )
    
    def _analyze_temporal_risk(
        self, 
        hour: int, 
        detections: List[dict]
    ) -> Tuple[float, str]:
        """Analyze risk based on time of day."""
        risk = 0.0
        factor = ""
        
        # Late night activity with people is concerning
        if (hour >= 23 or hour < 5):
            has_person = any(d.get("class_name", "").lower() == "person" for d in detections)
            if has_person:
                risk = 20.0
                factor = f"Person detected during high-risk hours ({hour}:00)"
        
        # Early morning (5-6 AM) slightly elevated
        elif 5 <= hour < 6:
            has_person = any(d.get("class_name", "").lower() == "person" for d in detections)
            if has_person:
                risk = 10.0
                factor = "Person detected during early morning hours"
        
        return risk, factor
    
    async def _analyze_behavioral_risk(
        self,
        camera_id: int,
        detections: List[dict],
        location_type: str
    ) -> Tuple[float, List[str]]:
        """Analyze behavioral patterns like loitering."""
        risk = 0.0
        factors = []
        
        # Update track history
        for detection in detections:
            track_id = detection.get("track_id")
            if track_id is not None:
                self._track_history[camera_id][track_id].append({
                    "timestamp": datetime.now(),
                    "bbox": detection.get("bbox", []),
                    "class": detection.get("class_name", ""),
                    "confidence": detection.get("confidence", 0)
                })
                
                # Keep only last 5 minutes of history
                cutoff = datetime.now() - timedelta(minutes=5)
                self._track_history[camera_id][track_id] = [
                    h for h in self._track_history[camera_id][track_id]
                    if h["timestamp"] > cutoff
                ]
        
        # Check for loitering
        threshold = self.LOITERING_THRESHOLDS.get(location_type, 
                                                   self.LOITERING_THRESHOLDS["default"])
        
        for track_id, history in self._track_history[camera_id].items():
            if len(history) >= 2:
                duration = (history[-1]["timestamp"] - history[0]["timestamp"]).total_seconds()
                
                # Check if it's a person loitering
                if history[-1]["class"].lower() == "person" and duration > threshold:
                    loitering_risk = min(30.0, (duration / threshold) * 15)
                    risk += loitering_risk
                    factors.append(
                        f"Loitering detected: Person present for {duration:.0f}s "
                        f"(threshold: {threshold}s)"
                    )
        
        return risk, factors
    
    def _analyze_detection_composition(
        self,
        detections: List[dict],
        hour: int
    ) -> Tuple[float, List[str]]:
        """Analyze what objects are detected together."""
        risk = 0.0
        factors = []
        
        classes = [d.get("class_name", "").lower() for d in detections]
        
        # High-risk objects
        high_risk_objects = {"knife", "gun", "weapon", "fire", "smoke"}
        found_high_risk = set(classes) & high_risk_objects
        if found_high_risk:
            risk += 40.0
            factors.append(f"High-risk objects detected: {', '.join(found_high_risk)}")
        
        # Multiple unknown people at night
        person_count = sum(1 for c in classes if c == "person")
        if person_count >= 3 and (hour >= 22 or hour < 6):
            risk += 20.0
            factors.append(f"Multiple people ({person_count}) detected at night")
        
        # Person + vehicle at night (potential theft/break-in)
        has_person = "person" in classes
        has_vehicle = any(v in classes for v in ["car", "truck", "motorcycle"])
        if has_person and has_vehicle and (hour >= 23 or hour < 5):
            risk += 15.0
            factors.append("Person with vehicle detected during late night hours")
        
        return risk, factors
    
    async def _analyze_sequence_patterns(
        self,
        camera_id: int,
        detections: List[dict]
    ) -> Tuple[float, Optional[str]]:
        """Check for known pre-incident sequence patterns."""
        # Get recent detection history from database
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("""
                        SELECT event_type, detected_objects, timestamp
                        FROM events
                        WHERE camera_id = :camera_id
                            AND timestamp > :cutoff
                        ORDER BY timestamp DESC
                        LIMIT 20
                    """),
                    {
                        "camera_id": camera_id,
                        "cutoff": datetime.now() - timedelta(minutes=10)
                    }
                )
                recent_events = result.fetchall()
                
                if len(recent_events) >= 3:
                    # Check for escalating severity
                    severities = [e.event_type for e in recent_events]
                    if "suspicious" in severities or "intrusion" in severities:
                        return 25.0, "Escalating suspicious activity pattern detected"
                
        except Exception as e:
            logger.debug(f"Sequence analysis error: {e}")
        
        return 0.0, None
    
    async def _detect_anomalies(
        self,
        camera_id: int,
        detections: List[dict]
    ) -> Tuple[float, Optional[str]]:
        """Detect statistical anomalies from baseline."""
        baseline = self._camera_baselines.get(camera_id, {})
        
        if not baseline:
            return 0.0, None
        
        risk = 0.0
        
        # Check detection count anomaly
        current_count = len(detections)
        avg_count = baseline.get("avg_detection_count", 0)
        std_count = baseline.get("std_detection_count", 1)
        
        if avg_count > 0 and std_count > 0:
            z_score = (current_count - avg_count) / std_count
            if z_score > 2.0:  # More than 2 std deviations
                risk = min(20.0, z_score * 5)
                return risk, f"Unusual number of detections: {current_count} (normal: {avg_count:.1f})"
        
        return 0.0, None
    
    def _generate_recommendations(
        self,
        risk_level: str,
        factors: List[str]
    ) -> List[str]:
        """Generate actionable recommendations based on risk."""
        recommendations = []
        
        if risk_level == "low":
            recommendations.append("Continue normal monitoring")
        
        elif risk_level == "medium":
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Review recent footage for context")
        
        elif risk_level == "high":
            recommendations.append("Immediate operator attention required")
            recommendations.append("Consider alerting security personnel")
            recommendations.append("Enable continuous recording")
        
        elif risk_level == "critical":
            recommendations.append("URGENT: Immediate response required")
            recommendations.append("Alert all security personnel")
            recommendations.append("Contact emergency services if applicable")
            recommendations.append("Preserve all footage for evidence")
        
        return recommendations
    
    async def learn_baseline(
        self,
        camera_id: int,
        hours: int = 168  # 1 week default
    ) -> Dict[str, Any]:
        """
        Learn normal activity patterns for a camera over time window.
        Should be run periodically (e.g., weekly) to establish baseline.
        """
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("""
                        SELECT 
                            EXTRACT(HOUR FROM timestamp) as hour,
                            COUNT(*) as event_count,
                            AVG(confidence_score) as avg_confidence
                        FROM events
                        WHERE camera_id = :camera_id
                            AND timestamp > :cutoff
                        GROUP BY EXTRACT(HOUR FROM timestamp)
                        ORDER BY hour
                    """),
                    {
                        "camera_id": camera_id,
                        "cutoff": datetime.now() - timedelta(hours=hours)
                    }
                )
                hourly_stats = result.fetchall()
                
                if hourly_stats:
                    counts = [row.event_count for row in hourly_stats]
                    
                    self._camera_baselines[camera_id] = {
                        "avg_detection_count": np.mean(counts),
                        "std_detection_count": np.std(counts),
                        "hourly_distribution": {
                            int(row.hour): row.event_count for row in hourly_stats
                        },
                        "learned_at": datetime.now().isoformat(),
                        "sample_hours": hours
                    }
                    
                    logger.info(f"Learned baseline for camera {camera_id}: "
                               f"avg={np.mean(counts):.1f}, std={np.std(counts):.1f}")
                    
                    return self._camera_baselines[camera_id]
                
        except Exception as e:
            logger.error(f"Failed to learn baseline: {e}")
        
        return {}
    
    async def detect_loitering(
        self,
        camera_id: int,
        threshold_seconds: float = 60
    ) -> List[LoiteringEvent]:
        """
        Detect all currently loitering objects.
        
        Returns:
            List of LoiteringEvent objects for each loitering detection
        """
        loitering_events = []
        
        for track_id, history in self._track_history[camera_id].items():
            if len(history) >= 2:
                duration = (history[-1]["timestamp"] - history[0]["timestamp"]).total_seconds()
                
                if duration > threshold_seconds and history[-1]["class"].lower() == "person":
                    bbox = history[-1].get("bbox", [0, 0, 0, 0])
                    center = (
                        (bbox[0] + bbox[2]) / 2 if len(bbox) >= 4 else 0,
                        (bbox[1] + bbox[3]) / 2 if len(bbox) >= 4 else 0
                    )
                    
                    loitering_events.append(LoiteringEvent(
                        camera_id=camera_id,
                        track_id=track_id,
                        duration_seconds=duration,
                        last_position=center,
                        first_seen=history[0]["timestamp"],
                        risk_score=min(100, (duration / threshold_seconds) * 50)
                    ))
        
        return loitering_events
    
    def cleanup_old_tracks(self, max_age_minutes: int = 10):
        """Clean up old track history to prevent memory bloat."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        
        for camera_id in list(self._track_history.keys()):
            for track_id in list(self._track_history[camera_id].keys()):
                self._track_history[camera_id][track_id] = [
                    h for h in self._track_history[camera_id][track_id]
                    if h["timestamp"] > cutoff
                ]
                
                # Remove empty tracks
                if not self._track_history[camera_id][track_id]:
                    del self._track_history[camera_id][track_id]


# Singleton instance
_predictive_service: Optional[PredictiveIncidentService] = None


def get_predictive_service() -> PredictiveIncidentService:
    """Get the singleton predictive incident service instance."""
    global _predictive_service
    if _predictive_service is None:
        _predictive_service = PredictiveIncidentService()
    return _predictive_service
