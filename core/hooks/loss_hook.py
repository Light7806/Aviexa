"""
core/hooks/loss_hook.py
Loss tracking for training loops.
Provides a simple interface to record loss values without fragile monkey-patching.
"""

import torch
import logging
import math
from typing import Optional

from anomaly.models import LossEvent
from core.buffer.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class LossTracker:
    """
    Tracks loss values during training.
    
    Usage:
        tracker = LossTracker(buffer, session_id)
        
        # In training loop:
        loss = criterion(output, target)
        tracker.record_loss(loss, step=current_step)
        loss.backward()
    """
    
    def __init__(self, buffer: RingBuffer, session_id: str):
        """
        Initialize loss tracker.
        
        Args:
            buffer: RingBuffer to write events to
            session_id: Current session identifier
        """
        self.buffer = buffer
        self.session_id = session_id
        self.current_step = 0
    
    def record_loss(self, loss: torch.Tensor, step: Optional[int] = None) -> None:
        """
        Record a loss value.
        
        Args:
            loss: Loss tensor (typically scalar)
            step: Training step (uses current_step if None)
        """
        try:
            if step is None:
                step = self.current_step
            
            # Extract scalar value
            if isinstance(loss, torch.Tensor):
                loss_value = float(loss.detach().cpu().item())
            else:
                loss_value = float(loss)
            
            # Check for NaN/Inf
            has_nan = math.isnan(loss_value)
            has_inf = math.isinf(loss_value)
            
            # Create and store event
            event = LossEvent(
                session_id=self.session_id,
                step=step,
                loss_value=loss_value,
                has_nan=has_nan,
                has_inf=has_inf
            )
            
            self.buffer.append(event)
            
        except Exception as e:
            # Never crash training due to tracking failure
            logger.warning(f"Loss tracking failed: {e}")
    
    def set_step(self, step: int) -> None:
        """
        Update current step counter.
        
        Args:
            step: Current training step
        """
        self.current_step = step


def create_loss_tracker(buffer: RingBuffer, session_id: str) -> LossTracker:
    """
    Convenience function to create a loss tracker.
    
    Args:
        buffer: RingBuffer to write events to
        session_id: Current session identifier
        
    Returns:
        LossTracker instance
    """
    return LossTracker(buffer, session_id)

# Made with Bob
