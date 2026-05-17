"""
core.hooks package
PyTorch hook managers for forward/backward passes and loss tracking.
"""

from core.hooks.forward_hook import ForwardHookManager, attach_forward_hooks
from core.hooks.backward_hook import BackwardHookManager, attach_backward_hooks
from core.hooks.loss_hook import LossTracker, create_loss_tracker

__all__ = [
    "ForwardHookManager",
    "attach_forward_hooks",
    "BackwardHookManager",
    "attach_backward_hooks",
    "LossTracker",
    "create_loss_tracker",
]

# Made with Bob
