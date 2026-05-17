"""
anomaly/detectors/shape_detector.py
Detects shape mismatch anomalies from ShapeEvent telemetry.
Simple converter from ShapeEvent to AnomalyEvent.
"""

from typing import List
import logging

from anomaly.models import TelemetryEvent, ShapeEvent, AnomalyEvent, EventType
from anomaly.detectors.classifier import AnomalyClassifier

logger = logging.getLogger(__name__)


class ShapeDetector:
    """
    Detects shape mismatch anomalies.
    
    Simply converts ShapeEvent with is_mismatch=True into AnomalyEvent.
    Shape mismatches are typically definitive and don't require statistical analysis.
    """
    
    def __init__(self):
        """Initialize shape detector."""
        pass
    
    def update(self, event: TelemetryEvent) -> List[AnomalyEvent]:
        """
        Process a single telemetry event and detect anomalies.
        
        Args:
            event: Telemetry event to process
            
        Returns:
            List of detected anomalies (may be empty)
        """
        if not isinstance(event, ShapeEvent) and event.event_type != EventType.SHAPE:
            return []
        
        # Type check and extract ShapeEvent-specific fields
        if not isinstance(event, ShapeEvent):
            return []
        
        # Only emit anomaly if this is actually a mismatch
        if not event.is_mismatch:
            return []
        
        # Extract shape information
        layer_name = event.layer_name or "unknown"
        expected_shape = event.expected_shape or ()
        actual_shape = event.actual_shape or ()
        mismatch_reason = event.mismatch_reason or "Shape mismatch detected"
        
        # Create anomaly event
        anomaly = AnomalyClassifier.classify_shape_mismatch(
            session_id=event.session_id,
            step=event.step,
            layer_name=layer_name,
            expected_shape=expected_shape,
            actual_shape=actual_shape,
            mismatch_reason=mismatch_reason,
            related_event_ids=[event.event_id]
        )
        
        return [anomaly]
    
    def analyze(self, events: List[TelemetryEvent]) -> List[AnomalyEvent]:
        """
        Analyze a batch of events.
        
        Args:
            events: List of telemetry events
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        for event in events:
            anomalies.extend(self.update(event))
        return anomalies
    
    def reset(self) -> None:
        """Reset all internal state (no state to reset for shape detector)."""
        logger.info("ShapeDetector reset")

# Made with Bob
