"""
anomaly/models.py
Shared Pydantic data models for telemetry events and anomalies.
Used by Layer 1 (core instrumentation) and Layer 2 (anomaly detection).
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
import uuid


class EventType(str, Enum):
    """Type of telemetry event captured during training."""
    FORWARD = "forward"
    BACKWARD = "backward"
    LOSS = "loss"
    MEMORY = "memory"
    SHAPE = "shape"
    SESSION = "session"


class AnomalyType(str, Enum):
    """Type of anomaly detected by the anomaly detection layer."""
    GRADIENT_EXPLOSION = "gradient_explosion"
    VANISHING_GRADIENT = "vanishing_gradient"
    LOSS_DIVERGENCE = "loss_divergence"
    LOSS_PLATEAU = "loss_plateau"
    SHAPE_MISMATCH = "shape_mismatch"
    MEMORY_LEAK = "memory_leak"
    UNKNOWN = "unknown"


class TelemetryEvent(BaseModel):
    """Base telemetry event captured by hooks and trackers."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    step: int
    layer_name: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class ForwardEvent(TelemetryEvent):
    """Event captured during forward pass of a module."""
    event_type: EventType = EventType.FORWARD
    input_shape: Optional[tuple] = None
    output_shape: Optional[tuple] = None
    output_mean: Optional[float] = None
    output_std: Optional[float] = None
    output_min: Optional[float] = None
    output_max: Optional[float] = None


class BackwardEvent(TelemetryEvent):
    """Event captured during backward pass (gradient computation)."""
    event_type: EventType = EventType.BACKWARD
    gradient_norm: Optional[float] = None
    gradient_is_none: bool = False
    gradient_max: Optional[float] = None
    gradient_min: Optional[float] = None
    has_nan: bool = False
    has_inf: bool = False


class LossEvent(TelemetryEvent):
    """Event captured when loss is recorded."""
    event_type: EventType = EventType.LOSS
    loss_value: float
    has_nan: bool = False
    has_inf: bool = False


class MemoryEvent(TelemetryEvent):
    """Event captured for memory usage tracking."""
    event_type: EventType = EventType.MEMORY
    cpu_allocated_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    cuda_allocated_mb: Optional[float] = None
    cuda_reserved_mb: Optional[float] = None
    cuda_max_allocated_mb: Optional[float] = None
    cuda_device: Optional[int] = None


class ShapeEvent(TelemetryEvent):
    """Event captured when shape validation occurs."""
    event_type: EventType = EventType.SHAPE
    expected_shape: Optional[tuple] = None
    actual_shape: Optional[tuple] = None
    is_mismatch: bool = False
    mismatch_reason: Optional[str] = None


class AnomalyEvent(BaseModel):
    """
    Classified anomaly event produced by anomaly detectors.
    This is what gets sent to IBM Bob for diagnosis.
    """
    anomaly_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    anomaly_type: AnomalyType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    step: int
    layer_name: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    related_events: list[str] = Field(default_factory=list)  # event_ids
    metrics: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)

# Made with Bob
