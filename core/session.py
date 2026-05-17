"""
core/session.py
Main orchestrator for Aviexa instrumentation.
Coordinates hooks, buffer, and trackers for a training session.
"""

import uuid
import logging
from typing import Optional, List
import torch
import torch.nn as nn

from anomaly.models import TelemetryEvent
from core.buffer.ring_buffer import RingBuffer
from core.hooks.forward_hook import ForwardHookManager
from core.hooks.backward_hook import BackwardHookManager
from core.hooks.loss_hook import LossTracker
from core.tracker.shape_tracker import ShapeTracker
from core.tracker.memory_tracker import MemoryTracker

logger = logging.getLogger(__name__)


class AviexaSession:
    """
    Main session orchestrator for Aviexa instrumentation.
    
    Responsibilities:
    - Create and manage session lifecycle
    - Own RingBuffer for telemetry events
    - Register/unregister hooks on model
    - Track training steps
    - Provide API for recording loss and memory
    - Provide access to collected events
    
    Usage:
        session = AviexaSession()
        session.start(model=model, optimizer=optimizer)
        
        for step, batch in enumerate(loader):
            session.increment_step()
            loss = train_step(...)
            session.record_loss(loss)
            session.record_memory()
        
        session.stop()
        events = session.latest_events(100)
    """
    
    def __init__(self, buffer_capacity: Optional[int] = None):
        """
        Initialize Aviexa session.
        
        Args:
            buffer_capacity: Size of ring buffer (None = use env default)
        """
        self.session_id = str(uuid.uuid4())
        self.buffer = RingBuffer(capacity=buffer_capacity)
        self.current_step = 0
        self._is_active = False
        
        # Hook and tracker managers (initialized on start)
        self._forward_hook_manager: Optional[ForwardHookManager] = None
        self._backward_hook_manager: Optional[BackwardHookManager] = None
        self._loss_tracker: Optional[LossTracker] = None
        self._shape_tracker: Optional[ShapeTracker] = None
        self._memory_tracker: Optional[MemoryTracker] = None
        
        logger.info(f"Created Aviexa session {self.session_id}")
    
    def start(
        self,
        model: Optional[nn.Module] = None,
        optimizer: Optional[torch.optim.Optimizer] = None,
        enable_forward_hooks: bool = True,
        enable_backward_hooks: bool = True,
        enable_shape_tracking: bool = True,
        enable_memory_tracking: bool = True
    ) -> None:
        """
        Start instrumentation session.
        
        Args:
            model: PyTorch model to instrument (optional)
            optimizer: PyTorch optimizer (optional, for future use)
            enable_forward_hooks: Enable forward pass hooks
            enable_backward_hooks: Enable backward pass hooks
            enable_shape_tracking: Enable shape validation
            enable_memory_tracking: Enable memory tracking
        """
        if self._is_active:
            logger.warning("Session already active, stopping previous session")
            self.stop()
        
        logger.info(f"Starting Aviexa session {self.session_id}")
        
        # Initialize trackers
        self._loss_tracker = LossTracker(self.buffer, self.session_id)
        
        if enable_shape_tracking:
            self._shape_tracker = ShapeTracker(self.buffer, self.session_id)
        
        if enable_memory_tracking:
            self._memory_tracker = MemoryTracker(self.buffer, self.session_id)
        
        # Register hooks if model provided
        if model is not None:
            if enable_forward_hooks:
                self._forward_hook_manager = ForwardHookManager(self.buffer, self.session_id)
                self._forward_hook_manager.register_hooks(model)
            
            if enable_backward_hooks:
                self._backward_hook_manager = BackwardHookManager(self.buffer, self.session_id)
                self._backward_hook_manager.register_hooks(model)
        
        self._is_active = True
        logger.info("Aviexa session started successfully")
    
    def stop(self) -> None:
        """Stop instrumentation and clean up all hooks."""
        if not self._is_active:
            logger.warning("Session not active, nothing to stop")
            return
        
        logger.info(f"Stopping Aviexa session {self.session_id}")
        
        # Remove all hooks
        if self._forward_hook_manager is not None:
            self._forward_hook_manager.remove_hooks()
            self._forward_hook_manager = None
        
        if self._backward_hook_manager is not None:
            self._backward_hook_manager.remove_hooks()
            self._backward_hook_manager = None
        
        self._is_active = False
        logger.info("Aviexa session stopped")
    
    def increment_step(self) -> None:
        """Increment the current training step counter."""
        self.current_step += 1
        
        # Update step in all managers
        if self._forward_hook_manager is not None:
            self._forward_hook_manager.set_step(self.current_step)
        
        if self._backward_hook_manager is not None:
            self._backward_hook_manager.set_step(self.current_step)
        
        if self._loss_tracker is not None:
            self._loss_tracker.set_step(self.current_step)
        
        if self._shape_tracker is not None:
            self._shape_tracker.set_step(self.current_step)
        
        if self._memory_tracker is not None:
            self._memory_tracker.set_step(self.current_step)
    
    def record_loss(self, loss: torch.Tensor, step: Optional[int] = None) -> None:
        """
        Record a loss value.
        
        Args:
            loss: Loss tensor
            step: Training step (uses current_step if None)
        """
        if self._loss_tracker is None:
            logger.warning("Loss tracker not initialized, call start() first")
            return
        
        self._loss_tracker.record_loss(loss, step)
    
    def record_memory(self, step: Optional[int] = None) -> None:
        """
        Record current memory usage.
        
        Args:
            step: Training step (uses current_step if None)
        """
        if self._memory_tracker is None:
            logger.debug("Memory tracker not initialized")
            return
        
        self._memory_tracker.record_memory(step)
    
    def validate_shape(self, layer_name: str, shape: tuple) -> bool:
        """
        Validate a tensor shape.
        
        Args:
            layer_name: Name of the layer/tensor
            shape: Shape to validate
            
        Returns:
            True if valid, False if mismatch detected
        """
        if self._shape_tracker is None:
            return True
        
        return self._shape_tracker.validate_shape(layer_name, shape)
    
    def get_events(self) -> List[TelemetryEvent]:
        """
        Get all events in the buffer.
        
        Returns:
            List of all telemetry events
        """
        return self.buffer.snapshot()
    
    def latest_events(self, n: int) -> List[TelemetryEvent]:
        """
        Get the n most recent events.
        
        Args:
            n: Number of recent events to retrieve
            
        Returns:
            List of up to n most recent events
        """
        return self.buffer.latest(n)
    
    def clear(self) -> None:
        """Clear all events from the buffer."""
        self.buffer.clear()
    
    def get_stats(self) -> dict:
        """
        Get session statistics.
        
        Returns:
            Dictionary with session stats
        """
        stats = {
            "session_id": self.session_id,
            "is_active": self._is_active,
            "current_step": self.current_step,
            "buffer_stats": self.buffer.stats(),
        }
        
        if self._memory_tracker is not None:
            stats["memory_stats"] = self._memory_tracker.get_memory_stats()
        
        if self._shape_tracker is not None:
            stats["registered_shapes"] = len(self._shape_tracker.get_expected_shapes())
        
        return stats
    
    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self._is_active
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        if self._is_active:
            self.stop()
        return False
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._is_active:
            self.stop()

# Made with Bob
