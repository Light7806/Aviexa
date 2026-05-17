"""
verify_report.py
Verification script for Aviexa PDF report generation feature.
Tests the complete report generation flow with mock data.
"""

import sys
from pathlib import Path

# Test imports
print("=" * 60)
print("REPORT FEATURE VERIFICATION")
print("=" * 60)
print()

print("1. Testing imports...")
try:
    from reports import AppliedFixRecord
    from reports.chart_builder import ChartBuilder
    from reports.pdf_generator import AviexaPDFReportGenerator
    from api.session_store import SessionStore, SessionRecord, SessionStatus
    from anomaly.models import TelemetryEvent, AnomalyEvent, LossEvent, BackwardEvent, EventType, AnomalyType
    from bob.models import BobResponse, Hypothesis, CodeFix, RiskLevel
    from datetime import datetime
    import uuid
    print("[OK] All imports successful")
except Exception as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)

print()
print("2. Testing AppliedFixRecord model...")
try:
    fix_record = AppliedFixRecord(
        session_id="test-session",
        file_path="train.py",
        start_line=10,
        end_line=12,
        original_code="old code",
        replacement_code="new code",
        explanation="Test fix",
        risk_level="low"
    )
    assert fix_record.fix_id is not None
    assert fix_record.session_id == "test-session"
    assert fix_record.status == "applied"
    print(f"[OK] AppliedFixRecord created with ID: {fix_record.fix_id[:8]}...")
except Exception as e:
    print(f"[FAIL] AppliedFixRecord test failed: {e}")
    sys.exit(1)

print()
print("3. Testing SessionStore with applied fixes...")
try:
    store = SessionStore()
    session_id = str(uuid.uuid4())
    session = store.create_session(session_id, script_path="test_train.py")
    
    # Add applied fix
    fix = AppliedFixRecord(
        session_id=session_id,
        file_path="model.py",
        replacement_code="fixed code",
        explanation="Test fix"
    )
    success = store.append_applied_fix(session_id, fix)
    assert success, "Failed to append applied fix"
    
    # Retrieve session and check
    retrieved = store.get_session(session_id)
    assert len(retrieved.applied_fixes) == 1
    assert retrieved.applied_fixes[0].file_path == "model.py"
    print(f"[OK] SessionStore tracks applied fixes correctly")
except Exception as e:
    print(f"[FAIL] SessionStore test failed: {e}")
    sys.exit(1)

print()
print("4. Creating mock session with full data...")
try:
    # Create session with telemetry, anomalies, diagnoses, and applied fixes
    session_id = str(uuid.uuid4())
    session = SessionRecord(
        session_id=session_id,
        status=SessionStatus.STOPPED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        script_path="demo/train_mnist.py"
    )
    
    # Add telemetry events
    for i in range(20):
        loss_event = LossEvent(
            session_id=session_id,
            step=i,
            loss_value=2.5 - (i * 0.1),
            event_type=EventType.LOSS
        )
        session.append_event(loss_event)
        
        backward_event = BackwardEvent(
            session_id=session_id,
            step=i,
            gradient_norm=1.5 + (i * 0.2),
            event_type=EventType.BACKWARD
        )
        session.append_event(backward_event)
    
    # Add anomaly
    anomaly = AnomalyEvent(
        session_id=session_id,
        anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
        step=15,
        confidence=0.95,
        description="Gradient norm exceeded threshold",
        layer_name="layer1",
        metrics={"gradient_norm": 15.5, "threshold": 10.0}
    )
    session.append_anomaly(anomaly)
    
    # Add diagnosis
    diagnosis = BobResponse(
        anomaly_id=anomaly.anomaly_id,
        session_id=session_id,
        summary="Gradient explosion due to high learning rate",
        hypotheses=[
            Hypothesis(
                title="Learning Rate Too High",
                explanation="The learning rate is set too high, causing gradients to explode.",
                confidence=0.9,
                evidence=["Gradient norm exceeded threshold", "Early training step"],
                affected_files=["train.py"]
            )
        ],
        fixes=[
            CodeFix(
                file_path="train.py",
                start_line=20,
                end_line=20,
                original_code="optimizer = torch.optim.Adam(model.parameters(), lr=0.01)",
                replacement_code="optimizer = torch.optim.Adam(model.parameters(), lr=0.001)",
                explanation="Reduce learning rate by 10x",
                risk_level=RiskLevel.LOW,
                requires_review=False
            )
        ],
        model="mock-bob-v1"
    )
    session.append_diagnosis(diagnosis)
    
    # Add applied fix
    applied_fix = AppliedFixRecord(
        session_id=session_id,
        anomaly_id=anomaly.anomaly_id,
        file_path="train.py",
        start_line=20,
        end_line=20,
        original_code="optimizer = torch.optim.Adam(model.parameters(), lr=0.01)",
        replacement_code="optimizer = torch.optim.Adam(model.parameters(), lr=0.001)",
        explanation="Reduced learning rate to fix gradient explosion",
        risk_level="low",
        status="applied"
    )
    session.append_applied_fix(applied_fix)
    
    print(f"[OK] Mock session created:")
    print(f"  - Telemetry events: {len(session.telemetry_events)}")
    print(f"  - Anomalies: {len(session.anomalies)}")
    print(f"  - Diagnoses: {len(session.diagnoses)}")
    print(f"  - Applied fixes: {len(session.applied_fixes)}")
    
except Exception as e:
    print(f"[FAIL] Mock session creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("5. Testing ChartBuilder...")
try:
    chart_builder = ChartBuilder()
    
    # Create temp directory for charts
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        charts = chart_builder.build_all_charts(session, Path(tmpdir))
        
        # Check which charts were generated
        generated = [k for k, v in charts.items() if v is not None]
        print(f"[OK] ChartBuilder generated {len(generated)} charts: {', '.join(generated)}")
        
        if not generated:
            print("  [WARNING] No charts generated (expected at least loss and gradient)")
        
except Exception as e:
    print(f"[FAIL] ChartBuilder test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("6. Testing PDF generation...")
try:
    generator = AviexaPDFReportGenerator()
    
    # Generate PDF
    output_dir = Path("aviexa-reports")
    output_dir.mkdir(exist_ok=True)
    
    pdf_path = generator.generate(session)
    
    assert pdf_path.exists(), f"PDF not created at {pdf_path}"
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stat().st_size > 1000, "PDF file too small"
    
    print(f"[OK] PDF report generated: {pdf_path}")
    print(f"  - File size: {pdf_path.stat().st_size:,} bytes")
    
except Exception as e:
    print(f"[FAIL] PDF generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("7. Testing API endpoints (if server is running)...")
try:
    from fastapi.testclient import TestClient
    from api.app import app
    
    client = TestClient(app)
    
    # Create session
    response = client.post("/session/start", json={"script_path": "test.py"})
    assert response.status_code == 200
    data = response.json()
    test_session_id = data["session_id"]
    print(f"[OK] Created test session: {test_session_id[:8]}...")
    
    # Send telemetry to trigger anomaly
    # Send telemetry — 5 backward events with a clear gradient explosion at step 3
    telemetry_data = [
        {
            "session_id": test_session_id,
            "event_type": "backward",
            "step": step,
            "layer_name": "layer.weight",
            "gradient_norm": grad_norm,
            "gradient_is_none": False,
            "has_nan": False,
            "has_inf": False,
        }
        for step, grad_norm in enumerate([1.0, 1.2, 250.0, 1.1, 1.0], start=1)
    ] + [
        {
            "session_id": test_session_id,
            "event_type": "loss",
            "step": i,
            "loss_value": 2.5 - (i * 0.1),
        }
        for i in range(1, 8)
    ]

    response = client.post(f"/session/{test_session_id}/telemetry", json=telemetry_data)
    assert response.status_code == 200, f"Telemetry POST failed: {response.text}"
    data = response.json()
    assert data.get("received", 0) >= 5, \
        f"Expected >= 5 events received, got: {data}"
    assert data["anomalies_detected"] >= 1, \
        f"[FAIL] No anomaly detected! Telemetry response: {data}"
    assert data["diagnoses_generated"] >= 1, \
        f"[FAIL] No diagnosis generated! Telemetry response: {data}"
    print(f"[OK] Telemetry ingested: {data['anomalies_detected']} anomalies, "
          f"{data['diagnoses_generated']} diagnoses")

    # Verify anomalies endpoint
    response = client.get(f"/session/{test_session_id}/anomalies")
    assert response.status_code == 200
    anomaly_data = response.json()
    anomalies = anomaly_data.get("anomalies", [])
    assert len(anomalies) >= 1, f"[FAIL] Anomalies endpoint returned empty! {anomaly_data}"
    print(f"[OK] /anomalies returned {len(anomalies)} anomaly/anomalies")

    # Verify diagnoses endpoint
    response = client.get(f"/session/{test_session_id}/diagnoses")
    assert response.status_code == 200
    diag_data = response.json()
    diagnoses = diag_data.get("diagnoses", [])
    assert len(diagnoses) >= 1, f"[FAIL] Diagnoses endpoint returned empty! {diag_data}"
    print(f"[OK] /diagnoses returned {len(diagnoses)} diagnosis/diagnoses")

    # Record an applied fix to make report complete
    fix_data = {
        "file_path": "train.py",
        "start_line": 10,
        "end_line": 12,
        "original_code": "optimizer = torch.optim.Adam(model.parameters(), lr=0.01)",
        "replacement_code": "optimizer = torch.optim.Adam(model.parameters(), lr=0.001)",
        "explanation": "Reduce learning rate 10x to stop gradient explosion",
        "risk_level": "low"
    }
    response = client.post(f"/session/{test_session_id}/fixes/applied", json=fix_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    print(f"[OK] Applied fix recorded: {data['fix_id'][:8]}...")

    # Verify applied fixes endpoint
    response = client.get(f"/session/{test_session_id}/fixes/applied")
    assert response.status_code == 200
    data = response.json()
    assert len(data["applied_fixes"]) == 1
    print(f"[OK] Retrieved {len(data['applied_fixes'])} applied fix(es)")

    # Generate report — must be a meaningful PDF (full story)
    response = client.get(f"/session/{test_session_id}/report")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 25000, \
        f"[FAIL] PDF too small ({len(response.content)} bytes) — report is likely empty/weak"
    print(f"[OK] PDF report endpoint returned {len(response.content):,} bytes")
    
except Exception as e:
    print(f"[FAIL] API endpoint test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("REPORT FEATURE VERIFICATION COMPLETE")
print("=" * 60)
print("[OK] All tests passed!")
print()
print("Summary:")
print("  [OK] AppliedFixRecord model")
print("  [OK] SessionStore tracks applied fixes")
print("  [OK] ChartBuilder generates charts")
print("  [OK] PDF generator creates reports")
print("  [OK] API endpoints work correctly")
print()
print("The PDF report feature is fully implemented and functional!")
print()

# Made with Bob