"""
reports/__init__.py
Models and utilities for Aviexa PDF report generation.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class AppliedFixRecord(BaseModel):
    """
    Record of a code fix that was applied during a session.
    
    Tracks when and how fixes suggested by Bob were applied to the codebase.
    """
    fix_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    anomaly_id: Optional[str] = None
    diagnosis_id: Optional[str] = None
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    original_code: Optional[str] = None
    replacement_code: str
    explanation: str
    risk_level: str = "medium"  # low, medium, high
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "applied"  # applied, reverted, failed
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


__all__ = [
    'AppliedFixRecord',
]

# Made with Bob
