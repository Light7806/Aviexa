"""
api/session_store.py
In-memory thread-safe session state manager.
Stores sessions, telemetry, anomalies, and diagnoses.
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import logging

from anomaly.models import TelemetryEvent, AnomalyEvent
from bob.models import BobResponse
from reports import AppliedFixRecord

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """Status of a training session."""
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SessionRecord:
    """Record of a training session."""
    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    script_path: Optional[str] = None
    telemetry_events: List[TelemetryEvent] = field(default_factory=list)
    anomalies: List[AnomalyEvent] = field(default_factory=list)
    diagnoses: List[BobResponse] = field(default_factory=list)
    applied_fixes: List[AppliedFixRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Limits to prevent memory explosion
    max_telemetry: int = 10000
    max_anomalies: int = 1000
    max_diagnoses: int = 100
    max_applied_fixes: int = 500
    
    def append_event(self, event: TelemetryEvent) -> None:
        """Append telemetry event with size limit."""
        self.telemetry_events.append(event)
        if len(self.telemetry_events) > self.max_telemetry:
            # Keep most recent events
            self.telemetry_events = self.telemetry_events[-self.max_telemetry:]
        self.updated_at = datetime.utcnow()
    
    def append_events(self, events: List[TelemetryEvent]) -> None:
        """Append multiple telemetry events."""
        for event in events:
            self.append_event(event)
    
    def append_anomaly(self, anomaly: AnomalyEvent) -> None:
        """Append anomaly with size limit."""
        self.anomalies.append(anomaly)
        if len(self.anomalies) > self.max_anomalies:
            self.anomalies = self.anomalies[-self.max_anomalies:]
        self.updated_at = datetime.utcnow()
    
    def append_diagnosis(self, diagnosis: BobResponse) -> None:
        """Append diagnosis with size limit."""
        self.diagnoses.append(diagnosis)
        if len(self.diagnoses) > self.max_diagnoses:
            self.diagnoses = self.diagnoses[-self.max_diagnoses:]
        self.updated_at = datetime.utcnow()
    
    def append_applied_fix(self, applied_fix: AppliedFixRecord) -> None:
        """Append applied fix with size limit."""
        self.applied_fixes.append(applied_fix)
        if len(self.applied_fixes) > self.max_applied_fixes:
            self.applied_fixes = self.applied_fixes[-self.max_applied_fixes:]
        self.updated_at = datetime.utcnow()


class SessionStore:
    """
    Thread-safe in-memory session store.
    
    Features:
    - Create and manage sessions
    - Store telemetry, anomalies, diagnoses
    - Automatic cleanup of expired sessions
    - Thread-safe operations
    """
    
    def __init__(self, ttl_hours: int = 24):
        """
        Initialize session store.
        
        Args:
            ttl_hours: Time-to-live for sessions in hours
        """
        self._sessions: Dict[str, SessionRecord] = {}
        self._lock = threading.RLock()
        self.ttl = timedelta(hours=ttl_hours)
    
    def create_session(
        self,
        session_id: str,
        script_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionRecord:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            script_path: Path to training script
            metadata: Additional metadata
            
        Returns:
            Created SessionRecord
        """
        with self._lock:
            now = datetime.utcnow()
            session = SessionRecord(
                session_id=session_id,
                status=SessionStatus.CREATED,
                created_at=now,
                updated_at=now,
                script_path=script_path,
                metadata=metadata or {}
            )
            self._sessions[session_id] = session
            logger.info(f"Created session {session_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionRecord or None if not found
        """
        with self._lock:
            return self._sessions.get(session_id)
    
    def list_sessions(self) -> List[SessionRecord]:
        """
        List all sessions.
        
        Returns:
            List of SessionRecord objects
        """
        with self._lock:
            return list(self._sessions.values())
    
    def update_session(self, session_id: str, **fields) -> Optional[SessionRecord]:
        """
        Update session fields.
        
        Args:
            session_id: Session identifier
            **fields: Fields to update
            
        Returns:
            Updated SessionRecord or None if not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            
            for key, value in fields.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            
            session.updated_at = datetime.utcnow()
            return session
    
    def append_event(self, session_id: str, event: TelemetryEvent) -> bool:
        """
        Append telemetry event to session.
        
        Args:
            session_id: Session identifier
            event: Telemetry event
            
        Returns:
            True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.append_event(event)
            return True
    
    def append_events(self, session_id: str, events: List[TelemetryEvent]) -> bool:
        """
        Append multiple telemetry events to session.
        
        Args:
            session_id: Session identifier
            events: List of telemetry events
            
        Returns:
            True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.append_events(events)
            return True
    
    def append_anomaly(self, session_id: str, anomaly: AnomalyEvent) -> bool:
        """
        Append anomaly to session.
        
        Args:
            session_id: Session identifier
            anomaly: Anomaly event
            
        Returns:
            True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.append_anomaly(anomaly)
            return True
    
    def append_diagnosis(self, session_id: str, diagnosis: BobResponse) -> bool:
        """
        Append diagnosis to session.
        
        Args:
            session_id: Session identifier
            diagnosis: Bob diagnosis response
            
        Returns:
            True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.append_diagnosis(diagnosis)
            return True
    
    def append_applied_fix(self, session_id: str, applied_fix: AppliedFixRecord) -> bool:
        """
        Append applied fix to session.
        
        Args:
            session_id: Session identifier
            applied_fix: Applied fix record
            
        Returns:
            True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.append_applied_fix(applied_fix)
            return True
    
    def stop_session(self, session_id: str) -> bool:
        """
        Stop a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False if session not found
        """
        return self.update_session(session_id, status=SessionStatus.STOPPED) is not None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Deleted session {session_id}")
                return True
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            Number of sessions removed
        """
        with self._lock:
            now = datetime.utcnow()
            expired = [
                sid for sid, session in self._sessions.items()
                if now - session.updated_at > self.ttl
            ]
            
            for sid in expired:
                del self._sessions[sid]
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
            
            return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get store statistics.
        
        Returns:
            Dictionary with stats
        """
        with self._lock:
            return {
                "total_sessions": len(self._sessions),
                "sessions_by_status": {
                    status.value: sum(1 for s in self._sessions.values() if s.status == status)
                    for status in SessionStatus
                },
                "ttl_hours": self.ttl.total_seconds() / 3600
            }

# Made with Bob
