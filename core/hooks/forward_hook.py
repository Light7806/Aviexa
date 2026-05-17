"""
core/hooks/forward_hook.py
Forward pass hook registration for PyTorch modules.
Captures activation statistics without blocking training.
"""

import torch
import torch.nn as nn
from typing import Optional, List, Callable
import logging

from anomaly.models import ForwardEvent
from core.buffer.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)


class ForwardHookManager:
    """
    Manages forward hooks for PyTorch modules.
    Captures output shape and statistics during forward pass.
    """
    
    def __init__(self, buffer: RingBuffer, session_id: str):
        """
        Initialize forward hook manager.
        
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
        Register forward hooks on all leaf modules in the model.
        
        Args:
            model: PyTorch model to instrument
        """
        # Build module name mapping
        for name, module in model.named_modules():
            self._module_names[id(module)] = name or "root"
        
        # Register hooks on leaf modules only
        for name, module in model.named_modules():
            # Skip container modules (Sequential, ModuleList, etc.)
            if len(list(module.children())) == 0:
                handle = module.register_forward_hook(self._create_hook(name or "root"))
                self._hook_handles.append(handle)
        
        logger.info(f"Registered {len(self._hook_handles)} forward hooks")
    
    def _create_hook(self, layer_name: str) -> Callable:
        """
        Create a forward hook function for a specific layer.
        
        Args:
            layer_name: Name of the layer/module
            
        Returns:
            Hook function compatible with register_forward_hook
        """
        def hook(module: nn.Module, input: tuple, output: torch.Tensor):
            try:
                # Extract shape information
                input_shape = None
                output_shape = None
                
                if isinstance(input, tuple) and len(input) > 0:
                    if hasattr(input[0], 'shape'):
                        input_shape = tuple(input[0].shape)
                
                if hasattr(output, 'shape'):
                    output_shape = tuple(output.shape)
                
                # Extract statistics from output tensor
                output_mean = None
                output_std = None
                output_min = None
                output_max = None
                
                if isinstance(output, torch.Tensor) and output.numel() > 0:
                    # Detach and move to CPU for statistics (avoid graph retention)
                    with torch.no_grad():
                        output_detached = output.detach()
                        if output_detached.dtype in [torch.float32, torch.float64, torch.float16]:
                            output_mean = float(output_detached.mean())
                            # std() requires at least 2 elements (Bessel correction);
                            # single-element tensors produce a UserWarning — skip instead.
                            output_std = float(output_detached.std()) if output_detached.numel() > 1 else None
                            output_min = float(output_detached.min())
                            output_max = float(output_detached.max())
                
                # Create and store event
                event = ForwardEvent(
                    session_id=self.session_id,
                    step=self.current_step,
                    layer_name=layer_name,
                    input_shape=input_shape,
                    output_shape=output_shape,
                    output_mean=output_mean,
                    output_std=output_std,
                    output_min=output_min,
                    output_max=output_max
                )
                
                self.buffer.append(event)
                
            except Exception as e:
                # Never crash training due to hook failure
                logger.warning(f"Forward hook failed for {layer_name}: {e}")
        
        return hook
    
    def set_step(self, step: int) -> None:
        """
        Update current step counter.
        
        Args:
            step: Current training step
        """
        self.current_step = step
    
    def remove_hooks(self) -> None:
        """Remove all registered forward hooks."""
        for handle in self._hook_handles:
            handle.remove()
        self._hook_handles.clear()
        logger.info("Removed all forward hooks")
    
    def __del__(self):
        """Cleanup hooks on deletion."""
        self.remove_hooks()


def attach_forward_hooks(model: nn.Module, buffer: RingBuffer, session_id: str) -> ForwardHookManager:
    """
    Convenience function to attach forward hooks to a model.
    
    Args:
        model: PyTorch model to instrument
        buffer: RingBuffer to write events to
        session_id: Current session identifier
        
    Returns:
        ForwardHookManager instance for managing hooks
    """
    manager = ForwardHookManager(buffer, session_id)
    manager.register_hooks(model)
    return manager

# Made with Bob
