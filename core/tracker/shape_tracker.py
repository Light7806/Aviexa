"""
core/tracker/shape_tracker.py
Validates tensor shape consistency across training steps.
Detects unexpected shape changes that may indicate bugs.
"""

import torch
import logging
from typing import Dict, Tuple, Optional

from anomaly.models import ShapeEvent
from core.buffer.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class ShapeTracker:
    """
    Tracks and validates tensor shapes across training steps.
    
    Features:
    - Records expected shapes on first pass
    - Validates subsequent passes against expected shapes
    - Allows dynamic batch dimension (dim 0)
    - Detects rank changes and feature dimension mismatches
    """
    
    def __init__(self, buffer: RingBuffer, session_id: str, allow_dynamic_batch: bool = True):
        """
        Initialize shape tracker.
        
        Args:
            buffer: RingBuffer to write events to
            session_id: Current session identifier
            allow_dynamic_batch: If True, ignore batch dimension (dim 0) in comparisons
        """
        self.buffer = buffer
        self.session_id = session_id
        self.allow_dynamic_batch = allow_dynamic_batch
        self.current_step = 0
        
        # Store expected shapes: {layer_name: expected_shape}
        self._expected_shapes: Dict[str, Tuple] = {}
        self._initialized = False
    
    def register_shape(self, layer_name: str, shape: Tuple[int, ...]) -> None:
        """
        Register expected shape for a layer.
        
        Args:
            layer_name: Name of the layer/tensor
            shape: Expected shape tuple
        """
        if layer_name not in self._expected_shapes:
            self._expected_shapes[layer_name] = shape
            logger.debug(f"Registered shape for {layer_name}: {shape}")
    
    def validate_shape(self, layer_name: str, actual_shape: Tuple[int, ...]) -> bool:
        """
        Validate a tensor shape against expected shape.
        
        Args:
            layer_name: Name of the layer/tensor
            actual_shape: Actual shape to validate
            
        Returns:
            True if shape is valid, False if mismatch detected
        """
        try:
            # If no expected shape, register this one
            if layer_name not in self._expected_shapes:
                self.register_shape(layer_name, actual_shape)
                return True
            
            expected_shape = self._expected_shapes[layer_name]
            
            # Check rank (number of dimensions)
            if len(actual_shape) != len(expected_shape):
                self._record_mismatch(
                    layer_name,
                    expected_shape,
                    actual_shape,
                    f"Rank mismatch: expected {len(expected_shape)} dims, got {len(actual_shape)} dims"
                )
                return False
            
            # Compare dimensions
            for i, (expected_dim, actual_dim) in enumerate(zip(expected_shape, actual_shape)):
                # Skip batch dimension if allowed
                if i == 0 and self.allow_dynamic_batch:
                    continue
                
                if expected_dim != actual_dim:
                    self._record_mismatch(
                        layer_name,
                        expected_shape,
                        actual_shape,
                        f"Dimension {i} mismatch: expected {expected_dim}, got {actual_dim}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Shape validation failed for {layer_name}: {e}")
            return True  # Don't report errors as mismatches
    
    def _record_mismatch(
        self,
        layer_name: str,
        expected_shape: Tuple,
        actual_shape: Tuple,
        reason: str
    ) -> None:
        """
        Record a shape mismatch event.
        
        Args:
            layer_name: Name of the layer/tensor
            expected_shape: Expected shape
            actual_shape: Actual shape
            reason: Description of the mismatch
        """
        event = ShapeEvent(
            session_id=self.session_id,
            step=self.current_step,
            layer_name=layer_name,
            expected_shape=expected_shape,
            actual_shape=actual_shape,
            is_mismatch=True,
            mismatch_reason=reason
        )
        
        self.buffer.append(event)
        logger.warning(f"Shape mismatch in {layer_name}: {reason}")
    
    def set_step(self, step: int) -> None:
        """
        Update current step counter.
        
        Args:
            step: Current training step
        """
        self.current_step = step
    
    def reset(self) -> None:
        """Clear all registered shapes."""
        self._expected_shapes.clear()
        self._initialized = False
        logger.info("Shape tracker reset")
    
    def get_expected_shapes(self) -> Dict[str, Tuple]:
        """
        Get all registered expected shapes.
        
        Returns:
            Dictionary mapping layer names to expected shapes
        """
        return self._expected_shapes.copy()


def create_shape_tracker(
    buffer: RingBuffer,
    session_id: str,
    allow_dynamic_batch: bool = True
) -> ShapeTracker:
    """
    Convenience function to create a shape tracker.
    
    Args:
        buffer: RingBuffer to write events to
        session_id: Current session identifier
        allow_dynamic_batch: If True, ignore batch dimension in comparisons
        
    Returns:
        ShapeTracker instance
    """
    return ShapeTracker(buffer, session_id, allow_dynamic_batch)

# Made with Bob
