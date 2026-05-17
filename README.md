# Aviexa.exe — AI-Powered ML Training Diagnostics

**Title:** Aviexa.exe  
**Tagline:** Your training run has a doctor now.  
**Description:** AI-powered PyTorch ML training diagnostics powered by IBM Bob. Detects gradient explosions, tensor shape mismatches, and loss divergence in real time — then delivers structured root-cause diagnoses, code-level fixes, and exportable PDF reports.

---

## Judge Quick-Start (≤ 5 minutes)

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Start the backend

```powershell
python aviexa.py api
```

Server starts on `http://127.0.0.1:8765`

### 3. Open the Web UI

```
http://127.0.0.1:8765/app
```

### 4. Run the Golden Demo path

The full demo works in a single click from the web UI:

| Step | Action | What happens |
|------|--------|--------------|
| 1 | Click **Check VS Code** | Confirms VS Code CLI availability |
| 2 | Folder: `demo\external_project` (pre-filled) | Points to the bundled bad-LR training script |
| 3 | Click **Inspect Folder** | Static code scan — finds high LR and missing grad clipping |
| 4 | Click **Run Demo** | Full automated path below |
| 5 | Click **Record Fix for PDF** | Confirms the Bob-style suggested fix in the report trail |
| 6 | Click **Export PDF** | Opens the generated diagnostic report |

**Golden Demo auto-runs:**
1. Inspects `demo/external_project/train_bad_lr.py`
2. Simulates gradient explosion telemetry
3. Bob AI generates diagnosis & root-cause
4. Shows a suggested fix (clip_grad_norm_)
5. Records the fix for the demo report trail
6. Returns session ID + PDF report link

The demo records the suggested fix for the PDF evidence trail. It does not rewrite arbitrary user projects unless a real patch flow is added.

---

## CLI Demo Commands

```powershell
# Health check
python aviexa.py health

# Synthetic gradient explosion demo
python aviexa.py demo gradient-explosion

# Real PyTorch training demo
python aviexa.py demo real-gradient-explosion

# Shape mismatch demo
python aviexa.py demo shape-mismatch

# Run external bad-LR script with report
python aviexa.py run demo\external_project\train_bad_lr.py --report

# Full verification suite
python verify_demo.py
```

---

## Architecture

```
web/index.html + app.js + styles.css
       │ HTTP
api/routes.py (FastAPI)
   ├─ /health               → backend status
   ├─ /vscode/status        → VS Code CLI check
   ├─ /vscode/open          → open folder in VS Code
   ├─ /inspect?path=…       → static ML risk scan
   ├─ /demo/golden          → ONE-SHOT full demo path
   ├─ /demo/run/{scenario}  → individual demo scenarios
   ├─ /session/{id}/report  → generate + serve PDF
   └─ /session/{id}/fixes/applied → record fix
anomaly/detectors.py  → gradient / loss / shape detectors
bob/client.py         → IBM Bob integration (mock safe)
reports/pdf_generator.py → ReportLab PDF reports
```

---

## Technology Stack

- Python · FastAPI · Uvicorn  
- PyTorch (for real training demos)  
- ReportLab · Matplotlib (PDF reports)  
- IBM Bob integration (mock mode — no API key required for demo)  
- VS Code Extension API skeleton  
- Vanilla HTML/CSS/JS web UI  

---

## Bob Integration

Bob is integrated in `bob/client.py`. The demo runs in **mock mode by default** — no `IBM_BOB_API_KEY` required. To use real Bob Shell, set the env var before starting:

```powershell
$env:IBM_BOB_API_KEY = "your_key_here"
python aviexa.py api
```

Bob mock mode returns rich structured diagnoses identical in shape to real Bob responses, so the PDF report and web UI look identical.

For hackathon review, Bob's role is visible in:

- `bob/` — context builder, prompt templates, client boundary, and response parser
- `/demo/golden` — turns detected training issues into Bob-style diagnosis objects
- `Record Fix for PDF` — records Bob's suggested fix into the report trail
- exported PDF reports — show findings, anomaly, Bob diagnosis, suggested fix, and charts

---

## Verification

```powershell
python verify_demo.py
```

All 17 checks should pass (imports, CLI, in-process API, anomaly detection, PDF generation).

---

> **Note for judges:** The code runs fully offline in Bob mock mode. No GPU, no API keys, no internet required for the demo.
