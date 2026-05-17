"""
anomaly/detectors/classifier.py
Centralized anomaly classification and AnomalyEvent construction.
Converts detector signals into structured AnomalyEvent objects.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from anomaly.models import AnomalyEvent, AnomalyType, TelemetryEvent


class AnomalyClassifier:
    """
    Centralized classifier for converting detector signals to AnomalyEvent objects.
    
    Responsibilities:
    - Build AnomalyEvent objects consistently
    - Normalize confidence scores to [0.0, 1.0]
    - Generate clear descriptions
    - Attach related event IDs and metrics
    """
    
    @staticmethod
    def classify_gradient_explosion(
        session_id: str,
        step: int,
        layer_name: str,
        gradient_norm: float,
        threshold: float,
        rolling_mean: Optional[float] = None,
        rolling_std: Optional[float] = None,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create gradient explosion anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            layer_name: Layer/parameter name
            gradient_norm: Current gradient norm
            threshold: Threshold that was exceeded
            rolling_mean: Rolling mean of gradient norms
            rolling_std: Rolling std of gradient norms
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for gradient explosion
        """
        # Calculate confidence based on how far above threshold
        if rolling_mean is not None and rolling_std is not None and rolling_std > 0:
            sigma_distance = (gradient_norm - rolling_mean) / rolling_std
            confidence = min(0.95, 0.5 + (sigma_distance / 20.0))
        else:
            confidence = 0.8 if gradient_norm > threshold * 2 else 0.6
        
        confidence = max(0.0, min(1.0, confidence))
        
        description = f"Gradient explosion detected in {layer_name}: norm={gradient_norm:.4f} exceeds threshold={threshold:.4f}"
        if rolling_mean is not None:
            description += f" (mean={rolling_mean:.4f})"
        
        metrics = {
            "gradient_norm": gradient_norm,
            "threshold": threshold,
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
            step=step,
            layer_name=layer_name,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )
    
    @staticmethod
    def classify_vanishing_gradient(
        session_id: str,
        step: int,
        layer_name: str,
        gradient_norm: float,
        consecutive_count: int,
        threshold: float,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create vanishing gradient anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            layer_name: Layer/parameter name
            gradient_norm: Current gradient norm
            consecutive_count: Number of consecutive low-gradient events
            threshold: Threshold below which gradients are considered vanishing
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for vanishing gradient
        """
        # Confidence increases with consecutive count
        confidence = min(0.95, 0.5 + (consecutive_count / 20.0))
        confidence = max(0.0, min(1.0, confidence))
        
        description = f"Vanishing gradient detected in {layer_name}: norm={gradient_norm:.2e} below threshold={threshold:.2e} for {consecutive_count} consecutive steps"
        
        metrics = {
            "gradient_norm": gradient_norm,
            "threshold": threshold,
            "consecutive_count": consecutive_count,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.VANISHING_GRADIENT,
            step=step,
            layer_name=layer_name,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )
    
    @staticmethod
    def classify_loss_divergence(
        session_id: str,
        step: int,
        current_loss: float,
        slope: float,
        window_size: int,
        threshold: float,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create loss divergence anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            current_loss: Current loss value
            slope: Slope of recent loss trend
            window_size: Size of rolling window used
            threshold: Slope threshold that was exceeded
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for loss divergence
        """
        # Confidence based on slope magnitude
        confidence = min(0.95, 0.6 + abs(slope) / (threshold * 10))
        confidence = max(0.0, min(1.0, confidence))
        
        description = f"Loss divergence detected: loss={current_loss:.4f}, slope={slope:.4f} over {window_size} steps exceeds threshold={threshold:.4f}"
        
        metrics = {
            "current_loss": current_loss,
            "slope": slope,
            "window_size": window_size,
            "threshold": threshold,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.LOSS_DIVERGENCE,
            step=step,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )
    
    @staticmethod
    def classify_loss_plateau(
        session_id: str,
        step: int,
        current_loss: float,
        slope: float,
        variance: float,
        window_size: int,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create loss plateau anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            current_loss: Current loss value
            slope: Slope of recent loss trend (near zero)
            variance: Variance of recent losses
            window_size: Size of rolling window used
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for loss plateau
        """
        # Confidence based on how flat the loss is
        confidence = 0.7 if variance < 1e-6 else 0.6
        confidence = max(0.0, min(1.0, confidence))
        
        description = f"Loss plateau detected: loss={current_loss:.4f} has been flat (slope={slope:.2e}, variance={variance:.2e}) over {window_size} steps"
        
        metrics = {
            "current_loss": current_loss,
            "slope": slope,
            "variance": variance,
            "window_size": window_size,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.LOSS_PLATEAU,
            step=step,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )
    
    @staticmethod
    def classify_shape_mismatch(
        session_id: str,
        step: int,
        layer_name: str,
        expected_shape: tuple,
        actual_shape: tuple,
        mismatch_reason: str,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create shape mismatch anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            layer_name: Layer/tensor name
            expected_shape: Expected tensor shape
            actual_shape: Actual tensor shape
            mismatch_reason: Description of the mismatch
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for shape mismatch
        """
        # Shape mismatches are usually definitive
        confidence = 0.95
        
        description = f"Shape mismatch in {layer_name}: expected {expected_shape}, got {actual_shape}. {mismatch_reason}"
        
        metrics = {
            "expected_shape": expected_shape,
            "actual_shape": actual_shape,
            "mismatch_reason": mismatch_reason,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.SHAPE_MISMATCH,
            step=step,
            layer_name=layer_name,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )
    
    @staticmethod
    def classify_memory_leak(
        session_id: str,
        step: int,
        current_mb: float,
        baseline_mb: float,
        growth_ratio: float,
        related_event_ids: Optional[List[str]] = None
    ) -> AnomalyEvent:
        """
        Create memory leak anomaly event.
        
        Args:
            session_id: Session identifier
            step: Training step
            current_mb: Current memory usage in MB
            baseline_mb: Baseline memory usage in MB
            growth_ratio: Ratio of current to baseline
            related_event_ids: Related telemetry event IDs
            
        Returns:
            AnomalyEvent for memory leak
        """
        # Confidence based on growth ratio
        confidence = min(0.9, 0.5 + (growth_ratio - 2.0) / 10.0)
        confidence = max(0.0, min(1.0, confidence))
        
        description = f"Potential memory leak: memory usage {current_mb:.1f}MB is {growth_ratio:.2f}x baseline {baseline_mb:.1f}MB"
        
        metrics = {
            "current_mb": current_mb,
            "baseline_mb": baseline_mb,
            "growth_ratio": growth_ratio,
        }
        
        return AnomalyEvent(
            session_id=session_id,
            anomaly_type=AnomalyType.MEMORY_LEAK,
            step=step,
            confidence=confidence,
            description=description,
            related_events=related_event_ids or [],
            metrics=metrics
        )

# Made with Bob
