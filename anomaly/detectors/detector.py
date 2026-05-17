"""
anomaly/detectors/detector.py
Main anomaly detection orchestrator.
Routes events to specialized detectors and deduplicates anomalies.
"""

from typing import List, Set, Tuple, Optional
import logging

from anomaly.models import TelemetryEvent, AnomalyEvent, EventType, AnomalyType
from core.buffer.ring_buffer import RingBuffer
from anomaly.detectors.gradient_detector import GradientDetector
from anomaly.detectors.loss_detector import LossDetector
from anomaly.detectors.shape_detector import ShapeDetector

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Main anomaly detection orchestrator.
    
    Responsibilities:
    - Route events to specialized detectors
    - Deduplicate repeated anomalies
    - Provide unified API for anomaly detection
    
    Does NOT:
    - Call IBM Bob (that's Layer 3)
    - Store events (that's RingBuffer's job)
    - Make network calls or write files
    """
    
    def __init__(
        self,
        enable_gradient_detection: bool = True,
        enable_loss_detection: bool = True,
        enable_shape_detection: bool = True,
        dedup_window_steps: int = 50
    ):
        """
        Initialize anomaly detector.
        
        Args:
            enable_gradient_detection: Enable gradient anomaly detection
            enable_loss_detection: Enable loss anomaly detection
            enable_shape_detection: Enable shape anomaly detection
            dedup_window_steps: Number of steps to use for deduplication
        """
        self.enable_gradient_detection = enable_gradient_detection
        self.enable_loss_detection = enable_loss_detection
        self.enable_shape_detection = enable_shape_detection
        self.dedup_window_steps = dedup_window_steps
        
        # Initialize specialized detectors
        self.gradient_detector = GradientDetector() if enable_gradient_detection else None
        self.loss_detector = LossDetector() if enable_loss_detection else None
        self.shape_detector = ShapeDetector() if enable_shape_detection else None
        
        # Track recently emitted anomalies for deduplication
        # Key: (anomaly_type, layer_name, step_bucket)
        self._recent_anomalies: Set[Tuple[str, str, int]] = set()
        self._last_cleanup_step = 0
    
    def update(self, event: TelemetryEvent) -> List[AnomalyEvent]:
        """
        Process a single telemetry event and detect anomalies.
        
        Args:
            event: Telemetry event to process
            
        Returns:
            List of detected anomalies (may be empty)
        """
        anomalies = []
        
        try:
            # Route to appropriate detector based on event type
            if event.event_type == EventType.BACKWARD and self.gradient_detector:
                anomalies.extend(self.gradient_detector.update(event))
            
            elif event.event_type == EventType.LOSS and self.loss_detector:
                anomalies.extend(self.loss_detector.update(event))
            
            elif event.event_type == EventType.SHAPE and self.shape_detector:
                anomalies.extend(self.shape_detector.update(event))
            
            # Note: FORWARD and MEMORY events not routed to detectors yet
            # Can be added later for activation statistics or memory leak detection
            
        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}")
        
        # Deduplicate anomalies
        deduplicated = self._deduplicate(anomalies, event.step)
        
        # Cleanup old deduplication entries periodically
        if event.step - self._last_cleanup_step > self.dedup_window_steps:
            self._cleanup_dedup_cache(event.step)
            self._last_cleanup_step = event.step
        
        return deduplicated
    
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
    
    def analyze_buffer(self, buffer: RingBuffer) -> List[AnomalyEvent]:
        """
        Analyze all events in a ring buffer.
        
        Args:
            buffer: RingBuffer containing telemetry events
            
        Returns:
            List of detected anomalies
        """
        events = buffer.snapshot()
        return self.analyze(events)
    
    def _deduplicate(self, anomalies: List[AnomalyEvent], current_step: int) -> List[AnomalyEvent]:
        """
        Deduplicate anomalies to avoid repeated alerts for the same issue.
        
        Args:
            anomalies: List of anomalies to deduplicate
            current_step: Current training step
            
        Returns:
            Deduplicated list of anomalies
        """
        deduplicated = []
        
        for anomaly in anomalies:
            # Create deduplication key
            step_bucket = current_step // self.dedup_window_steps
            layer_name = anomaly.layer_name or "global"
            # Handle both enum and string values
            anomaly_type_str = anomaly.anomaly_type.value if hasattr(anomaly.anomaly_type, 'value') else str(anomaly.anomaly_type)
            key = (anomaly_type_str, layer_name, step_bucket)
            
            # Only emit if not recently seen
            if key not in self._recent_anomalies:
                deduplicated.append(anomaly)
                self._recent_anomalies.add(key)
        
        return deduplicated
    
    def _cleanup_dedup_cache(self, current_step: int) -> None:
        """
        Remove old entries from deduplication cache.
        
        Args:
            current_step: Current training step
        """
        current_bucket = current_step // self.dedup_window_steps
        
        # Remove entries older than 2 windows
        self._recent_anomalies = {
            key for key in self._recent_anomalies
            if key[2] >= current_bucket - 2
        }
    
    def reset(self) -> None:
        """Reset all detectors and internal state."""
        if self.gradient_detector:
            self.gradient_detector.reset()
        
        if self.loss_detector:
            self.loss_detector.reset()
        
        if self.shape_detector:
            self.shape_detector.reset()
        
        self._recent_anomalies.clear()
        self._last_cleanup_step = 0
        
        logger.info("AnomalyDetector reset")
    
    def get_stats(self) -> dict:
        """
        Get detector statistics.
        
        Returns:
            Dictionary with detector stats
        """
        return {
            "gradient_detection_enabled": self.enable_gradient_detection,
            "loss_detection_enabled": self.enable_loss_detection,
            "shape_detection_enabled": self.enable_shape_detection,
            "dedup_cache_size": len(self._recent_anomalies),
            "dedup_window_steps": self.dedup_window_steps,
        }

# Made with Bob
