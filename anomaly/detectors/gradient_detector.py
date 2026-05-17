"""
anomaly/detectors/gradient_detector.py
Detects gradient explosion and vanishing gradient anomalies.
Uses rolling statistics and consecutive event tracking.
"""

import math
from collections import defaultdict, deque
from typing import List, Dict, Optional
import logging

from anomaly.models import TelemetryEvent, BackwardEvent, AnomalyEvent, EventType
from anomaly.detectors.classifier import AnomalyClassifier

logger = logging.getLogger(__name__)


class GradientDetector:
    """
    Detects gradient explosion and vanishing gradient anomalies.
    
    Detection strategies:
    - Gradient explosion: norm exceeds threshold or is NaN/Inf
    - Vanishing gradient: norm consistently near zero for multiple steps
    """
    
    def __init__(
        self,
        explosion_threshold: float = 100.0,
        explosion_sigma: float = 5.0,
        vanishing_threshold: float = 1e-7,
        vanishing_consecutive: int = 5,
        rolling_window: int = 50
    ):
        """
        Initialize gradient detector.
        
        Args:
            explosion_threshold: Absolute threshold for gradient explosion
            explosion_sigma: Number of standard deviations above mean for explosion
            vanishing_threshold: Threshold below which gradients are considered vanishing
            vanishing_consecutive: Number of consecutive low-gradient steps to trigger
            rolling_window: Size of rolling window for statistics
        """
        self.explosion_threshold = explosion_threshold
        self.explosion_sigma = explosion_sigma
        self.vanishing_threshold = vanishing_threshold
        self.vanishing_consecutive = vanishing_consecutive
        self.rolling_window = rolling_window
        
        # Track gradient norms per layer
        self._gradient_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=rolling_window))
        
        # Track consecutive vanishing counts per layer
        self._vanishing_counts: Dict[str, int] = defaultdict(int)
        
        # Track last emitted anomaly step per layer to avoid duplicates
        self._last_explosion_step: Dict[str, int] = {}
        self._last_vanishing_step: Dict[str, int] = {}
    
    def update(self, event: TelemetryEvent) -> List[AnomalyEvent]:
        """
        Process a single telemetry event and detect anomalies.
        
        Args:
            event: Telemetry event to process
            
        Returns:
            List of detected anomalies (may be empty)
        """
        if not isinstance(event, BackwardEvent) and event.event_type != EventType.BACKWARD:
            return []
        
        anomalies = []
        
        # Extract gradient information
        layer_name = event.layer_name or "unknown"
        step = event.step
        
        # Type check and extract BackwardEvent-specific fields
        if isinstance(event, BackwardEvent):
            gradient_norm = event.gradient_norm
            gradient_is_none = event.gradient_is_none
            has_nan = event.has_nan
            has_inf = event.has_inf
        else:
            # Shouldn't happen but handle gracefully
            return []
        
        # Skip if gradient is None (not necessarily an anomaly)
        if gradient_is_none or gradient_norm is None:
            return []
        
        # Check for NaN/Inf (immediate explosion)
        if has_nan or has_inf or math.isnan(gradient_norm) or math.isinf(gradient_norm):
            anomaly = AnomalyClassifier.classify_gradient_explosion(
                session_id=event.session_id,
                step=step,
                layer_name=layer_name,
                gradient_norm=gradient_norm,
                threshold=self.explosion_threshold,
                related_event_ids=[event.event_id]
            )
            anomalies.append(anomaly)
            self._last_explosion_step[layer_name] = step
            return anomalies
        
        # Update gradient history
        self._gradient_history[layer_name].append(gradient_norm)
        
        # Check for gradient explosion
        explosion_anomaly = self._check_explosion(event, layer_name, gradient_norm, step)
        if explosion_anomaly:
            anomalies.append(explosion_anomaly)
        
        # Check for vanishing gradient
        vanishing_anomaly = self._check_vanishing(event, layer_name, gradient_norm, step)
        if vanishing_anomaly:
            anomalies.append(vanishing_anomaly)
        
        return anomalies
    
    def _check_explosion(
        self,
        event: TelemetryEvent,
        layer_name: str,
        gradient_norm: float,
        step: int
    ) -> Optional[AnomalyEvent]:
        """Check for gradient explosion."""
        # Avoid duplicate detections within 10 steps
        if layer_name in self._last_explosion_step:
            if step - self._last_explosion_step[layer_name] < 10:
                return None
        
        history = self._gradient_history[layer_name]
        
        # Need at least 3 samples for meaningful statistics
        if len(history) < 3:
            # But still check absolute threshold
            if gradient_norm > self.explosion_threshold:
                self._last_explosion_step[layer_name] = step
                return AnomalyClassifier.classify_gradient_explosion(
                    session_id=event.session_id,
                    step=step,
                    layer_name=layer_name,
                    gradient_norm=gradient_norm,
                    threshold=self.explosion_threshold,
                    related_event_ids=[event.event_id]
                )
            return None
        
        # Calculate rolling statistics
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance) if variance > 0 else 0.0
        
        # Check absolute threshold
        if gradient_norm > self.explosion_threshold:
            self._last_explosion_step[layer_name] = step
            return AnomalyClassifier.classify_gradient_explosion(
                session_id=event.session_id,
                step=step,
                layer_name=layer_name,
                gradient_norm=gradient_norm,
                threshold=self.explosion_threshold,
                rolling_mean=mean,
                rolling_std=std,
                related_event_ids=[event.event_id]
            )
        
        # Check sigma threshold
        if std > 0 and gradient_norm > mean + self.explosion_sigma * std:
            self._last_explosion_step[layer_name] = step
            return AnomalyClassifier.classify_gradient_explosion(
                session_id=event.session_id,
                step=step,
                layer_name=layer_name,
                gradient_norm=gradient_norm,
                threshold=mean + self.explosion_sigma * std,
                rolling_mean=mean,
                rolling_std=std,
                related_event_ids=[event.event_id]
            )
        
        return None
    
    def _check_vanishing(
        self,
        event: TelemetryEvent,
        layer_name: str,
        gradient_norm: float,
        step: int
    ) -> Optional[AnomalyEvent]:
        """Check for vanishing gradient."""
        # Avoid duplicate detections within 20 steps
        if layer_name in self._last_vanishing_step:
            if step - self._last_vanishing_step[layer_name] < 20:
                return None
        
        # Check if gradient is below vanishing threshold
        if gradient_norm < self.vanishing_threshold:
            self._vanishing_counts[layer_name] += 1
        else:
            # Reset count if gradient recovers
            self._vanishing_counts[layer_name] = 0
            return None
        
        # Trigger anomaly if consecutive count reached
        if self._vanishing_counts[layer_name] >= self.vanishing_consecutive:
            self._last_vanishing_step[layer_name] = step
            # Reset count to avoid repeated triggers
            self._vanishing_counts[layer_name] = 0
            
            return AnomalyClassifier.classify_vanishing_gradient(
                session_id=event.session_id,
                step=step,
                layer_name=layer_name,
                gradient_norm=gradient_norm,
                consecutive_count=self.vanishing_consecutive,
                threshold=self.vanishing_threshold,
                related_event_ids=[event.event_id]
            )
        
        return None
    
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
        """Reset all internal state."""
        self._gradient_history.clear()
        self._vanishing_counts.clear()
        self._last_explosion_step.clear()
        self._last_vanishing_step.clear()
        logger.info("GradientDetector reset")

# Made with Bob
