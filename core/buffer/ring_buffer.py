"""
core/buffer/ring_buffer.py
Lock-free circular buffer for telemetry events.
Thread-safe for concurrent writes from training thread and reads from monitoring thread.
"""

import os
import threading
from typing import List, Optional
from collections import deque

from anomaly.models import TelemetryEvent


class RingBuffer:
    """
    Fixed-size circular buffer for telemetry events.
    
    Features:
    - O(1) append operation
    - Thread-safe for concurrent reads/writes
    - Overwrites oldest events when full
    - Tracks dropped event count
    - Returns copies to prevent external mutation
    """
    
    def __init__(self, capacity: Optional[int] = None):
        """
        Initialize ring buffer.
        
        Args:
            capacity: Maximum number of events to store. 
                     Defaults to AVIEXA_BUFFER_SIZE env var or 10000.
        """
        if capacity is None:
            capacity = int(os.getenv("AVIEXA_BUFFER_SIZE", "10000"))
        
        self.capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._dropped_count = 0
        self._total_written = 0
    
    def append(self, event: TelemetryEvent) -> None:
        """
        Append a single event to the buffer.
        
        Args:
            event: TelemetryEvent to store
        """
        with self._lock:
            if len(self._buffer) >= self.capacity:
                self._dropped_count += 1
            self._buffer.append(event)
            self._total_written += 1
    
    def extend(self, events: List[TelemetryEvent]) -> None:
        """
        Append multiple events to the buffer.
        
        Args:
            events: List of TelemetryEvent objects to store
        """
        with self._lock:
            for event in events:
                if len(self._buffer) >= self.capacity:
                    self._dropped_count += 1
                self._buffer.append(event)
                self._total_written += 1
    
    def snapshot(self) -> List[TelemetryEvent]:
        """
        Get a copy of all events currently in the buffer.
        
        Returns:
            List of all events (copy, safe to mutate)
        """
        with self._lock:
            return list(self._buffer)
    
    def latest(self, n: int) -> List[TelemetryEvent]:
        """
        Get the n most recent events.
        
        Args:
            n: Number of recent events to retrieve
            
        Returns:
            List of up to n most recent events (copy)
        """
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)
            # deque is ordered oldest to newest, so slice from end
            return list(self._buffer)[-n:]
    
    def clear(self) -> None:
        """Clear all events from the buffer."""
        with self._lock:
            self._buffer.clear()
    
    def __len__(self) -> int:
        """Return current number of events in buffer."""
        with self._lock:
            return len(self._buffer)
    
    @property
    def dropped_count(self) -> int:
        """Number of events dropped due to buffer overflow."""
        with self._lock:
            return self._dropped_count
    
    @property
    def total_written(self) -> int:
        """Total number of events written to buffer (including dropped)."""
        with self._lock:
            return self._total_written
    
    def stats(self) -> dict:
        """
        Get buffer statistics.
        
        Returns:
            Dictionary with capacity, current size, dropped count, etc.
        """
        with self._lock:
            return {
                "capacity": self.capacity,
                "current_size": len(self._buffer),
                "dropped_count": self._dropped_count,
                "total_written": self._total_written,
                "utilization": len(self._buffer) / self.capacity if self.capacity > 0 else 0.0
            }

# Made with Bob
