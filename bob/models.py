"""
bob/models.py
Pydantic data models for IBM Bob integration.
Defines structures for prompts, responses, hypotheses, and code fixes.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class RiskLevel(str, Enum):
    """Risk level for code fixes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DiagnosticStatus(str, Enum):
    """Status of diagnostic report."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceSnippet(BaseModel):
    """Source code snippet with context."""
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    reason: Optional[str] = None


class Hypothesis(BaseModel):
    """Diagnostic hypothesis from Bob."""
    title: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)


class CodeFix(BaseModel):
    """Code fix suggestion from Bob."""
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    original_code: Optional[str] = None
    replacement_code: str
    explanation: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_review: bool = True


class BobPrompt(BaseModel):
    """Prompt sent to IBM Bob."""
    prompt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_id: str
    session_id: str
    anomaly_type: str
    prompt_version: str = "1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    system_message: str
    user_message: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BobResponse(BaseModel):
    """Response from IBM Bob."""
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_id: str
    session_id: str
    summary: str
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    fixes: List[CodeFix] = Field(default_factory=list)
    raw_response: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DiagnosticReport(BaseModel):
    """Complete diagnostic report for an anomaly."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    anomaly_id: str
    anomaly_type: str
    bob_response: BobResponse
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    status: DiagnosticStatus = DiagnosticStatus.COMPLETED

# Made with Bob
