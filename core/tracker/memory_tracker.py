"""
core/tracker/memory_tracker.py
Tracks CPU and GPU memory usage during training.
Works gracefully on CPU-only machines.
"""

import torch
import logging
from typing import Optional

from anomaly.models import MemoryEvent
from core.buffer.ring_buffer import RingBuffer

logger = logging.getLogger(__name__)

# Try to import psutil for CPU memory tracking
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False
    logger.info("psutil not available, CPU memory tracking will be limited")


class MemoryTracker:
    """
    Tracks memory usage during training.
    
    Features:
    - Tracks CUDA memory if available
    - Tracks CPU memory if psutil is installed
    - Works on CPU-only machines without errors
    - Provides simple leak detection signals
    """
    
    def __init__(self, buffer: RingBuffer, session_id: str, cuda_device: Optional[int] = None):
        """
        Initialize memory tracker.
        
        Args:
            buffer: RingBuffer to write events to
            session_id: Current session identifier
            cuda_device: CUDA device to track (None = default device)
        """
        self.buffer = buffer
        self.session_id = session_id
        self.current_step = 0
        
        # Determine CUDA availability
        self.cuda_available = torch.cuda.is_available()
        if self.cuda_available:
            if cuda_device is None:
                self.cuda_device = torch.cuda.current_device()
            else:
                self.cuda_device = cuda_device
            logger.info(f"CUDA memory tracking enabled for device {self.cuda_device}")
        else:
            self.cuda_device = None
            logger.info("CUDA not available, GPU memory tracking disabled")
        
        # Track baseline and peak for leak detection
        self._baseline_cuda_mb: Optional[float] = None
        self._peak_cuda_mb: Optional[float] = None
    
    def record_memory(self, step: Optional[int] = None) -> None:
        """
        Record current memory usage.
        
        Args:
            step: Training step (uses current_step if None)
        """
        try:
            if step is None:
                step = self.current_step
            
            # Track CPU memory
            cpu_allocated_mb = None
            cpu_percent = None
            
            if PSUTIL_AVAILABLE and psutil is not None:
                process = psutil.Process()
                memory_info = process.memory_info()
                cpu_allocated_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
                cpu_percent = process.memory_percent()
            
            # Track CUDA memory
            cuda_allocated_mb = None
            cuda_reserved_mb = None
            cuda_max_allocated_mb = None
            
            if self.cuda_available:
                cuda_allocated_mb = torch.cuda.memory_allocated(self.cuda_device) / (1024 * 1024)
                cuda_reserved_mb = torch.cuda.memory_reserved(self.cuda_device) / (1024 * 1024)
                cuda_max_allocated_mb = torch.cuda.max_memory_allocated(self.cuda_device) / (1024 * 1024)
                
                # Update baseline and peak for leak detection
                if self._baseline_cuda_mb is None:
                    self._baseline_cuda_mb = cuda_allocated_mb
                
                if self._peak_cuda_mb is None or cuda_allocated_mb > self._peak_cuda_mb:
                    self._peak_cuda_mb = cuda_allocated_mb
            
            # Create and store event
            event = MemoryEvent(
                session_id=self.session_id,
                step=step,
                cpu_allocated_mb=cpu_allocated_mb,
                cpu_percent=cpu_percent,
                cuda_allocated_mb=cuda_allocated_mb,
                cuda_reserved_mb=cuda_reserved_mb,
                cuda_max_allocated_mb=cuda_max_allocated_mb,
                cuda_device=self.cuda_device
            )
            
            self.buffer.append(event)
            
        except Exception as e:
            # Never crash training due to tracking failure
            logger.warning(f"Memory tracking failed: {e}")
    
    def set_step(self, step: int) -> None:
        """
        Update current step counter.
        
        Args:
            step: Current training step
        """
        self.current_step = step
    
    def reset_peak_memory(self) -> None:
        """Reset CUDA peak memory statistics."""
        if self.cuda_available:
            torch.cuda.reset_peak_memory_stats(self.cuda_device)
            self._peak_cuda_mb = None
    
    def get_memory_stats(self) -> dict:
        """
        Get current memory statistics.
        
        Returns:
            Dictionary with memory stats and leak indicators
        """
        from typing import Any
        stats: dict[str, Any] = {
            "cuda_available": self.cuda_available,
            "psutil_available": PSUTIL_AVAILABLE,
        }
        
        if self.cuda_available:
            current_mb = torch.cuda.memory_allocated(self.cuda_device) / (1024 * 1024)
            stats.update({
                "cuda_device": self.cuda_device,
                "cuda_allocated_mb": current_mb,
                "cuda_reserved_mb": torch.cuda.memory_reserved(self.cuda_device) / (1024 * 1024),
                "cuda_max_allocated_mb": torch.cuda.max_memory_allocated(self.cuda_device) / (1024 * 1024),
                "baseline_cuda_mb": self._baseline_cuda_mb,
                "peak_cuda_mb": self._peak_cuda_mb,
            })
            
            # Simple leak indicator: current usage significantly above baseline
            if self._baseline_cuda_mb is not None and self._baseline_cuda_mb > 0:
                growth_ratio = current_mb / self._baseline_cuda_mb
                stats["memory_growth_ratio"] = growth_ratio
                stats["potential_leak"] = growth_ratio > 2.0  # More than 2x baseline
        
        if PSUTIL_AVAILABLE and psutil is not None:
            process = psutil.Process()
            memory_info = process.memory_info()
            stats.update({
                "cpu_allocated_mb": memory_info.rss / (1024 * 1024),
                "cpu_percent": process.memory_percent(),
            })
        
        return stats


def create_memory_tracker(
    buffer: RingBuffer,
    session_id: str,
    cuda_device: Optional[int] = None
) -> MemoryTracker:
    """
    Convenience function to create a memory tracker.
    
    Args:
        buffer: RingBuffer to write events to
        session_id: Current session identifier
        cuda_device: CUDA device to track (None = default device)
        
    Returns:
        MemoryTracker instance
    """
    return MemoryTracker(buffer, session_id, cuda_device)

# Made with Bob
