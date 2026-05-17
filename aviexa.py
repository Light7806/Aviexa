"""
aviexa.py — Aviexa CLI entry point.

Commands:
  python aviexa.py health
  python aviexa.py api
  python aviexa.py demo gradient-explosion
  python aviexa.py demo real-gradient-explosion
  python aviexa.py demo healthy
  python aviexa.py demo shape-mismatch
  python aviexa.py report <session_id>
  python aviexa.py run <script_path> [--timeout SECONDS] [--report|--no-report] [--scenario-name NAME]
  python aviexa.py inspect <project_path>
"""

import sys
import os
import argparse
import json
import logging
from pathlib import Path

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,          # suppress INFO from sub-modules
    format="%(levelname)s: %(message)s",
)
_log = logging.getLogger("aviexa.cli")


# ── Internal client (TestClient or real HTTP) ─────────────────────────────────

class _TestClientAdapter:
    """
    Adapter that wraps FastAPI TestClient so it exposes the same
    .get(path) / .post(path, json_body=...) interface as _HttpClient.
    The raw TestClient.post() uses json=, not json_body=.
    """
    def __init__(self, tc):
        self._tc = tc

    def get(self, path: str):
        return self._tc.get(path)

    def post(self, path: str, json_body):
        return self._tc.post(path, json=json_body)


def _get_client():
    """
    Try the live API on localhost:8765 first.
    Fall back to FastAPI TestClient (zero-dependency, no server needed).
    Returns (client, mode) where mode is 'http' or 'testclient'.
    """
    port = int(os.environ.get("AVIEXA_API_PORT", "8765"))
    try:
        import urllib.request
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
        # Live API is up — use a thin HTTP wrapper
        return _HttpClient(f"http://localhost:{port}"), "http"
    except Exception:
        from fastapi.testclient import TestClient
        from api.app import app
        return _TestClientAdapter(TestClient(app)), "testclient"


class _HttpClient:
    """Thin wrapper so TestClient and HTTP share the same .get/.post interface."""
    def __init__(self, base_url: str):
        import urllib.request, urllib.error
        self._base = base_url
        self._req = urllib.request

    def get(self, path: str):
        import urllib.request
        url = self._base + path
        with urllib.request.urlopen(url) as r:
            return _Resp(r.read(), dict(r.headers))

    def post(self, path: str, json_body):
        import urllib.request, urllib.error
        import json as _json
        payload = _json.dumps(json_body).encode()
        req = urllib.request.Request(
            self._base + path, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return _Resp(r.read(), dict(r.headers))


class _Resp:
    def __init__(self, content: bytes, headers: dict):
        self.content = content
        self.status_code = 200
        self.headers = {k.lower(): v for k, v in headers.items()}
    def json(self):
        return json.loads(self.content)


# ── Shared demo engine ────────────────────────────────────────────────────────

def _run_demo(
    scenario: str,
    telemetry_events: list,
    applied_fix: dict,
    *,
    quiet: bool = False,
) -> dict:
    """
    Core demo engine used by all demo subcommands.

    Returns a result dict with session_id, anomalies, diagnoses, report_path.
    Raises SystemExit(1) on any hard failure.
    """
    client, mode = _get_client()
    if not quiet:
        print(f"\n{'='*60}")
        print(f"  Aviexa Demo: {scenario}")
        print(f"  API mode   : {mode}")
        print(f"{'='*60}")

    # 1. Start session
    r = client.post("/session/start", json_body={"script_path": f"demo/{scenario}.py", "metadata": {"demo": True}})
    _assert(r.status_code == 200, f"Failed to start session: {r.content}")
    session_id = r.json()["session_id"]
    if not quiet:
        print(f"\n[1] Session started: {session_id}")

    # 2. Send telemetry
    r = client.post(f"/session/{session_id}/telemetry", json_body=telemetry_events)
    _assert(r.status_code == 200, f"Telemetry POST failed: {r.content}")
    t = r.json()
    received      = t.get("received", 0)
    n_anomalies   = t.get("anomalies_detected", 0)
    n_diagnoses   = t.get("diagnoses_generated", 0)

    if not quiet:
        print(f"[2] Telemetry: {received} events sent")
        print(f"    Anomalies detected  : {n_anomalies}")
        print(f"    Bob diagnoses       : {n_diagnoses}")

    # 3. Fail fast if no anomaly/diagnosis (gradient-explosion scenario expects them)
    if scenario != "healthy":
        _assert(n_anomalies >= 1,
                f"No anomaly detected for '{scenario}'! Check threshold. Response: {t}")
        _assert(n_diagnoses >= 1,
                f"No Bob diagnosis for '{scenario}'! Response: {t}")

    # 4. Fetch anomalies + diagnoses for summary
    anomalies = client.get(f"/session/{session_id}/anomalies").json().get("anomalies", [])
    diagnoses  = client.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])

    # 5. Record applied fix
    r = client.post(f"/session/{session_id}/fixes/applied", json_body=applied_fix)
    _assert(r.status_code == 200, f"Applied fix POST failed: {r.content}")
    fix_id = r.json()["fix_id"]
    if not quiet:
        print(f"[3] Applied fix recorded: {fix_id[:8]}...")

    # 6. Generate PDF report
    r = client.get(f"/session/{session_id}/report")
    _assert(r.status_code == 200, "Report endpoint failed")
    _assert(len(r.content) > 25_000,
            f"PDF too small ({len(r.content)} bytes) — report is weak")

    # Save PDF to disk
    report_dir = Path("aviexa-reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"demo_{scenario}_{session_id[:8]}.pdf"
    report_path.write_bytes(r.content)

    if not quiet:
        print(f"[4] PDF report: {report_path}  ({len(r.content):,} bytes)")

    # 7. Print suggested fixes summary
    if not quiet and diagnoses:
        all_fixes = [fx for d in diagnoses for fx in d.get("fixes", [])]
        if all_fixes:
            print(f"\n--- Suggested Fixes ({len(all_fixes)}) ---")
            for i, fx in enumerate(all_fixes, 1):
                print(f"  {i}. {fx.get('file_path','?')} L{fx.get('start_line','?')}"
                      f"  risk={fx.get('risk_level','?')}")
                print(f"     {fx.get('explanation','')}")

    # 8. Final summary
    if not quiet:
        print(f"\n{'='*60}")
        print(f"  DEMO COMPLETE")
        print(f"  Session ID  : {session_id}")
        print(f"  Events sent : {received}")
        print(f"  Anomalies   : {n_anomalies}")
        print(f"  Diagnoses   : {n_diagnoses}")
        print(f"  Report      : {report_path}")
        print(f"{'='*60}\n")

    return {
        "session_id":   session_id,
        "received":     received,
        "anomalies":    n_anomalies,
        "diagnoses":    n_diagnoses,
        "report_path":  str(report_path),
        "report_bytes": len(r.content),
    }


def _assert(cond: bool, msg: str):
    if not cond:
        print(f"\n[FAIL] {msg}", file=sys.stderr)
        sys.exit(1)


# ── Telemetry builders ────────────────────────────────────────────────────────

def _telemetry_gradient_explosion(session_id: str) -> list:
    """5 backward events with a clear gradient explosion at step 3, plus 7 loss events."""
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


def _telemetry_healthy(session_id: str) -> list:
    """Clean declining loss, stable gradient norms — no anomaly expected."""
    events = []
    for step in range(1, 16):
        events.append({
            "session_id": session_id,
            "event_type": "backward",
            "step": step,
            "layer_name": "fc1.weight",
            "gradient_norm": 0.5 + 0.02 * (15 - step),
            "gradient_is_none": False,
            "has_nan": False,
            "has_inf": False,
        })
        events.append({
            "session_id": session_id,
            "event_type": "loss",
            "step": step,
            "loss_value": max(0.05, 2.0 - step * 0.12),
        })
    return events


def _telemetry_shape_mismatch(session_id: str) -> list:
    """Real ShapeEvent telemetry — emits a shape mismatch for the fc layer."""
    events = []
    # Normal loss and backward events for context
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
    # Real shape mismatch event: backbone outputs (batch, 128) but fc expects (batch, 256)
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


def _run_real_pytorch_training(session_id: str) -> tuple[list, dict]:
    """
    Run a real tiny PyTorch model with intentional gradient explosion.
    Returns (telemetry_events, training_stats).
    
    Uses:
    - torch.manual_seed for reproducibility
    - Intentionally bad learning rate (10.0) to cause gradient explosion
    - Small model (2 layers)
    - Synthetic CPU tensors
    - Captures real loss and gradient norms
    """
    import torch
    import torch.nn as nn
    
    # Ensure reproducibility
    torch.manual_seed(42)
    
    # Tiny synthetic dataset
    N = 64
    X = torch.randn(N, 8)
    Y = torch.randint(0, 2, (N,)).float()
    
    # Small model
    class TinyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(8, 16)
            self.fc2 = nn.Linear(16, 1)
        
        def forward(self, x):
            return self.fc2(torch.relu(self.fc1(x))).squeeze(1)
    
    model = TinyNet()
    
    # INTENTIONALLY BAD: learning rate too high to guarantee gradient explosion
    # lr=100.0 ensures gradient norms will exceed the 100.0 detector threshold
    optimizer = torch.optim.SGD(model.parameters(), lr=100.0)
    criterion = nn.BCEWithLogitsLoss()
    
    events = []
    max_grad_norm = 0.0
    final_loss = 0.0
    
    # Train for 10 steps
    BATCH = 16
    for step in range(1, 11):
        idx = torch.randint(0, N, (BATCH,))
        xb, yb = X[idx], Y[idx]
        
        optimizer.zero_grad()
        output = model(xb)
        loss = criterion(output, yb)
        loss.backward()
        
        # Capture real loss
        loss_val = loss.item()
        final_loss = loss_val
        events.append({
            "session_id": session_id,
            "event_type": "loss",
            "step": step,
            "loss_value": loss_val,
        })
        
        # Capture real gradient norms for each layer
        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                max_grad_norm = max(max_grad_norm, grad_norm)
                
                events.append({
                    "session_id": session_id,
                    "event_type": "backward",
                    "step": step,
                    "layer_name": name,
                    "gradient_norm": grad_norm,
                    "gradient_is_none": False,
                    "has_nan": torch.isnan(param.grad).any().item(),
                    "has_inf": torch.isinf(param.grad).any().item(),
                })
        
        optimizer.step()
    
    stats = {
        "max_gradient_norm": max_grad_norm,
        "final_loss": final_loss,
        "total_steps": 10,
        "events_generated": len(events),
    }
    
    return events, stats


# ── Applied-fix templates ────────────────────────────────────────────────────

_FIX_GRADIENT_EXPLOSION = {
    "file_path": "demo/planted_bugs/bug_gradient_explosion.py",
    "start_line": 32,  # Line 32: optimizer = torch.optim.SGD(model.parameters(), lr=100.0)
    "end_line": 33,
    "original_code": "optimizer = torch.optim.SGD(model.parameters(), lr=100.0)  # BUG: should be 0.001",
    "replacement_code": (
        "optimizer = torch.optim.SGD(model.parameters(), lr=0.001)\n"
        "torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)"
    ),
    "explanation": "Reduce learning rate from 100.0 to 0.001 and add gradient clipping.",
    "risk_level": "low",
}

_FIX_HEALTHY = {
    "file_path": "demo/scripts/train_mnist.py",
    "start_line": 1,
    "end_line": 1,
    "original_code": "# no fix needed",
    "replacement_code": "# no fix needed — baseline is healthy",
    "explanation": "Training is healthy. No changes required.",
    "risk_level": "low",
}

_FIX_SHAPE_MISMATCH = {
    "file_path": "demo/planted_bugs/bug_shape_mismatch.py",
    "start_line": 21,  # Line 21: self.fc = nn.Linear(256, 10)  # BUG
    "end_line": 21,
    "original_code": "self.fc = nn.Linear(256, 10)          # BUG: should be nn.Linear(128, 10)",
    "replacement_code": "self.fc = nn.Linear(128, 10)",
    "explanation": "Fix Linear input dimension: backbone outputs 128, not 256.",
    "risk_level": "medium",
}


# ── CLI subcommands ───────────────────────────────────────────────────────────

def cmd_health(args):
    client, mode = _get_client()
    r = client.get("/health")
    d = r.json()
    print(f"Aviexa API health — mode: {mode}")
    print(json.dumps(d, indent=2))


def cmd_api(args):
    """Start the Uvicorn dev server."""
    import subprocess
    port = int(os.environ.get("AVIEXA_API_PORT", "8765"))
    print(f"Starting Aviexa API on http://0.0.0.0:{port} ...")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "api.app:app",
        "--host", "0.0.0.0", "--port", str(port), "--reload"
    ])


def cmd_demo(args):
    scenario = args.scenario

    # Need session_id before building telemetry — obtain it first
    client, _ = _get_client()
    r = client.post("/session/start", json_body={
        "script_path": f"demo/{scenario}.py", "metadata": {"demo": True}
    })
    _assert(r.status_code == 200, f"Could not start session: {r.content}")
    session_id = r.json()["session_id"]

    if scenario == "gradient-explosion":
        telemetry = _telemetry_gradient_explosion(session_id)
        fix       = _FIX_GRADIENT_EXPLOSION
        stats     = None
    elif scenario == "real-gradient-explosion":
        print("\n" + "="*60)
        print("  Running REAL PyTorch gradient explosion demo")
        print("  (actual training loop with real telemetry capture)")
        print("="*60)
        telemetry, stats = _run_real_pytorch_training(session_id)
        fix = _FIX_GRADIENT_EXPLOSION
        print(f"\n[Training Complete]")
        print(f"  Max gradient norm : {stats['max_gradient_norm']:.2f}")
        print(f"  Final loss        : {stats['final_loss']:.4f}")
        print(f"  Events generated  : {stats['events_generated']}")
    elif scenario == "healthy":
        telemetry = _telemetry_healthy(session_id)
        fix       = _FIX_HEALTHY
        stats     = None
    elif scenario == "shape-mismatch":
        telemetry = _telemetry_shape_mismatch(session_id)
        fix       = _FIX_SHAPE_MISMATCH
        stats     = None
    else:
        print(f"Unknown scenario: {scenario}", file=sys.stderr)
        sys.exit(1)

    fix["session_id"] = session_id

    # Re-use engine but skip the internal session start (already done above)
    _run_demo_from_existing_session(
        scenario=scenario,
        session_id=session_id,
        client=client,
        telemetry_events=telemetry,
        applied_fix=fix,
        training_stats=stats,
    )


def _run_demo_from_existing_session(scenario, session_id, client, telemetry_events, applied_fix, training_stats=None):
    """Like _run_demo but skips the session/start call."""
    from pathlib import Path

    print(f"\n{'='*60}")
    print(f"  Aviexa Demo: {scenario}")
    print(f"{'='*60}")
    print(f"\n[1] Session: {session_id}")

    r = client.post(f"/session/{session_id}/telemetry", json_body=telemetry_events)
    _assert(r.status_code == 200, f"Telemetry failed: {r.content}")
    t = r.json()
    received    = t.get("received", 0)
    n_anomalies = t.get("anomalies_detected", 0)
    n_diagnoses = t.get("diagnoses_generated", 0)

    print(f"[2] Telemetry : {received} events sent")
    print(f"    Anomalies : {n_anomalies}")
    print(f"    Diagnoses : {n_diagnoses}")
    
    if training_stats:
        print(f"\n[Real Training Stats]")
        print(f"    Max gradient norm : {training_stats['max_gradient_norm']:.2f}")
        print(f"    Final loss        : {training_stats['final_loss']:.4f}")

    if scenario != "healthy":
        _assert(n_anomalies >= 1, f"No anomaly for '{scenario}'! {t}")
        _assert(n_diagnoses >= 1, f"No diagnosis for '{scenario}'! {t}")

    diagnoses = client.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])

    r = client.post(f"/session/{session_id}/fixes/applied", json_body=applied_fix)
    _assert(r.status_code == 200, f"Applied fix failed: {r.content}")
    fix_id = r.json()["fix_id"]
    print(f"[3] Applied fix: {fix_id[:8]}...")

    r = client.get(f"/session/{session_id}/report")
    _assert(r.status_code == 200, "Report endpoint failed")
    _assert(len(r.content) > 25_000, f"PDF too small ({len(r.content)} bytes)")

    report_dir  = Path("aviexa-reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"demo_{scenario}_{session_id[:8]}.pdf"
    report_path.write_bytes(r.content)
    print(f"[4] Report    : {report_path}  ({len(r.content):,} bytes)")

    if diagnoses:
        all_fixes = [fx for d in diagnoses for fx in d.get("fixes", [])]
        if all_fixes:
            print(f"\n--- Suggested Fixes ({len(all_fixes)}) ---")
            for i, fx in enumerate(all_fixes, 1):
                print(f"  {i}. {fx.get('file_path','?')} "
                      f"L{fx.get('start_line','?')}  risk={fx.get('risk_level','?')}")
                print(f"     {fx.get('explanation','')}")

    print(f"\n{'='*60}")
    print(f"  DEMO COMPLETE — {scenario}")
    print(f"  Session  : {session_id}")
    print(f"  Events   : {received}  |  Anomalies: {n_anomalies}  |  Diagnoses: {n_diagnoses}")
    print(f"  Report   : {report_path}")
    print(f"{'='*60}\n")


def cmd_report(args):
    client, mode = _get_client()
    session_id = args.session_id
    r = client.get(f"/session/{session_id}/report")
    _assert(r.status_code == 200, "Report endpoint failed")
    report_dir  = Path("aviexa-reports")
    report_dir.mkdir(exist_ok=True)
    out = report_dir / f"report_{session_id[:8]}.pdf"
    out.write_bytes(r.content)
    print(f"Report saved: {out}  ({len(r.content):,} bytes)")


def cmd_run(args):
    """
    Run a user-provided training script with Aviexa telemetry collection.
    
    Workflow:
    1. Start an Aviexa session
    2. Execute the training script as a subprocess
    3. Parse AVIEXA_TELEMETRY lines from stdout
    4. Capture exit code
    5. Collect anomalies and diagnoses
    6. Optionally generate a PDF report
    """
    import subprocess
    import re
    from pathlib import Path
    
    script_path = args.script_path
    timeout = args.timeout
    generate_report = args.report
    scenario_name = args.scenario_name or Path(script_path).stem
    
    # Validate script exists
    if not Path(script_path).exists():
        print(f"[FAIL] Script not found: {script_path}", file=sys.stderr)
        sys.exit(1)
    
    client, mode = _get_client()
    
    print(f"\n{'='*60}")
    print(f"  Aviexa Run: {script_path}")
    print(f"  API mode  : {mode}")
    print(f"{'='*60}")
    
    # 1. Start session
    r = client.post("/session/start", json_body={
        "script_path": script_path,
        "metadata": {"scenario": scenario_name, "run_mode": "external"}
    })
    _assert(r.status_code == 200, f"Failed to start session: {r.content}")
    session_id = r.json()["session_id"]
    print(f"\n[1] Session started: {session_id}")
    
    # 2. Execute training script as subprocess
    env = os.environ.copy()
    env["AVIEXA_SESSION_ID"] = session_id
    env["AVIEXA_API_URL"] = "http://localhost:8765" if mode == "http" else "testclient"
    env["AVIEXA_API_MODE"] = mode
    
    print(f"[2] Executing: {script_path}")
    print(f"    Environment: AVIEXA_SESSION_ID={session_id}")
    
    telemetry_events = []
    telemetry_pattern = re.compile(r'^AVIEXA_TELEMETRY:\s*(\{.*\})$')
    
    try:
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
        )
        
        # Capture stdout line by line
        stdout_lines = []
        stderr_lines = []
        
        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                stdout_lines.append(line)
                
                # Check for telemetry JSON lines
                match = telemetry_pattern.match(line)
                if match:
                    try:
                        telemetry_json = json.loads(match.group(1))
                        telemetry_json["session_id"] = session_id
                        telemetry_events.append(telemetry_json)
                    except json.JSONDecodeError as e:
                        print(f"    [WARN] Invalid telemetry JSON: {e}", file=sys.stderr)
                else:
                    # Print non-telemetry output
                    print(f"    {line}")
        
        # Wait for process to complete
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            print(f"\n[WARN] Process killed after {timeout}s timeout", file=sys.stderr)
        
        # Capture stderr
        if process.stderr:
            stderr_lines = process.stderr.read().splitlines()
            if stderr_lines:
                print(f"\n[stderr output]:")
                for line in stderr_lines:
                    print(f"    {line}")
        
        exit_code = process.returncode
        
    except Exception as e:
        print(f"\n[FAIL] Subprocess execution failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n[3] Script completed with exit code: {exit_code}")
    print(f"    Telemetry events captured: {len(telemetry_events)}")
    
    # 3. Send telemetry to API if any was captured
    n_anomalies = 0
    n_diagnoses = 0
    
    if telemetry_events:
        r = client.post(f"/session/{session_id}/telemetry", json_body=telemetry_events)
        _assert(r.status_code == 200, f"Telemetry POST failed: {r.content}")
        t = r.json()
        n_anomalies = t.get("anomalies_detected", 0)
        n_diagnoses = t.get("diagnoses_generated", 0)
        
        print(f"[4] Telemetry processed:")
        print(f"    Anomalies detected  : {n_anomalies}")
        print(f"    Bob diagnoses       : {n_diagnoses}")
    else:
        print(f"[4] No telemetry events captured")
        print(f"    Tip: Use AVIEXA_TELEMETRY: {{...}} format in stdout")
    
    # 4. Fetch anomalies and diagnoses
    anomalies = client.get(f"/session/{session_id}/anomalies").json().get("anomalies", [])
    diagnoses = client.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])
    
    # 5. Generate report if requested
    report_path = None
    report_bytes = 0
    
    if generate_report:
        print(f"[5] Generating PDF report...")
        r = client.get(f"/session/{session_id}/report")
        _assert(r.status_code == 200, "Report endpoint failed")
        
        report_dir = Path("aviexa-reports")
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"run_{scenario_name}_{session_id[:8]}.pdf"
        report_path.write_bytes(r.content)
        report_bytes = len(r.content)
        
        print(f"    Report saved: {report_path}  ({report_bytes:,} bytes)")
    
    # 6. Print summary
    print(f"\n{'='*60}")
    print(f"  RUN COMPLETE")
    print(f"  Session ID       : {session_id}")
    print(f"  Script           : {script_path}")
    print(f"  Exit code        : {exit_code}")
    print(f"  Telemetry count  : {len(telemetry_events)}")
    print(f"  Anomalies count  : {n_anomalies}")
    print(f"  Diagnoses count  : {n_diagnoses}")
    if report_path:
        print(f"  Report path      : {report_path}")
    print(f"{'='*60}\n")
    
    # Print anomaly summary if any
    if anomalies:
        print(f"--- Detected Anomalies ({len(anomalies)}) ---")
        for i, anom in enumerate(anomalies, 1):
            print(f"  {i}. {anom.get('anomaly_type', '?')} at step {anom.get('step', '?')}")
            print(f"     Severity: {anom.get('severity', '?')}")
    
    # Print diagnosis summary if any
    if diagnoses:
        print(f"\n--- Bob Diagnoses ({len(diagnoses)}) ---")
        for i, diag in enumerate(diagnoses, 1):
            print(f"  {i}. {diag.get('title', '?')}")
            fixes = diag.get('fixes', [])
            if fixes:
                print(f"     Suggested fixes: {len(fixes)}")
    
    # Exit with script's exit code
    sys.exit(exit_code)


# ── Project inspector ─────────────────────────────────────────────────────────

def cmd_inspect(args):
    """Scan an ML project folder for likely PyTorch training risks."""
    import re
    from datetime import datetime

    project_path = Path(args.project_path).resolve()
    if not project_path.exists():
        print(f"[FAIL] Project path not found: {project_path}", file=sys.stderr)
        sys.exit(1)

    exclude_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "aviexa-reports"}
    py_files = [
        p for p in project_path.rglob("*.py")
        if not any(part in exclude_dirs for part in p.parts)
    ]

    inventory = {
        "training_files": [],
        "model_files": [],
        "optimizer_files": [],
        "loss_files": [],
    }
    findings = []

    rules = [
        (
            "high-learning-rate",
            "high",
            re.compile(r"lr\s*=\s*(?:1\.0|[2-9](?:\.0)?|[1-9]\d+(?:\.\d+)?)"),
            "Very high learning rate can cause loss divergence or gradient explosion.",
            "Reduce the learning rate or add a scheduler; start near 1e-3 for Adam-style optimizers.",
        ),
        (
            "backward-without-gradient-clipping",
            "medium",
            re.compile(r"\.backward\s*\("),
            "Backward pass found without visible gradient clipping in this file.",
            "Add torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0) before optimizer.step().",
        ),
        (
            "missing-zero-grad-risk",
            "high",
            re.compile(r"optimizer\.step\s*\("),
            "optimizer.step() found; verify gradients are cleared every iteration.",
            "Call optimizer.zero_grad() before loss.backward() in each training iteration.",
        ),
        (
            "sigmoid-vanishing-gradient-risk",
            "medium",
            re.compile(r"nn\.Sigmoid|torch\.sigmoid"),
            "Sigmoid activations can saturate and contribute to vanishing gradients.",
            "Consider ReLU/GELU, normalization, or residual paths for deeper networks.",
        ),
        (
            "reshape-shape-mismatch-risk",
            "medium",
            re.compile(r"\.view\s*\(|\.reshape\s*\(|flatten\s*\("),
            "Manual reshape/flatten is a common source of tensor shape mismatch bugs.",
            "Assert tensor shapes and verify Linear input dimensions after flatten/reshape.",
        ),
    ]

    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = str(path.relative_to(project_path))
        lowered = text.lower()
        if "backward(" in lowered or "optimizer.step" in lowered or "train" in path.name.lower():
            inventory["training_files"].append(rel)
        if "nn.module" in lowered or "def forward" in lowered:
            inventory["model_files"].append(rel)
        if "optim." in text or "torch.optim" in text:
            inventory["optimizer_files"].append(rel)
        if "loss" in lowered or "criterion" in lowered:
            inventory["loss_files"].append(rel)

        has_clip = "clip_grad_norm" in text or "clip_grad_value" in text
        has_zero_grad = "zero_grad" in text

        for rule_id, severity, pattern, message, fix in rules:
            if rule_id == "backward-without-gradient-clipping" and has_clip:
                continue
            if rule_id == "missing-zero-grad-risk" and has_zero_grad:
                continue
            match = pattern.search(text)
            if not match:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append({
                "id": rule_id,
                "severity": severity,
                "file": rel,
                "line": line_no,
                "message": message,
                "fix": fix,
            })

    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")

    report_dir = Path("aviexa-reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"inspect_{project_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    lines = [
        "# Aviexa Project Inspection Report",
        "",
        f"Project: `{project_path}`",
        f"Python files scanned: {len(py_files)}",
        f"Findings: {len(findings)} ({high} high, {medium} medium)",
        "",
        "## ML Inventory",
        "",
    ]
    for key, files in inventory.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {len(files)}")
        for file in files[:8]:
            lines.append(f"  - `{file}`")
    lines.extend(["", "## Findings", ""])
    if findings:
        for idx, finding in enumerate(findings, 1):
            lines.extend([
                f"### {idx}. {finding['id']} ({finding['severity']})",
                "",
                f"- Location: `{finding['file']}` line {finding['line']}",
                f"- Why it matters: {finding['message']}",
                f"- Suggested fix: {finding['fix']}",
                "",
            ])
    else:
        lines.append("No common ML training risks were detected by the static inspector.")
    lines.extend([
        "",
        "## Bob Context",
        "",
        "This report is Bob-ready context: Aviexa identified likely training files, risk patterns, and candidate fixes before runtime instrumentation.",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print("  AVIEXA PROJECT INSPECTION")
    print(f"{'='*60}")
    print(f"  Project        : {project_path}")
    print(f"  Python files   : {len(py_files)}")
    print(f"  Training files : {len(inventory['training_files'])}")
    print(f"  Model files    : {len(inventory['model_files'])}")
    print(f"  Findings       : {len(findings)} ({high} high, {medium} medium)")
    print(f"  Report         : {report_path}")
    print(f"{'='*60}\n")

    for finding in findings[:8]:
        print(f"[{finding['severity'].upper()}] {finding['file']}:{finding['line']}  {finding['id']}")
        print(f"       {finding['message']}")
        print(f"       Fix: {finding['fix']}")
    if len(findings) > 8:
        print(f"\n... {len(findings) - 8} more finding(s) in {report_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="aviexa",
        description="Aviexa — AI-powered ML training diagnostics CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Check API health")
    sub.add_parser("api",    help="Start the Aviexa API server")

    demo_p = sub.add_parser("demo", help="Run a demo scenario")
    demo_p.add_argument(
        "scenario",
        choices=["gradient-explosion", "real-gradient-explosion", "healthy", "shape-mismatch"],
        help="Demo scenario to run",
    )

    rep_p = sub.add_parser("report", help="Export PDF for a session")
    rep_p.add_argument("session_id", help="Session ID to export")

    run_p = sub.add_parser("run", help="Run a training script with Aviexa telemetry")
    run_p.add_argument("script_path", help="Path to the training script")
    run_p.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    run_p.add_argument("--report", dest="report", action="store_true", default=True, help="Generate PDF report (default)")
    run_p.add_argument("--no-report", dest="report", action="store_false", help="Skip PDF report generation")
    run_p.add_argument("--scenario-name", help="Custom scenario name for the report")

    inspect_p = sub.add_parser("inspect", help="Scan any ML project folder for likely training risks")
    inspect_p.add_argument("project_path", help="Path to the ML project folder to inspect")

    args = parser.parse_args()

    dispatch = {
        "health": cmd_health,
        "api":    cmd_api,
        "demo":   cmd_demo,
        "report": cmd_report,
        "run":    cmd_run,
        "inspect": cmd_inspect,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
