"""
core/hooks/backward_hook.py
Backward pass hook registration for PyTorch modules.
Captures gradient statistics without blocking training.
"""

import torch
import torch.nn as nn
from typing import List, Callable, Optional
import logging
import math

from anomaly.models import BackwardEvent
from core.buffer.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class BackwardHookManager:
    """
    Manages backward hooks for PyTorch modules.
    Captures gradient norms and statistics during backward pass.
    """
    
    def __init__(self, buffer: RingBuffer, session_id: str):
        """
        Initialize backward hook manager.
        
        Args:
            buffer: RingBuffer to write events to
            session_id: Current session identifier
        """
        self.buffer = buffer
        self.session_id = session_id
        self.current_step = 0
        self._hook_handles: List[torch.utils.hooks.RemovableHandle] = []
        self._module_names: dict = {}
    
    def register_hooks(self, model: nn.Module) -> None:
        """
        Register backward hooks on all parameters with gradients.
        
        Args:
            model: PyTorch model to instrument
        """
        # Build module name mapping
        for name, module in model.named_modules():
            self._module_names[id(module)] = name or "root"
        
        # Register hooks on parameters that require gradients
        for name, param in model.named_parameters():
            if param.requires_grad:
                handle = param.register_hook(self._create_hook(name))
                self._hook_handles.append(handle)
        
        logger.info(f"Registered {len(self._hook_handles)} backward hooks")
    
    def _create_hook(self, param_name: str) -> Callable:
        """
        Create a backward hook function for a specific parameter.
        
        Args:
            param_name: Name of the parameter
            
        Returns:
            Hook function compatible with register_hook
        """
        def hook(grad: Optional[torch.Tensor]):
            try:
                # Check if gradient is None
                if grad is None:
                    event = BackwardEvent(
                        session_id=self.session_id,
                        step=self.current_step,
                        layer_name=param_name,
                        gradient_is_none=True
                    )
                    self.buffer.append(event)
                    return
                
                # Detach gradient to avoid retaining computation graph
                with torch.no_grad():
                    grad_detached = grad.detach()
                    
                    # Calculate gradient norm
                    gradient_norm = None
                    if grad_detached.numel() > 0:
                        gradient_norm = float(grad_detached.norm(2))
                    
                    # Calculate min/max
                    gradient_max = None
                    gradient_min = None
                    if grad_detached.numel() > 0:
                        gradient_max = float(grad_detached.max())
                        gradient_min = float(grad_detached.min())
                    
                    # Check for NaN/Inf
                    has_nan = bool(torch.isnan(grad_detached).any())
                    has_inf = bool(torch.isinf(grad_detached).any())
                    
                    # Create and store event
                    event = BackwardEvent(
                        session_id=self.session_id,
                        step=self.current_step,
                        layer_name=param_name,
                        gradient_norm=gradient_norm,
                        gradient_is_none=False,
                        gradient_max=gradient_max,
                        gradient_min=gradient_min,
                        has_nan=has_nan,
                        has_inf=has_inf
                    )
                    
                    self.buffer.append(event)
                
            except Exception as e:
                # Never crash training due to hook failure
                logger.warning(f"Backward hook failed for {param_name}: {e}")
            
            # Return None to not modify the gradient
            return None
        
        return hook
    
    def set_step(self, step: int) -> None:
        """
        Update current step counter.
        
        Args:
            step: Current training step
        """
        self.current_step = step
    
    def remove_hooks(self) -> None:
        """Remove all registered backward hooks."""
        for handle in self._hook_handles:
            handle.remove()
        self._hook_handles.clear()
        logger.info("Removed all backward hooks")
    
    def __del__(self):
        """Cleanup hooks on deletion."""
        self.remove_hooks()


def attach_backward_hooks(model: nn.Module, buffer: RingBuffer, session_id: str) -> BackwardHookManager:
    """
    Convenience function to attach backward hooks to a model.
    
    Args:
        model: PyTorch model to instrument
        buffer: RingBuffer to write events to
        session_id: Current session identifier
        
    Returns:
        BackwardHookManager instance for managing hooks
    """
    manager = BackwardHookManager(buffer, session_id)
    manager.register_hooks(model)
    return manager

# Made with Bob
