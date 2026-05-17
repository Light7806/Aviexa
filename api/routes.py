"""
api/routes.py
FastAPI routes for Aviexa API.
Exposes session management, telemetry ingestion, and diagnosis endpoints.
"""

import uuid
import re
import subprocess
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import logging

from anomaly.models import TelemetryEvent, AnomalyEvent, BackwardEvent, LossEvent, ForwardEvent, MemoryEvent, ShapeEvent
from anomaly.detectors import AnomalyDetector
from bob import BobClient
from api.session_store import SessionStore, SessionStatus
from reports import AppliedFixRecord
from reports.pdf_generator import AviexaPDFReportGenerator

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Global instances (initialized by app)
session_store: Optional[SessionStore] = None
anomaly_detector: Optional[AnomalyDetector] = None
bob_client: Optional[BobClient] = None
REPO_ROOT = Path(__file__).resolve().parent.parent


def init_dependencies(store: SessionStore, detector: AnomalyDetector, client: BobClient):
    """Initialize route dependencies."""
    global session_store, anomaly_detector, bob_client
    session_store = store
    anomaly_detector = detector
    bob_client = client


def _resolve_project_path(path_value: Optional[str], default_relative: str = "demo/external_project") -> Path:
    """Resolve UI paths relative to the repo, not the server launch directory."""
    raw = (path_value or default_relative).strip() or default_relative
    candidate = Path(raw).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [REPO_ROOT / candidate, Path.cwd() / candidate]

    for path in candidates:
        resolved = path.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved

    fallback = (REPO_ROOT / default_relative).resolve()
    if fallback.exists() and fallback.is_dir():
        return fallback

    raise HTTPException(status_code=404, detail=f"Project folder not found: {raw}")


# Request/Response Models
class StartSessionRequest(BaseModel):
    """Request to start a new session."""
    script_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StartSessionResponse(BaseModel):
    """Response from starting a session."""
    session_id: str
    status: str
    created_at: str


class SessionResponse(BaseModel):
    """Session information response."""
    session_id: str
    status: str
    created_at: str
    updated_at: str
    script_path: Optional[str]
    telemetry_count: int
    anomaly_count: int
    diagnosis_count: int
    metadata: Dict[str, Any]


class TelemetryResponse(BaseModel):
    """Response from telemetry ingestion."""
    received: int
    anomalies_detected: int
    diagnoses_generated: int
    new_anomalies: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    bob_mock: bool


def _demo_gradient_explosion(session_id: str) -> List[Dict[str, Any]]:
    events = []
    for step, gnorm in enumerate([1.1, 1.3, 250.0, 1.2, 1.0], start=1):
        events.append({
            "session_id": session_id,
            "event_type": "backward",
            "step": step,
            "layer_name": "fc2.weight",
            "gradient_norm": gnorm,
            "gradient_is_none": False,
            "has_nan": False,
            "has_inf": False,
        })
    for step in range(1, 8):
        events.append({
            "session_id": session_id,
            "event_type": "loss",
            "step": step,
            "loss_value": 2.4 - step * 0.05,
        })
    return events


def _demo_shape_mismatch(session_id: str) -> List[Dict[str, Any]]:
    events = []
    for step in range(1, 4):
        events.append({
            "session_id": session_id,
            "event_type": "backward",
            "step": step,
            "layer_name": "backbone.weight",
            "gradient_norm": 0.8 + step * 0.05,
            "gradient_is_none": False,
            "has_nan": False,
            "has_inf": False,
        })
        events.append({
            "session_id": session_id,
            "event_type": "loss",
            "step": step,
            "loss_value": 2.5 - step * 0.1,
        })
    events.append({
        "session_id": session_id,
        "event_type": "shape",
        "step": 4,
        "layer_name": "fc",
        "is_mismatch": True,
        "expected_shape": [16, 256],
        "actual_shape": [16, 128],
        "mismatch_reason": "Linear layer expects input dim 256 but backbone outputs 128",
    })
    return events


def _parse_event(event_data: Dict[str, Any]):
    event_type = event_data.get("event_type")
    if event_type == "backward":
        return BackwardEvent(**event_data)
    if event_type == "loss":
        return LossEvent(**event_data)
    if event_type == "forward":
        return ForwardEvent(**event_data)
    if event_type == "memory":
        return MemoryEvent(**event_data)
    if event_type == "shape":
        return ShapeEvent(**event_data)
    return TelemetryEvent(**event_data)


def _static_project_inspection(project_path: Path) -> Dict[str, Any]:
    exclude_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "aviexa-reports"}
    py_files = [
        p for p in project_path.rglob("*.py")
        if not any(part in exclude_dirs for part in p.parts)
    ]
    findings = []
    inventory = {"training_files": [], "model_files": [], "optimizer_files": [], "loss_files": []}
    rules = [
        ("high-learning-rate", "high", re.compile(r"lr\s*=\s*(?:1\.0|[2-9](?:\.0)?|[1-9]\d+(?:\.\d+)?)"), "Very high learning rate can cause loss divergence or gradient explosion.", "Reduce the learning rate or add a scheduler."),
        ("backward-without-gradient-clipping", "medium", re.compile(r"\.backward\s*\("), "Backward pass found without visible gradient clipping.", "Add clip_grad_norm_ before optimizer.step()."),
        ("reshape-shape-mismatch-risk", "medium", re.compile(r"\.view\s*\(|\.reshape\s*\(|flatten\s*\("), "Manual reshape/flatten can cause tensor shape mismatch bugs.", "Assert tensor shapes and verify Linear dimensions."),
    ]
    for path in py_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(project_path))
        low = text.lower()
        if "backward(" in low or "optimizer.step" in low or "train" in path.name.lower():
            inventory["training_files"].append(rel)
        if "nn.module" in low or "def forward" in low:
            inventory["model_files"].append(rel)
        if "optim." in text or "torch.optim" in text:
            inventory["optimizer_files"].append(rel)
        if "loss" in low or "criterion" in low:
            inventory["loss_files"].append(rel)
        has_clip = "clip_grad_norm" in text or "clip_grad_value" in text
        for rule_id, severity, pattern, message, fix in rules:
            if rule_id == "backward-without-gradient-clipping" and has_clip:
                continue
            match = pattern.search(text)
            if match:
                findings.append({
                    "id": rule_id,
                    "severity": severity,
                    "file": rel,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "message": message,
                    "fix": fix,
                })
    return {
        "project": str(project_path),
        "python_files": len(py_files),
        "inventory": inventory,
        "findings": findings,
        "generated_at": datetime.utcnow().isoformat(),
    }


# Routes

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        service="aviexa",
        version="1.0.0",
        bob_mock=bob_client.use_mock if bob_client else True
    )


@router.post("/demo/run/{scenario}")
async def run_demo_scenario(scenario: str):
    """Run a polished in-browser demo scenario for the Aviexa app."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Services not initialized")

    if scenario == "gradient-explosion":
        title = "Gradient explosion"
        telemetry_builder = _demo_gradient_explosion
        fix_payload = {
            "file_path": "train.py",
            "start_line": 45,
            "end_line": 47,
            "original_code": "loss.backward()\noptimizer.step()",
            "replacement_code": "loss.backward()\ntorch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)\noptimizer.step()",
            "explanation": "Add gradient clipping to prevent exploding gradients.",
            "risk_level": "low",
            "status": "suggested",
        }
    elif scenario == "shape-mismatch":
        title = "Shape mismatch"
        telemetry_builder = _demo_shape_mismatch
        fix_payload = {
            "file_path": "model.py",
            "start_line": 12,
            "end_line": 12,
            "original_code": "self.fc1 = nn.Linear(256, 64)",
            "replacement_code": "self.fc1 = nn.Linear(128, 64)",
            "explanation": "Match the Linear layer input dimension to the backbone output.",
            "risk_level": "low",
            "status": "suggested",
        }
    else:
        raise HTTPException(status_code=404, detail="Unknown demo scenario")

    session_id = str(uuid.uuid4())
    session = session_store.create_session(
        session_id=session_id,
        script_path=f"demo/{scenario}.py",
        metadata={"demo": True, "title": title, "surface": "web-app"},
    )
    session_store.update_session(session_id, status=SessionStatus.RUNNING)

    raw_events = telemetry_builder(session_id)
    parsed_events = []
    for raw_event in raw_events:
        try:
            parsed_events.append(_parse_event(raw_event))
        except Exception as e:
            logger.warning("Failed to parse demo event: %s", e)

    session_store.append_events(session_id, parsed_events)

    # Demo routes must be deterministic across repeated clicks. Use a fresh
    # detector so rolling thresholds from a previous session cannot leak in.
    local_detector = AnomalyDetector()
    new_anomalies = []
    for event in parsed_events:
        for anomaly in local_detector.update(event):
            if getattr(anomaly, "session_id", None) != session_id:
                anomaly = anomaly.model_copy(update={"session_id": session_id})
            session_store.append_anomaly(session_id, anomaly)
            new_anomalies.append(anomaly)

    # Use the rich local Bob-compatible fallback for instant web demos. The
    # CLI path can still exercise Bob Shell; the browser app must stay snappy.
    from bob import BobClient
    demo_bob = BobClient(use_mock=True)
    diagnoses = []
    for anomaly in new_anomalies:
        diagnosis = demo_bob.diagnose_anomaly(anomaly, parsed_events)
        session_store.append_diagnosis(session_id, diagnosis)
        diagnoses.append(diagnosis)

    applied_fix = AppliedFixRecord(session_id=session_id, **fix_payload)
    session_store.append_applied_fix(session_id, applied_fix)

    return {
        "scenario": scenario,
        "session_id": session_id,
        "telemetry_count": len(parsed_events),
        "anomalies": [a.model_dump() for a in new_anomalies],
        "diagnoses": [d.model_dump() for d in diagnoses],
        "applied_fixes": [applied_fix.model_dump()],
        "report_url": f"/session/{session_id}/report",
    }


@router.get("/demo/inspect")
async def inspect_demo_project():
    """Inspect the bundled external ML project used in the web demo."""
    project_path = REPO_ROOT / "demo" / "external_project"
    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Demo project not found")
    return _static_project_inspection(project_path.resolve())


@router.get("/inspect")
async def inspect_project(path: Optional[str] = Query(None, description="Project folder to inspect")):
    """Inspect any local ML project folder available on this machine."""
    project_path = _resolve_project_path(path, ".")
    return _static_project_inspection(project_path)


@router.post("/session/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest):
    """Start a new training session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session_id = str(uuid.uuid4())
    session = session_store.create_session(
        session_id=session_id,
        script_path=request.script_path,
        metadata=request.metadata
    )
    
    # Update status to running
    session_store.update_session(session_id, status=SessionStatus.RUNNING)
    
    return StartSessionResponse(
        session_id=session.session_id,
        status=session.status.value,
        created_at=session.created_at.isoformat()
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session information."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=session.session_id,
        status=session.status.value,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        script_path=session.script_path,
        telemetry_count=len(session.telemetry_events),
        anomaly_count=len(session.anomalies),
        diagnosis_count=len(session.diagnoses),
        metadata=session.metadata
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all sessions."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    sessions = session_store.list_sessions()
    return [
        SessionResponse(
            session_id=s.session_id,
            status=s.status.value,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            script_path=s.script_path,
            telemetry_count=len(s.telemetry_events),
            anomaly_count=len(s.anomalies),
            diagnosis_count=len(s.diagnoses),
            metadata=s.metadata
        )
        for s in sessions
    ]


@router.post("/session/{session_id}/telemetry", response_model=TelemetryResponse)
async def ingest_telemetry(session_id: str, events: Union[Dict[str, Any], List[Dict[str, Any]]]):
    """Ingest telemetry events and run anomaly detection."""
    if not session_store or not anomaly_detector or not bob_client:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Normalize to list
    if isinstance(events, dict):
        events = [events]
    
    # Parse events
    parsed_events = []
    for event_data in events:
        try:
            # Determine event type and parse
            event_type = event_data.get('event_type')
            if event_type == 'backward':
                event = BackwardEvent(**event_data)
            elif event_type == 'loss':
                event = LossEvent(**event_data)
            elif event_type == 'forward':
                event = ForwardEvent(**event_data)
            elif event_type == 'memory':
                event = MemoryEvent(**event_data)
            elif event_type == 'shape':
                event = ShapeEvent(**event_data)
            else:
                # Generic telemetry event
                event = TelemetryEvent(**event_data)
            parsed_events.append(event)
        except Exception as e:
            logger.warning(f"Failed to parse event: {e}")
            continue
    
    # Store events
    session_store.append_events(session_id, parsed_events)
    
    # Run anomaly detection
    new_anomalies = []
    for event in parsed_events:
        anomalies = anomaly_detector.update(event)
        for anomaly in anomalies:
            session_store.append_anomaly(session_id, anomaly)
            new_anomalies.append(anomaly)
    
    # Run Bob diagnosis on new anomalies
    diagnoses_generated = 0
    for anomaly in new_anomalies:
        try:
            # Ensure anomaly carries the correct session_id.
            # Pydantic v2 models are immutable; use model_copy() instead of setattr.
            if getattr(anomaly, "session_id", None) != session_id:
                anomaly = anomaly.model_copy(update={"session_id": session_id})
            diagnosis = bob_client.diagnose_anomaly(anomaly, parsed_events)
            session_store.append_diagnosis(session_id, diagnosis)
            diagnoses_generated += 1
        except Exception as e:
            import traceback
            logger.error(f"Bob diagnosis failed for {anomaly.anomaly_type}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    return TelemetryResponse(
        received=len(parsed_events),
        anomalies_detected=len(new_anomalies),
        diagnoses_generated=diagnoses_generated,
        new_anomalies=[a.model_dump() for a in new_anomalies]
    )


@router.get("/session/{session_id}/telemetry")
async def get_telemetry(session_id: str, limit: int = Query(100, ge=1, le=10000)):
    """Get recent telemetry events."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    events = session.telemetry_events[-limit:]
    return {"events": [e.model_dump() for e in events]}


@router.get("/session/{session_id}/anomalies")
async def get_anomalies(session_id: str, limit: int = Query(100, ge=1, le=1000)):
    """Get detected anomalies."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    anomalies = session.anomalies[-limit:]
    return {"anomalies": [a.model_dump() for a in anomalies]}


@router.get("/session/{session_id}/diagnoses")
async def get_diagnoses(session_id: str, limit: int = Query(100, ge=1, le=100)):
    """Get Bob diagnoses."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    diagnoses = session.diagnoses[-limit:]
    return {"diagnoses": [d.model_dump() for d in diagnoses]}


@router.post("/session/{session_id}/diagnose")
async def diagnose_anomaly(session_id: str, anomaly_data: Optional[Dict[str, Any]] = None):
    """Manually trigger diagnosis."""
    if not session_store or not bob_client:
        raise HTTPException(status_code=500, detail="Services not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Use provided anomaly or latest from session
    if anomaly_data:
        try:
            anomaly = AnomalyEvent(**anomaly_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid anomaly data: {e}")
    elif session.anomalies:
        anomaly = session.anomalies[-1]
    else:
        raise HTTPException(status_code=400, detail="No anomaly to diagnose")
    
    # Run diagnosis
    try:
        diagnosis = bob_client.diagnose_anomaly(anomaly, session.telemetry_events)
        session_store.append_diagnosis(session_id, diagnosis)
        return {"diagnosis": diagnosis.model_dump()}
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {e}")


@router.post("/session/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    success = session_store.stop_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "stopped", "session_id": session_id}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    success = session_store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "deleted", "session_id": session_id}

# Made with Bob


# Applied Fix Models
class ApplyFixRequest(BaseModel):
    """Request to record an applied fix."""
    anomaly_id: Optional[str] = None
    diagnosis_id: Optional[str] = None
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    original_code: Optional[str] = None
    replacement_code: str
    explanation: str
    risk_level: str = "medium"
    status: str = "applied"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApplyFixResponse(BaseModel):
    """Response from recording an applied fix."""
    status: str
    fix_id: str
    applied_fix: Dict[str, Any]


@router.post("/session/{session_id}/fixes/applied")
async def record_applied_fix(session_id: str, request: ApplyFixRequest):
    """Record a fix that was applied during the session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Create AppliedFixRecord
    try:
        applied_fix = AppliedFixRecord(
            session_id=session_id,
            anomaly_id=request.anomaly_id,
            diagnosis_id=request.diagnosis_id,
            file_path=request.file_path,
            start_line=request.start_line,
            end_line=request.end_line,
            original_code=request.original_code,
            replacement_code=request.replacement_code,
            explanation=request.explanation,
            risk_level=request.risk_level,
            status=request.status,
            metadata=request.metadata
        )
        
        # Store in session
        session_store.append_applied_fix(session_id, applied_fix)
        
        logger.info(f"Recorded applied fix {applied_fix.fix_id} for session {session_id}")
        
        return ApplyFixResponse(
            status="ok",
            fix_id=applied_fix.fix_id,
            applied_fix=applied_fix.model_dump()
        )
    
    except Exception as e:
        logger.error(f"Failed to record applied fix: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record fix: {e}")


@router.get("/session/{session_id}/fixes/applied")
async def get_applied_fixes(session_id: str):
    """Get all applied fixes for a session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "applied_fixes": [fix.model_dump() for fix in session.applied_fixes]
    }


@router.get("/session/{session_id}/report")
async def generate_report(session_id: str):
    """Generate and return PDF report for a session."""
    if not session_store:
        raise HTTPException(status_code=500, detail="Session store not initialized")
    
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Generate PDF report
        generator = AviexaPDFReportGenerator()
        report_path = generator.generate(session)
        
        # Return as file response
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=f"aviexa_report_{session_id[:8]}.pdf"
        )
    
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


# VS Code Integration Endpoints

class VSCodeStatusResponse(BaseModel):
    """VS Code CLI status response."""
    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    message: str


class VSCodeOpenRequest(BaseModel):
    """Request to open a folder in VS Code."""
    path: str


class VSCodeOpenResponse(BaseModel):
    """Response from opening folder in VS Code."""
    ok: bool
    message: str
    path: Optional[str] = None


@router.get("/vscode/status", response_model=VSCodeStatusResponse)
async def check_vscode_status():
    """Check if VS Code CLI is available."""
    try:
        # Try to find 'code' command
        code_path = shutil.which("code")
        
        if not code_path:
            return VSCodeStatusResponse(
                available=False,
                message="VS Code CLI not found. Install VS Code and add 'code' to PATH."
            )
        
        # Try to get version
        try:
            result = subprocess.run(
                ["code", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip().split('\n')[0] if result.returncode == 0 else None
        except Exception:
            version = None
        
        return VSCodeStatusResponse(
            available=True,
            path=code_path,
            version=version,
            message="VS Code CLI is available and ready."
        )
    
    except Exception as e:
        logger.error(f"Failed to check VS Code status: {e}")
        return VSCodeStatusResponse(
            available=False,
            message=f"Error checking VS Code: {str(e)}"
        )


@router.post("/vscode/open", response_model=VSCodeOpenResponse)
async def open_in_vscode(request: VSCodeOpenRequest):
    """Open a folder in VS Code."""
    try:
        # Validate path
        folder_path = Path(request.path).expanduser().resolve()
        
        if not folder_path.exists():
            return VSCodeOpenResponse(
                ok=False,
                message=f"Folder does not exist: {folder_path}"
            )
        
        if not folder_path.is_dir():
            return VSCodeOpenResponse(
                ok=False,
                message=f"Path is not a directory: {folder_path}"
            )
        
        # Check if code command is available
        if not shutil.which("code"):
            return VSCodeOpenResponse(
                ok=False,
                message="VS Code CLI not found. Install VS Code and add 'code' to PATH."
            )
        
        # Open in VS Code
        try:
            result = subprocess.run(
                ["code", str(folder_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return VSCodeOpenResponse(
                    ok=True,
                    message=f"Successfully opened folder in VS Code",
                    path=str(folder_path)
                )
            else:
                return VSCodeOpenResponse(
                    ok=False,
                    message=f"VS Code command failed: {result.stderr or 'Unknown error'}"
                )
        
        except subprocess.TimeoutExpired:
            # Timeout might mean it's opening in background, which is OK
            return VSCodeOpenResponse(
                ok=True,
                message=f"VS Code is opening folder (command timed out, but likely succeeded)",
                path=str(folder_path)
            )
        
        except Exception as e:
            return VSCodeOpenResponse(
                ok=False,
                message=f"Failed to launch VS Code: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Failed to open folder in VS Code: {e}")
        return VSCodeOpenResponse(
            ok=False,
            message=f"Error: {str(e)}"
        )



class GoldenDemoRequest(BaseModel):
    """Request body for the golden demo endpoint."""
    project_path: Optional[str] = None  # defaults to demo/external_project


@router.post("/demo/golden")
async def run_golden_demo(request: GoldenDemoRequest = None):
    """
    One-shot golden demo path for hackathon judges.

    Steps:
    1. Inspect demo/external_project (or the supplied path) via static analysis.
    2. Simulate the bad-learning-rate / gradient-explosion scenario.
    3. Run Bob mock diagnosis.
    4. Record a suggested applied fix.
    5. Return everything + a report URL.
    """
    if not session_store:
        raise HTTPException(status_code=500, detail="Services not initialized")

    # Resolve project path
    project_path_str = request.project_path if request else None
    project_path = _resolve_project_path(project_path_str, "demo/external_project")

    # Step 1 — static inspection
    try:
        inspection = _static_project_inspection(project_path)
    except Exception as e:
        logger.warning("Golden demo inspection failed: %s", e)
        inspection = {"project": str(project_path), "python_files": 0, "findings": [], "inventory": {}}

    # Step 2 — create session
    session_id = str(uuid.uuid4())
    session_store.create_session(
        session_id=session_id,
        script_path="demo/external_project/train_bad_lr.py",
        metadata={"demo": True, "title": "Golden Demo", "surface": "web-app", "golden": True},
    )
    session_store.update_session(session_id, status=SessionStatus.RUNNING)

    # Step 3 — inject gradient-explosion telemetry
    raw_events = _demo_gradient_explosion(session_id)
    parsed_events = []
    for raw in raw_events:
        try:
            parsed_events.append(_parse_event(raw))
        except Exception as exc:
            logger.warning("Golden demo event parse error: %s", exc)

    session_store.append_events(session_id, parsed_events)

    # Step 4 — anomaly detection
    # Golden demo must be repeat-safe for judges clicking multiple times.
    # Avoid shared detector state from earlier demo or telemetry sessions.
    local_detector = AnomalyDetector()
    new_anomalies = []
    for event in parsed_events:
        for anomaly in local_detector.update(event):
            if getattr(anomaly, "session_id", None) != session_id:
                anomaly = anomaly.model_copy(update={"session_id": session_id})
            session_store.append_anomaly(session_id, anomaly)
            new_anomalies.append(anomaly)

    # Step 5 — Bob mock diagnosis
    from bob import BobClient as _BobClient
    _demo_bob = _BobClient(use_mock=True)
    diagnoses = []
    for anomaly in new_anomalies:
        try:
            diag = _demo_bob.diagnose_anomaly(anomaly, parsed_events)
            session_store.append_diagnosis(session_id, diag)
            diagnoses.append(diag)
        except Exception as exc:
            logger.warning("Golden demo diagnosis error: %s", exc)

    # Step 6 — record applied fix
    fix_payload = {
        "file_path": "demo/external_project/train_bad_lr.py",
        "start_line": 18,
        "end_line": 20,
        "original_code": "loss.backward()\noptimizer.step()",
        "replacement_code": (
            "loss.backward()\n"
            "torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)\n"
            "optimizer.step()"
        ),
        "explanation": (
            "Add gradient clipping (clip_grad_norm_, max_norm=1.0) before optimizer.step() "
            "to prevent the exploding gradients caused by the high learning rate (lr=1.0). "
            "Also consider reducing lr to 1e-3 or adding a lr scheduler."
        ),
        "risk_level": "low",
        "status": "suggested",
    }
    applied_fix = AppliedFixRecord(session_id=session_id, **fix_payload)
    session_store.append_applied_fix(session_id, applied_fix)

    return {
        "session_id": session_id,
        "project_path": str(project_path),
        "python_files": inspection.get("python_files", 0),
        "inventory": inspection.get("inventory", {}),
        "findings": inspection.get("findings", []),
        "anomalies": [a.model_dump() for a in new_anomalies],
        "diagnoses": [d.model_dump() for d in diagnoses],
        "applied_fixes": [applied_fix.model_dump()],
        "report_url": f"/session/{session_id}/report",
        "telemetry_count": len(parsed_events),
    }


# Made with Bob
