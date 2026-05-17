"""
anomaly/detectors/loss_detector.py
Detects loss divergence and loss plateau anomalies.
Uses rolling window statistics and slope analysis.
"""

import math
from collections import deque
from typing import List, Optional
import logging

from anomaly.models import TelemetryEvent, LossEvent, AnomalyEvent, EventType
from anomaly.detectors.classifier import AnomalyClassifier

logger = logging.getLogger(__name__)


class LossDetector:
    """
    Detects loss divergence and loss plateau anomalies.
    
    Detection strategies:
    - Loss divergence: loss increases rapidly or is NaN/Inf
    - Loss plateau: loss remains flat for extended period
    """
    
    def __init__(
        self,
        divergence_slope_threshold: float = 0.1,
        plateau_slope_threshold: float = 1e-4,
        plateau_variance_threshold: float = 1e-6,
        min_plateau_loss: float = 1e-3,
        rolling_window: int = 50,
        min_samples: int = 10
    ):
        """
        Initialize loss detector.
        
        Args:
            divergence_slope_threshold: Positive slope threshold for divergence
            plateau_slope_threshold: Near-zero slope threshold for plateau
            plateau_variance_threshold: Low variance threshold for plateau
            min_plateau_loss: Minimum loss value to consider for plateau (avoid detecting at zero)
            rolling_window: Size of rolling window for statistics
            min_samples: Minimum samples needed before detecting
        """
        self.divergence_slope_threshold = divergence_slope_threshold
        self.plateau_slope_threshold = plateau_slope_threshold
        self.plateau_variance_threshold = plateau_variance_threshold
        self.min_plateau_loss = min_plateau_loss
        self.rolling_window = rolling_window
        self.min_samples = min_samples
        
        # Track loss history
        self._loss_history: deque = deque(maxlen=rolling_window)
        self._step_history: deque = deque(maxlen=rolling_window)
        
        # Track last emitted anomaly step to avoid duplicates
        self._last_divergence_step: Optional[int] = None
        self._last_plateau_step: Optional[int] = None
    
    def update(self, event: TelemetryEvent) -> List[AnomalyEvent]:
        """
        Process a single telemetry event and detect anomalies.
        
        Args:
            event: Telemetry event to process
            
        Returns:
            List of detected anomalies (may be empty)
        """
        if not isinstance(event, LossEvent) and event.event_type != EventType.LOSS:
            return []
        
        anomalies = []
        
        # Type check and extract LossEvent-specific fields
        if isinstance(event, LossEvent):
            loss_value = event.loss_value
            has_nan = event.has_nan
            has_inf = event.has_inf
        else:
            return []
        
        step = event.step
        
        # Check for NaN/Inf (immediate divergence)
        if has_nan or has_inf or math.isnan(loss_value) or math.isinf(loss_value):
            anomaly = AnomalyClassifier.classify_loss_divergence(
                session_id=event.session_id,
                step=step,
                current_loss=loss_value,
                slope=float('inf'),
                window_size=1,
                threshold=self.divergence_slope_threshold,
                related_event_ids=[event.event_id]
            )
            anomalies.append(anomaly)
            self._last_divergence_step = step
            return anomalies
        
        # Update loss history
        self._loss_history.append(loss_value)
        self._step_history.append(step)
        
        # Need minimum samples for meaningful analysis
        if len(self._loss_history) < self.min_samples:
            return []
        
        # Calculate slope
        slope = self._calculate_slope()
        
        # Check for loss divergence
        divergence_anomaly = self._check_divergence(event, loss_value, slope, step)
        if divergence_anomaly:
            anomalies.append(divergence_anomaly)
        
        # Check for loss plateau (only if not diverging)
        if not divergence_anomaly:
            plateau_anomaly = self._check_plateau(event, loss_value, slope, step)
            if plateau_anomaly:
                anomalies.append(plateau_anomaly)
        
        return anomalies
    
    def _calculate_slope(self) -> float:
        """Calculate slope of loss over recent history using linear regression."""
        if len(self._loss_history) < 2:
            return 0.0
        
        n = len(self._loss_history)
        losses = list(self._loss_history)
        steps = list(self._step_history)
        
        # Simple linear regression: slope = cov(x,y) / var(x)
        mean_step = sum(steps) / n
        mean_loss = sum(losses) / n
        
        numerator = sum((steps[i] - mean_step) * (losses[i] - mean_loss) for i in range(n))
        denominator = sum((steps[i] - mean_step) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope
    
    def _calculate_variance(self) -> float:
        """Calculate variance of recent losses."""
        if len(self._loss_history) < 2:
            return 0.0
        
        losses = list(self._loss_history)
        mean = sum(losses) / len(losses)
        variance = sum((x - mean) ** 2 for x in losses) / len(losses)
        return variance
    
    def _check_divergence(
        self,
        event: TelemetryEvent,
        loss_value: float,
        slope: float,
        step: int
    ) -> Optional[AnomalyEvent]:
        """Check for loss divergence."""
        # Avoid duplicate detections within 20 steps
        if self._last_divergence_step is not None:
            if step - self._last_divergence_step < 20:
                return None
        
        # Check if slope exceeds threshold (loss increasing)
        if slope > self.divergence_slope_threshold:
            self._last_divergence_step = step
            return AnomalyClassifier.classify_loss_divergence(
                session_id=event.session_id,
                step=step,
                current_loss=loss_value,
                slope=slope,
                window_size=len(self._loss_history),
                threshold=self.divergence_slope_threshold,
                related_event_ids=[event.event_id]
            )
        
        return None
    
    def _check_plateau(
        self,
        event: TelemetryEvent,
        loss_value: float,
        slope: float,
        step: int
    ) -> Optional[AnomalyEvent]:
        """Check for loss plateau."""
        # Avoid duplicate detections within 50 steps
        if self._last_plateau_step is not None:
            if step - self._last_plateau_step < 50:
                return None
        
        # Need enough samples for plateau detection
        if len(self._loss_history) < self.rolling_window // 2:
            return None
        
        # Don't detect plateau if loss is already very small
        if loss_value < self.min_plateau_loss:
            return None
        
        # Calculate variance
        variance = self._calculate_variance()
        
        # Check if slope is near zero and variance is low
        if abs(slope) < self.plateau_slope_threshold and variance < self.plateau_variance_threshold:
            self._last_plateau_step = step
            return AnomalyClassifier.classify_loss_plateau(
                session_id=event.session_id,
                step=step,
                current_loss=loss_value,
                slope=slope,
                variance=variance,
                window_size=len(self._loss_history),
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
        self._loss_history.clear()
        self._step_history.clear()
        self._last_divergence_step = None
        self._last_plateau_step = None
        logger.info("LossDetector reset")

# Made with Bob
