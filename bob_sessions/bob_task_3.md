**User:**

<task>
Implement a real PyTorch training demo path for Aviexa, so the demo is not only synthetic telemetry.

Current status:
- CLI demo command works:
  python aviexa.py demo gradient-explosion
- It currently uses deterministic synthetic telemetry.
- That is reliable, but for hackathon credibility we need a real tiny PyTorch training run where Aviexa captures actual loss/gradient telemetry from training.

Goal:
Add a real training demo command:

python aviexa.py demo real-gradient-explosion

This command should:
1. Run a tiny PyTorch model on synthetic CPU tensors.
2. Use an intentionally bad learning rate or scale to create real gradient explosion.
3. Capture real telemetry from the actual training loop.
4. Send telemetry events to the existing API.
5. Trigger anomaly detection.
6. Generate Bob diagnosis.
7. Record an applied fix.
8. Export a PDF report.
9. Print a clean terminal summary.

Do not use internet downloads.
Do not require GPU.
Do not require MNIST.
Do not require real IBM Bob API.
Do not break the existing synthetic demo command.

Implementation options:
- Either use AviexaSession directly to collect ForwardEvent, BackwardEvent, LossEvent, MemoryEvent from a real model,
- or manually collect real loss/gradient norms from the PyTorch training loop and convert them into API telemetry events.

Reliability matters:
- The anomaly must trigger every time.
- Use torch.manual_seed().
- Use a small model.
- Use synthetic tensors.
- Keep runtime under 10 seconds.

Files to update:
1. aviexa.py
2. demo/planted_bugs/bug_gradient_explosion.py if useful
3. verify_demo.py

CLI requirements:
Add scenario:
python aviexa.py demo real-gradient-explosion

The existing scenario must still work:
python aviexa.py demo gradient-explosion

Telemetry requirements:
For the real-gradient-explosion scenario:
- Send actual loss values from training loop.
- Send actual gradient norms from model parameters after loss.backward().
- Include layer_name where possible.
- Include at least 5-10 steps.
- Ensure at least one gradient_norm exceeds the detector threshold.

Verification:
Update verify_demo.py to test both:
1. synthetic gradient-explosion demo flow
2. real-gradient-explosion demo flow

Assertions for real demo:
- events_sent >= 5
- anomalies_detected >= 1
- diagnoses_generated >= 1
- report generated
- report size > 25000 bytes

Terminal output:
The real demo should clearly print:
- “Running real PyTorch gradient explosion demo”
- session_id
- max gradient norm observed
- final loss
- anomalies detected
- diagnoses generated
- report path

Final response:
Summarize:
1. Files changed
2. New CLI command added
3. How real telemetry is captured
4. Verification results
5. Exact command to run
</task>
<environment_details>
# VSCode Visible Files
reports\pdf_generator.py

# VSCode Open Tabs
anomaly/models.py,.gitignore,anomaly/detectors/classifier.py,anomaly/detectors/gradient_detector.py,anomaly/detectors/loss_detector.py,anomaly/detectors/shape_detector.py,anomaly/detectors/__init__.py,anomaly/detectors/detector.py,verify_layer2.py,bob/models.py,bob/response_parser.py,bob/__init__.py,verify_layer3.py,api/app.py,api/__init__.py,bob/client.py,verify_layer4.py,reports/__init__.py,api/session_store.py,reports/chart_builder.py

# Current Time
Current time in ISO 8601 UTC format: 2026-05-16T15:48:53.127Z
User time zone: Asia/Calcutta, UTC+5:30

# Current Cost
$0.00

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**

# Current Mode
<slug>code</slug>
<name>💻 Code</name>


# Current Workspace Directory (c:/Users/ABHIMANYU/OneDrive/Documents/Desktop/aviexa) Files
.env.example
.gitignore
aviexa.py
package.json
README.md
requirements.txt
simulate_training.py
verify_demo.py
verify_layer1.py
verify_layer2.py
verify_layer3.py
verify_layer4.py
verify_polish.py
verify_report.py
anomaly/
anomaly/__init__.py
anomaly/models.py
anomaly/detectors/
anomaly/detectors/__init__.py
anomaly/detectors/classifier.py
anomaly/detectors/detector.py
anomaly/detectors/gradient_detector.py
anomaly/detectors/loss_detector.py
anomaly/detectors/shape_detector.py
api/
api/__init__.py
api/app.py
api/routes.py
api/session_store.py
aviexa-reports/aviexa_report_0d550f33_20260516_205524.pdf
aviexa-reports/aviexa_report_2b405407_20260516_202421.pdf
aviexa-reports/aviexa_report_4a1c960f_20260516_210931.pdf
aviexa-reports/aviexa_report_7f97e7b0_20260516_202605.pdf
aviexa-reports/aviexa_report_20f08fe8_20260516_201454.pdf
aviexa-reports/aviexa_report_22c292e7_20260516_201013.pdf
aviexa-reports/aviexa_report_26bdfe50_20260516_205522.pdf
aviexa-reports/aviexa_report_29cdcb41_20260516_202420.pdf
aviexa-reports/aviexa_report_82de4974_20260516_201453.pdf
aviexa-reports/aviexa_report_082fda92_20260516_201233.pdf
aviexa-reports/aviexa_report_86f3730a_20260516_204312.pdf
aviexa-reports/aviexa_report_90ff1426_20260516_210939.pdf
aviexa-reports/aviexa_report_168a9e84_20260516_202420.pdf
aviexa-reports/aviexa_report_414a95db_20260516_205307.pdf
aviexa-reports/aviexa_report_6665ec9c_20260516_201015.pdf
aviexa-reports/aviexa_report_8386cf96_20260516_211029.pdf
aviexa-reports/aviexa_report_0162775f_20260516_204312.pdf
aviexa-reports/aviexa_report_442463ef_20260516_201232.pdf
aviexa-reports/aviexa_report_1404237a_20260516_202122.pdf
aviexa-reports/aviexa_report_2550209c_20260516_210737.pdf
aviexa-reports/aviexa_report_a6c0f347_20260516_205731.pdf
aviexa-reports/aviexa_report_ac595430_20260516_204315.pdf
aviexa-reports/aviexa_report_acf197a1_20260516_210655.pdf
aviexa-reports/aviexa_report_b0b1bc77_20260516_205733.pdf
aviexa-reports/aviexa_report_bb15a17c_20260516_205304.pdf
aviexa-reports/aviexa_report_bd0b8e81_20260516_210752.pdf
aviexa-reports/aviexa_report_c8911039_20260516_211027.pdf
aviexa-reports/aviexa_report_d56e1959_20260516_210735.pdf
aviexa-reports/aviexa_report_e8a175ff_20260516_202123.pdf
aviexa-reports/aviexa_report_e5728e38_20260516_202603.pdf
aviexa-reports/demo_gradient-explosion_90ff1426.pdf
aviexa-reports/demo_gradient-explosion_bd0b8e81.pdf
aviexa-reports/verify_demo_4a1c960f.pdf
aviexa-reports/verify_demo_acf197a1.pdf
aviexa-reports/charts/2b405407_gradient_norm.png
aviexa-reports/charts/2b405407_loss_curve.png
aviexa-reports/charts/7f97e7b0_gradient_norm.png
aviexa-reports/charts/7f97e7b0_loss_curve.png
aviexa-reports/charts/29cdcb41_gradient_norm.png
aviexa-reports/charts/29cdcb41_loss_curve.png
aviexa-reports/charts/86f3730a_gradient_norm.png
aviexa-reports/charts/168a9e84_gradient_norm.png
aviexa-reports/charts/0162775f_gradient_norm.png
aviexa-reports/charts/0162775f_loss_curve.png
aviexa-reports/charts/1404237a_gradient_norm.png
aviexa-reports/charts/1404237a_loss_curve.png
aviexa-reports/charts/ac595430_gradient_norm.png
aviexa-reports/charts/ac595430_loss_curve.png
aviexa-reports/charts/e8a175ff_gradient_norm.png
aviexa-reports/charts/e8a175ff_loss_curve.png
aviexa-reports/charts/e5728e38_gradient_norm.png
aviexa-reports/charts/e5728e38_loss_curve.png
aviexa-reports/charts/gradient_norm.png
aviexa-reports/charts/loss_curve.png
aviexa-reports/charts/0d550f33/gradient_norm.png
aviexa-reports/charts/0d550f33/loss_curve.png
aviexa-reports/charts/4a1c960f/gradient_norm.png
aviexa-reports/charts/4a1c960f/loss_curve.png
aviexa-reports/charts/26bdfe50/gradient_norm.png
aviexa-reports/charts/26bdfe50/loss_curve.png
aviexa-reports/charts/90ff1426/gradient_norm.png
aviexa-reports/charts/90ff1426/loss_curve.png
aviexa-reports/charts/414a95db/gradient_norm.png
aviexa-reports/charts/414a95db/loss_curve.png
aviexa-reports/charts/8386cf96/gradient_norm.png
aviexa-reports/charts/8386cf96/loss_curve.png
aviexa-reports/charts/2550209c/gradient_norm.png
aviexa-reports/charts/2550209c/loss_curve.png
aviexa-reports/charts/a6c0f347/gradient_norm.png
aviexa-reports/charts/a6c0f347/loss_curve.png
aviexa-reports/charts/acf197a1/gradient_norm.png
aviexa-reports/charts/acf197a1/loss_curve.png
aviexa-reports/charts/b0b1bc77/gradient_norm.png
aviexa-reports/charts/b0b1bc77/loss_curve.png
aviexa-reports/charts/bb15a17c/gradient_norm.png
aviexa-reports/charts/bb15a17c/loss_curve.png
aviexa-reports/charts/bd0b8e81/gradient_norm.png
aviexa-reports/charts/bd0b8e81/loss_curve.png
aviexa-reports/charts/c8911039/gradient_norm.png
aviexa-reports/charts/c8911039/loss_curve.png
aviexa-reports/charts/d56e1959/gradient_norm.png
aviexa-reports/charts/d56e1959/loss_curve.png
bob/
bob/__init__.py
bob/client.py
bob/context_builder.py
bob/models.py
bob/prompt_templates.py
bob/response_parser.py
core/
core/__init__.py
core/session.py
core/buffer/
core/buffer/__init__.py
core/buffer/ring_buffer.py
core/hooks/
core/hooks/__init__.py
core/hooks/backward_hook.py
core/hooks/forward_hook.py
core/hooks/loss_hook.py
core/tracker/
core/tracker/__init__.py
core/tracker/memory_tracker.py
core/tracker/shape_tracker.py
demo/
demo/planted_bugs/
demo/planted_bugs/bug_gradient_explosion.py
demo/planted_bugs/bug_shape_mismatch.py
demo/planted_bugs/bug_vanishing_gradient.py
demo/scripts/
demo/scripts/train_mnist.py
docs/
docs/ARCHITECTURE.md
docs/BOB_INTEGRATION.md
docs/DEMO_GUIDE.md
extension/
extension/commands/
extension/commands/apply_fix.js
extension/commands/start_session.js
extension/panels/
extension/panels/diagnosis_panel.js
extension/panels/metrics_panel.js
extension/src/
extension/src/extension.js
pytest-cache-files-1lfj2x0n/.gitignore
pytest-cache-files-1lfj2x0n/CACHEDIR.TAG
pytest-cache-files-1lfj2x0n/README.md
reports/
reports/__init__.py
reports/chart_builder.py
reports/pdf_generator.py
tests/
tests/__init__.py
tests/integration/
tests/integration/__init__.py
tests/integration/test_full_pipeline.py
tests/unit/
tests/unit/__init__.py
tests/unit/test_context_builder.py
tests/unit/test_gradient_detector.py
tests/unit/test_loss_detector.py
tests/unit/test_response_parser.py
tests/unit/test_ring_buffer.py
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

I'll implement a real PyTorch training demo path for Aviexa. Let me start by examining the current demo implementation to understand the structure.

<read_file>
<args>
<file>
<path>aviexa.py</path>
</file>
<file>
<path>demo/planted_bugs/bug_gradient_explosion.py</path>
</file>
<file>
<path>verify_demo.py</path>
</file>
</args>
</read_file>

---

**User:**

[read_file for 'aviexa.py', 'demo/planted_bugs/bug_gradient_explosion.py', 'verify_demo.py'] Result:
<files>
<file><path>aviexa.py</path>
<content lines="1-473">
  1 | """
  2 | aviexa.py — Aviexa CLI entry point.
  3 | 
  4 | Commands:
  5 |   python aviexa.py health
  6 |   python aviexa.py api
  7 |   python aviexa.py demo gradient-explosion
  8 |   python aviexa.py demo healthy
  9 |   python aviexa.py demo shape-mismatch
 10 |   python aviexa.py report <session_id>
 11 | """
 12 | 
 13 | import sys
 14 | import os
 15 | import argparse
 16 | import json
 17 | import logging
 18 | from pathlib import Path
 19 | 
 20 | # ── Logging ──────────────────────────────────────────────────────────────────
 21 | logging.basicConfig(
 22 |     level=logging.WARNING,          # suppress INFO from sub-modules
 23 |     format="%(levelname)s: %(message)s",
 24 | )
 25 | _log = logging.getLogger("aviexa.cli")
 26 | 
 27 | 
 28 | # ── Internal client (TestClient or real HTTP) ─────────────────────────────────
 29 | 
 30 | def _get_client():
 31 |     """
 32 |     Try the live API on localhost:8765 first.
 33 |     Fall back to FastAPI TestClient (zero-dependency, no server needed).
 34 |     Returns (client, mode) where mode is 'http' or 'testclient'.
 35 |     """
 36 |     port = int(os.environ.get("AVIEXA_API_PORT", "8765"))
 37 |     try:
 38 |         import urllib.request
 39 |         urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
 40 |         # Live API is up — use a thin HTTP wrapper
 41 |         return _HttpClient(f"http://localhost:{port}"), "http"
 42 |     except Exception:
 43 |         from fastapi.testclient import TestClient
 44 |         from api.app import app
 45 |         return TestClient(app), "testclient"
 46 | 
 47 | 
 48 | class _HttpClient:
 49 |     """Thin wrapper so TestClient and HTTP share the same .get/.post interface."""
 50 |     def __init__(self, base_url: str):
 51 |         import urllib.request, urllib.error
 52 |         self._base = base_url
 53 |         self._req = urllib.request
 54 | 
 55 |     def get(self, path: str):
 56 |         import urllib.request
 57 |         url = self._base + path
 58 |         with urllib.request.urlopen(url) as r:
 59 |             return _Resp(r.read(), dict(r.headers))
 60 | 
 61 |     def post(self, path: str, json_body):
 62 |         import urllib.request, urllib.error
 63 |         import json as _json
 64 |         payload = _json.dumps(json_body).encode()
 65 |         req = urllib.request.Request(
 66 |             self._base + path, data=payload,
 67 |             headers={"Content-Type": "application/json"}, method="POST")
 68 |         with urllib.request.urlopen(req) as r:
 69 |             return _Resp(r.read(), dict(r.headers))
 70 | 
 71 | 
 72 | class _Resp:
 73 |     def __init__(self, content: bytes, headers: dict):
 74 |         self.content = content
 75 |         self.status_code = 200
 76 |         self.headers = {k.lower(): v for k, v in headers.items()}
 77 |     def json(self):
 78 |         return json.loads(self.content)
 79 | 
 80 | 
 81 | # ── Shared demo engine ────────────────────────────────────────────────────────
 82 | 
 83 | def _run_demo(
 84 |     scenario: str,
 85 |     telemetry_events: list,
 86 |     applied_fix: dict,
 87 |     *,
 88 |     quiet: bool = False,
 89 | ) -> dict:
 90 |     """
 91 |     Core demo engine used by all demo subcommands.
 92 | 
 93 |     Returns a result dict with session_id, anomalies, diagnoses, report_path.
 94 |     Raises SystemExit(1) on any hard failure.
 95 |     """
 96 |     client, mode = _get_client()
 97 |     if not quiet:
 98 |         print(f"\n{'='*60}")
 99 |         print(f"  Aviexa Demo: {scenario}")
100 |         print(f"  API mode   : {mode}")
101 |         print(f"{'='*60}")
102 | 
103 |     # 1. Start session
104 |     r = client.post("/session/start", json_body={"script_path": f"demo/{scenario}.py", "metadata": {"demo": True}})
105 |     _assert(r.status_code == 200, f"Failed to start session: {r.content}")
106 |     session_id = r.json()["session_id"]
107 |     if not quiet:
108 |         print(f"\n[1] Session started: {session_id}")
109 | 
110 |     # 2. Send telemetry
111 |     r = client.post(f"/session/{session_id}/telemetry", json_body=telemetry_events)
112 |     _assert(r.status_code == 200, f"Telemetry POST failed: {r.content}")
113 |     t = r.json()
114 |     received      = t.get("received", 0)
115 |     n_anomalies   = t.get("anomalies_detected", 0)
116 |     n_diagnoses   = t.get("diagnoses_generated", 0)
117 | 
118 |     if not quiet:
119 |         print(f"[2] Telemetry: {received} events sent")
120 |         print(f"    Anomalies detected  : {n_anomalies}")
121 |         print(f"    Bob diagnoses       : {n_diagnoses}")
122 | 
123 |     # 3. Fail fast if no anomaly/diagnosis (gradient-explosion scenario expects them)
124 |     if scenario != "healthy":
125 |         _assert(n_anomalies >= 1,
126 |                 f"No anomaly detected for '{scenario}'! Check threshold. Response: {t}")
127 |         _assert(n_diagnoses >= 1,
128 |                 f"No Bob diagnosis for '{scenario}'! Response: {t}")
129 | 
130 |     # 4. Fetch anomalies + diagnoses for summary
131 |     anomalies = client.get(f"/session/{session_id}/anomalies").json().get("anomalies", [])
132 |     diagnoses  = client.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])
133 | 
134 |     # 5. Record applied fix
135 |     r = client.post(f"/session/{session_id}/fixes/applied", json_body=applied_fix)
136 |     _assert(r.status_code == 200, f"Applied fix POST failed: {r.content}")
137 |     fix_id = r.json()["fix_id"]
138 |     if not quiet:
139 |         print(f"[3] Applied fix recorded: {fix_id[:8]}...")
140 | 
141 |     # 6. Generate PDF report
142 |     r = client.get(f"/session/{session_id}/report")
143 |     _assert(r.status_code == 200, "Report endpoint failed")
144 |     _assert(len(r.content) > 25_000,
145 |             f"PDF too small ({len(r.content)} bytes) — report is weak")
146 | 
147 |     # Save PDF to disk
148 |     report_dir = Path("aviexa-reports")
149 |     report_dir.mkdir(exist_ok=True)
150 |     report_path = report_dir / f"demo_{scenario}_{session_id[:8]}.pdf"
151 |     report_path.write_bytes(r.content)
152 | 
153 |     if not quiet:
154 |         print(f"[4] PDF report: {report_path}  ({len(r.content):,} bytes)")
155 | 
156 |     # 7. Print suggested fixes summary
157 |     if not quiet and diagnoses:
158 |         all_fixes = [fx for d in diagnoses for fx in d.get("fixes", [])]
159 |         if all_fixes:
160 |             print(f"\n--- Suggested Fixes ({len(all_fixes)}) ---")
161 |             for i, fx in enumerate(all_fixes, 1):
162 |                 print(f"  {i}. {fx.get('file_path','?')} L{fx.get('start_line','?')}"
163 |                       f"  risk={fx.get('risk_level','?')}")
164 |                 print(f"     {fx.get('explanation','')}")
165 | 
166 |     # 8. Final summary
167 |     if not quiet:
168 |         print(f"\n{'='*60}")
169 |         print(f"  DEMO COMPLETE")
170 |         print(f"  Session ID  : {session_id}")
171 |         print(f"  Events sent : {received}")
172 |         print(f"  Anomalies   : {n_anomalies}")
173 |         print(f"  Diagnoses   : {n_diagnoses}")
174 |         print(f"  Report      : {report_path}")
175 |         print(f"{'='*60}\n")
176 | 
177 |     return {
178 |         "session_id":   session_id,
179 |         "received":     received,
180 |         "anomalies":    n_anomalies,
181 |         "diagnoses":    n_diagnoses,
182 |         "report_path":  str(report_path),
183 |         "report_bytes": len(r.content),
184 |     }
185 | 
186 | 
187 | def _assert(cond: bool, msg: str):
188 |     if not cond:
189 |         print(f"\n[FAIL] {msg}", file=sys.stderr)
190 |         sys.exit(1)
191 | 
192 | 
193 | # ── Telemetry builders ────────────────────────────────────────────────────────
194 | 
195 | def _telemetry_gradient_explosion(session_id: str) -> list:
196 |     """5 backward events with a clear gradient explosion at step 3, plus 7 loss events."""
197 |     events = []
198 |     for step, gnorm in enumerate([1.1, 1.3, 250.0, 1.2, 1.0], start=1):
199 |         events.append({
200 |             "session_id": session_id,
201 |             "event_type": "backward",
202 |             "step": step,
203 |             "layer_name": "fc2.weight",
204 |             "gradient_norm": gnorm,
205 |             "gradient_is_none": False,
206 |             "has_nan": False,
207 |             "has_inf": False,
208 |         })
209 |     for step in range(1, 8):
210 |         events.append({
211 |             "session_id": session_id,
212 |             "event_type": "loss",
213 |             "step": step,
214 |             "loss_value": 2.4 - step * 0.05,
215 |         })
216 |     return events
217 | 
218 | 
219 | def _telemetry_healthy(session_id: str) -> list:
220 |     """Clean declining loss, stable gradient norms — no anomaly expected."""
221 |     events = []
222 |     for step in range(1, 16):
223 |         events.append({
224 |             "session_id": session_id,
225 |             "event_type": "backward",
226 |             "step": step,
227 |             "layer_name": "fc1.weight",
228 |             "gradient_norm": 0.5 + 0.02 * (15 - step),
229 |             "gradient_is_none": False,
230 |             "has_nan": False,
231 |             "has_inf": False,
232 |         })
233 |         events.append({
234 |             "session_id": session_id,
235 |             "event_type": "loss",
236 |             "step": step,
237 |             "loss_value": max(0.05, 2.0 - step * 0.12),
238 |         })
239 |     return events
240 | 
241 | 
242 | def _telemetry_shape_mismatch(session_id: str) -> list:
243 |     """Normal telemetry — shape mismatch anomaly added manually."""
244 |     events = []
245 |     for step in range(1, 6):
246 |         events.append({
247 |             "session_id": session_id,
248 |             "event_type": "backward",
249 |             "step": step,
250 |             "layer_name": "fc1.weight",
251 |             "gradient_norm": 1.0,
252 |             "gradient_is_none": False,
253 |             "has_nan": False,
254 |             "has_inf": False,
255 |         })
256 |         events.append({
257 |             "session_id": session_id,
258 |             "event_type": "loss",
259 |             "step": step,
260 |             "loss_value": 2.5 - step * 0.1,
261 |         })
262 |     # Trigger gradient explosion as a proxy (shape detector not yet in API layer)
263 |     events.append({
264 |         "session_id": session_id,
265 |         "event_type": "backward",
266 |         "step": 6,
267 |         "layer_name": "projection.weight",
268 |         "gradient_norm": 180.0,
269 |         "gradient_is_none": False,
270 |         "has_nan": False,
271 |         "has_inf": False,
272 |     })
273 |     return events
274 | 
275 | 
276 | # ── Applied-fix templates ────────────────────────────────────────────────────
277 | 
278 | _FIX_GRADIENT_EXPLOSION = {
279 |     "file_path": "demo/planted_bugs/bug_gradient_explosion.py",
280 |     "start_line": 18,
281 |     "end_line": 19,
282 |     "original_code": "optimizer = torch.optim.SGD(model.parameters(), lr=100.0)",
283 |     "replacement_code": (
284 |         "optimizer = torch.optim.SGD(model.parameters(), lr=0.001)\n"
285 |         "torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)"
286 |     ),
287 |     "explanation": "Reduce learning rate from 100.0 to 0.001 and add gradient clipping.",
288 |     "risk_level": "low",
289 | }
290 | 
291 | _FIX_HEALTHY = {
292 |     "file_path": "demo/scripts/train_mnist.py",
293 |     "start_line": 1,
294 |     "end_line": 1,
295 |     "original_code": "# no fix needed",
296 |     "replacement_code": "# no fix needed — baseline is healthy",
297 |     "explanation": "Training is healthy. No changes required.",
298 |     "risk_level": "low",
299 | }
300 | 
301 | _FIX_SHAPE_MISMATCH = {
302 |     "file_path": "demo/planted_bugs/bug_shape_mismatch.py",
303 |     "start_line": 12,
304 |     "end_line": 12,
305 |     "original_code": "self.fc = nn.Linear(256, 10)",
306 |     "replacement_code": "self.fc = nn.Linear(128, 10)",
307 |     "explanation": "Fix Linear input dimension: backbone outputs 128, not 256.",
308 |     "risk_level": "medium",
309 | }
310 | 
311 | 
312 | # ── CLI subcommands ───────────────────────────────────────────────────────────
313 | 
314 | def cmd_health(args):
315 |     client, mode = _get_client()
316 |     r = client.get("/health")
317 |     d = r.json()
318 |     print(f"Aviexa API health — mode: {mode}")
319 |     print(json.dumps(d, indent=2))
320 | 
321 | 
322 | def cmd_api(args):
323 |     """Start the Uvicorn dev server."""
324 |     import subprocess
325 |     port = int(os.environ.get("AVIEXA_API_PORT", "8765"))
326 |     print(f"Starting Aviexa API on http://0.0.0.0:{port} ...")
327 |     subprocess.run([
328 |         sys.executable, "-m", "uvicorn", "api.app:app",
329 |         "--host", "0.0.0.0", "--port", str(port), "--reload"
330 |     ])
331 | 
332 | 
333 | def cmd_demo(args):
334 |     scenario = args.scenario
335 | 
336 |     # Need session_id before building telemetry — obtain it first
337 |     client, _ = _get_client()
338 |     r = client.post("/session/start", json_body={
339 |         "script_path": f"demo/{scenario}.py", "metadata": {"demo": True}
340 |     })
341 |     _assert(r.status_code == 200, f"Could not start session: {r.content}")
342 |     session_id = r.json()["session_id"]
343 | 
344 |     if scenario == "gradient-explosion":
345 |         telemetry = _telemetry_gradient_explosion(session_id)
346 |         fix       = _FIX_GRADIENT_EXPLOSION
347 |     elif scenario == "healthy":
348 |         telemetry = _telemetry_healthy(session_id)
349 |         fix       = _FIX_HEALTHY
350 |     elif scenario == "shape-mismatch":
351 |         telemetry = _telemetry_shape_mismatch(session_id)
352 |         fix       = _FIX_SHAPE_MISMATCH
353 |     else:
354 |         print(f"Unknown scenario: {scenario}", file=sys.stderr)
355 |         sys.exit(1)
356 | 
357 |     fix["session_id"] = session_id
358 | 
359 |     # Re-use engine but skip the internal session start (already done above)
360 |     _run_demo_from_existing_session(
361 |         scenario=scenario,
362 |         session_id=session_id,
363 |         client=client,
364 |         telemetry_events=telemetry,
365 |         applied_fix=fix,
366 |     )
367 | 
368 | 
369 | def _run_demo_from_existing_session(scenario, session_id, client, telemetry_events, applied_fix):
370 |     """Like _run_demo but skips the session/start call."""
371 |     from pathlib import Path
372 | 
373 |     print(f"\n{'='*60}")
374 |     print(f"  Aviexa Demo: {scenario}")
375 |     print(f"{'='*60}")
376 |     print(f"\n[1] Session: {session_id}")
377 | 
378 |     r = client.post(f"/session/{session_id}/telemetry", json_body=telemetry_events)
379 |     _assert(r.status_code == 200, f"Telemetry failed: {r.content}")
380 |     t = r.json()
381 |     received    = t.get("received", 0)
382 |     n_anomalies = t.get("anomalies_detected", 0)
383 |     n_diagnoses = t.get("diagnoses_generated", 0)
384 | 
385 |     print(f"[2] Telemetry : {received} events sent")
386 |     print(f"    Anomalies : {n_anomalies}")
387 |     print(f"    Diagnoses : {n_diagnoses}")
388 | 
389 |     if scenario != "healthy":
390 |         _assert(n_anomalies >= 1, f"No anomaly for '{scenario}'! {t}")
391 |         _assert(n_diagnoses >= 1, f"No diagnosis for '{scenario}'! {t}")
392 | 
393 |     diagnoses = client.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])
394 | 
395 |     r = client.post(f"/session/{session_id}/fixes/applied", json_body=applied_fix)
396 |     _assert(r.status_code == 200, f"Applied fix failed: {r.content}")
397 |     fix_id = r.json()["fix_id"]
398 |     print(f"[3] Applied fix: {fix_id[:8]}...")
399 | 
400 |     r = client.get(f"/session/{session_id}/report")
401 |     _assert(r.status_code == 200, "Report endpoint failed")
402 |     _assert(len(r.content) > 25_000, f"PDF too small ({len(r.content)} bytes)")
403 | 
404 |     report_dir  = Path("aviexa-reports")
405 |     report_dir.mkdir(exist_ok=True)
406 |     report_path = report_dir / f"demo_{scenario}_{session_id[:8]}.pdf"
407 |     report_path.write_bytes(r.content)
408 |     print(f"[4] Report    : {report_path}  ({len(r.content):,} bytes)")
409 | 
410 |     if diagnoses:
411 |         all_fixes = [fx for d in diagnoses for fx in d.get("fixes", [])]
412 |         if all_fixes:
413 |             print(f"\n--- Suggested Fixes ({len(all_fixes)}) ---")
414 |             for i, fx in enumerate(all_fixes, 1):
415 |                 print(f"  {i}. {fx.get('file_path','?')} "
416 |                       f"L{fx.get('start_line','?')}  risk={fx.get('risk_level','?')}")
417 |                 print(f"     {fx.get('explanation','')}")
418 | 
419 |     print(f"\n{'='*60}")
420 |     print(f"  DEMO COMPLETE — {scenario}")
421 |     print(f"  Session  : {session_id}")
422 |     print(f"  Events   : {received}  |  Anomalies: {n_anomalies}  |  Diagnoses: {n_diagnoses}")
423 |     print(f"  Report   : {report_path}")
424 |     print(f"{'='*60}\n")
425 | 
426 | 
427 | def cmd_report(args):
428 |     client, mode = _get_client()
429 |     session_id = args.session_id
430 |     r = client.get(f"/session/{session_id}/report")
431 |     _assert(r.status_code == 200, "Report endpoint failed")
432 |     report_dir  = Path("aviexa-reports")
433 |     report_dir.mkdir(exist_ok=True)
434 |     out = report_dir / f"report_{session_id[:8]}.pdf"
435 |     out.write_bytes(r.content)
436 |     print(f"Report saved: {out}  ({len(r.content):,} bytes)")
437 | 
438 | 
439 | # ── Main ──────────────────────────────────────────────────────────────────────
440 | 
441 | def main():
442 |     parser = argparse.ArgumentParser(
443 |         prog="aviexa",
444 |         description="Aviexa — AI-powered ML training diagnostics CLI",
445 |     )
446 |     sub = parser.add_subparsers(dest="command", required=True)
447 | 
448 |     sub.add_parser("health", help="Check API health")
449 |     sub.add_parser("api",    help="Start the Aviexa API server")
450 | 
451 |     demo_p = sub.add_parser("demo", help="Run a demo scenario")
452 |     demo_p.add_argument(
453 |         "scenario",
454 |         choices=["gradient-explosion", "healthy", "shape-mismatch"],
455 |         help="Demo scenario to run",
456 |     )
457 | 
458 |     rep_p = sub.add_parser("report", help="Export PDF for a session")
459 |     rep_p.add_argument("session_id", help="Session ID to export")
460 | 
461 |     args = parser.parse_args()
462 | 
463 |     dispatch = {
464 |         "health": cmd_health,
465 |         "api":    cmd_api,
466 |         "demo":   cmd_demo,
467 |         "report": cmd_report,
468 |     }
469 |     dispatch[args.command](args)
470 | 
471 | 
472 | if __name__ == "__main__":
473 |     main()
</content>
</file>
<file><path>demo/planted_bugs/bug_gradient_explosion.py</path>
<content lines="1-52">
 1 | """
 2 | demo/planted_bugs/bug_gradient_explosion.py
 3 | Planted bug: learning rate = 100.0 (should be 0.001) + no gradient clipping.
 4 | Produces gradient norm spikes that Aviexa detects as GRADIENT_EXPLOSION.
 5 | 
 6 | THE BUG (line 18):  lr=100.0
 7 | THE FIX:            lr=0.001 + clip_grad_norm_(model.parameters(), max_norm=1.0)
 8 | """
 9 | 
10 | import torch
11 | import torch.nn as nn
12 | 
13 | torch.manual_seed(0)
14 | N = 128
15 | X = torch.randn(N, 16)
16 | Y = torch.randint(0, 2, (N,)).float()
17 | 
18 | 
19 | class BuggyNet(nn.Module):
20 |     def __init__(self):
21 |         super().__init__()
22 |         self.fc1 = nn.Linear(16, 64)
23 |         self.fc2 = nn.Linear(64, 1)
24 | 
25 |     def forward(self, x):
26 |         return self.fc2(torch.relu(self.fc1(x))).squeeze(1)
27 | 
28 | 
29 | model = BuggyNet()
30 | 
31 | # ── THE BUG: learning rate is 100,000× too high ──────────────────────────────
32 | optimizer = torch.optim.SGD(model.parameters(), lr=100.0)  # BUG: should be 0.001
33 | # ── MISSING: torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
34 | 
35 | criterion = nn.BCEWithLogitsLoss()
36 | BATCH = 32
37 | 
38 | print("bug_gradient_explosion.py: intentionally broken training (lr=100.0, no clipping)")
39 | for step in range(10):
40 |     idx  = torch.randint(0, N, (BATCH,))
41 |     xb, yb = X[idx], Y[idx]
42 |     optimizer.zero_grad()
43 |     loss = criterion(model(xb), yb)
44 |     loss.backward()
45 | 
46 |     gnorm = sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None) ** 0.5
47 |     print(f"  Step {step+1:2d}  loss={loss.item():.4f}  grad_norm={gnorm:.2f}")
48 | 
49 |     optimizer.step()
50 | 
51 | print("\nExpected: gradient explosion detected by Aviexa around step 1-3.")
52 | print("Fix: reduce lr to 0.001 and add clip_grad_norm_(model.parameters(), max_norm=1.0)")
</content>
</file>
<file><path>verify_demo.py</path>
<content lines="1-160">
  1 | """
  2 | verify_demo.py
  3 | Verification suite for the Aviexa demo CLI flow.
  4 | Checks: imports, CLI commands, full gradient-explosion demo flow.
  5 | Does NOT require IBM_BOB_API_KEY or internet/GPU.
  6 | """
  7 | 
  8 | import sys
  9 | import os
 10 | from pathlib import Path
 11 | 
 12 | print("=" * 60)
 13 | print("AVIEXA DEMO VERIFICATION")
 14 | print("=" * 60)
 15 | 
 16 | # ── 1. Imports ────────────────────────────────────────────────────────────────
 17 | print("\n1. Testing imports...")
 18 | try:
 19 |     import aviexa                                   # CLI module
 20 |     from fastapi.testclient import TestClient
 21 |     from api.app import app
 22 |     from reports.pdf_generator import AviexaPDFReportGenerator
 23 |     from anomaly.models import AnomalyType
 24 |     print("[OK] All imports successful")
 25 | except Exception as e:
 26 |     print(f"[FAIL] Import error: {e}")
 27 |     sys.exit(1)
 28 | 
 29 | # ── 2. CLI health command ─────────────────────────────────────────────────────
 30 | print("\n2. Testing CLI health command (TestClient)...")
 31 | try:
 32 |     client = TestClient(app)
 33 |     r = client.get("/health")
 34 |     assert r.status_code == 200
 35 |     d = r.json()
 36 |     assert d["status"] == "ok"
 37 |     print(f"[OK] Health check passed: {d}")
 38 | except Exception as e:
 39 |     print(f"[FAIL] Health check failed: {e}")
 40 |     sys.exit(1)
 41 | 
 42 | # ── 3. Demo engine: gradient-explosion ───────────────────────────────────────
 43 | print("\n3. Testing gradient-explosion demo engine...")
 44 | try:
 45 |     # Monkey-patch aviexa's _get_client to always return TestClient
 46 |     import importlib
 47 |     _orig_get_client = aviexa._get_client
 48 | 
 49 |     def _mock_get_client():
 50 |         return TestClient(app), "testclient"
 51 | 
 52 |     aviexa._get_client = _mock_get_client
 53 | 
 54 |     # Start session
 55 |     tc = TestClient(app)
 56 |     r = tc.post("/session/start", json={"script_path": "demo/gradient-explosion.py", "metadata": {"demo": True}})
 57 |     assert r.status_code == 200
 58 |     session_id = r.json()["session_id"]
 59 |     print(f"   Session started: {session_id[:8]}...")
 60 | 
 61 |     # 4. Send telemetry ────────────────────────────────────────────────────────
 62 |     print("\n4. Sending gradient-explosion telemetry...")
 63 |     telemetry = aviexa._telemetry_gradient_explosion(session_id)
 64 |     assert len(telemetry) >= 5, f"Expected >= 5 events, got {len(telemetry)}"
 65 |     r = tc.post(f"/session/{session_id}/telemetry", json=telemetry)
 66 |     assert r.status_code == 200, f"Telemetry failed: {r.text}"
 67 |     t = r.json()
 68 |     received    = t.get("received", 0)
 69 |     n_anomalies = t.get("anomalies_detected", 0)
 70 |     n_diagnoses = t.get("diagnoses_generated", 0)
 71 |     print(f"[OK] Events received     : {received}")
 72 | 
 73 |     # 5. Assert anomaly detected ───────────────────────────────────────────────
 74 |     print("\n5. Asserting anomaly detected...")
 75 |     assert n_anomalies >= 1, \
 76 |         f"[FAIL] No anomaly detected! Response: {t}"
 77 |     print(f"[OK] Anomalies detected  : {n_anomalies}")
 78 | 
 79 |     # 6. Assert Bob diagnosis generated ───────────────────────────────────────
 80 |     print("\n6. Asserting Bob diagnosis generated...")
 81 |     assert n_diagnoses >= 1, \
 82 |         f"[FAIL] No diagnosis generated! Response: {t}"
 83 |     print(f"[OK] Diagnoses generated : {n_diagnoses}")
 84 | 
 85 |     # Confirm via /anomalies and /diagnoses endpoints
 86 |     anomalies = tc.get(f"/session/{session_id}/anomalies").json().get("anomalies", [])
 87 |     diagnoses = tc.get(f"/session/{session_id}/diagnoses").json().get("diagnoses", [])
 88 |     assert len(anomalies) >= 1, f"[FAIL] /anomalies empty: {anomalies}"
 89 |     assert len(diagnoses) >= 1, f"[FAIL] /diagnoses empty: {diagnoses}"
 90 |     print(f"[OK] /anomalies endpoint : {len(anomalies)} anomaly")
 91 |     print(f"[OK] /diagnoses endpoint : {len(diagnoses)} diagnosis")
 92 | 
 93 |     # 7. Record applied fix ───────────────────────────────────────────────────
 94 |     print("\n7. Recording applied fix...")
 95 |     fix = dict(aviexa._FIX_GRADIENT_EXPLOSION)
 96 |     fix["session_id"] = session_id
 97 |     r = tc.post(f"/session/{session_id}/fixes/applied", json=fix)
 98 |     assert r.status_code == 200, f"[FAIL] Fix record failed: {r.text}"
 99 |     fix_id = r.json()["fix_id"]
100 |     applied_fixes = tc.get(f"/session/{session_id}/fixes/applied").json().get("applied_fixes", [])
101 |     assert len(applied_fixes) == 1
102 |     print(f"[OK] Applied fix recorded: {fix_id[:8]}...")
103 | 
104 |     # 8. Generate PDF report ───────────────────────────────────────────────────
105 |     print("\n8. Generating PDF report...")
106 |     r = tc.get(f"/session/{session_id}/report")
107 |     assert r.status_code == 200, f"[FAIL] Report endpoint: {r.text}"
108 |     assert r.headers.get("content-type") == "application/pdf"
109 |     pdf_bytes = len(r.content)
110 |     assert pdf_bytes > 25_000, \
111 |         f"[FAIL] PDF too small ({pdf_bytes} bytes) — report is likely empty"
112 | 
113 |     out_dir = Path("aviexa-reports")
114 |     out_dir.mkdir(exist_ok=True)
115 |     out_path = out_dir / f"verify_demo_{session_id[:8]}.pdf"
116 |     out_path.write_bytes(r.content)
117 |     print(f"[OK] PDF generated       : {out_path}  ({pdf_bytes:,} bytes)")
118 | 
119 |     # 9. No real IBM key required ─────────────────────────────────────────────
120 |     print("\n9. Confirming no IBM_BOB_API_KEY required...")
121 |     assert "IBM_BOB_API_KEY" not in os.environ or os.environ.get("IBM_BOB_API_KEY", "") == "", \
122 |         "IBM_BOB_API_KEY is set — test still passes but mock mode not confirmed"
123 |     # Actually passes either way; just confirm mock mode was used
124 |     health = tc.get("/health").json()
125 |     assert health.get("bob_mock") is True, \
126 |         f"Expected bob_mock=true but got: {health}"
127 |     print(f"[OK] Bob mock mode confirmed: {health}")
128 | 
129 |     # 10. No external downloads ────────────────────────────────────────────────
130 |     print("\n10. Confirming no external downloads needed...")
131 |     # The demo scripts use torch.randn synthetic data — no MNIST download
132 |     print("[OK] All demo scripts use synthetic tensors (no downloads)")
133 | 
134 |     # Restore original _get_client
135 |     aviexa._get_client = _orig_get_client
136 | 
137 | except Exception as e:
138 |     print(f"\n[FAIL] Demo verification failed: {e}")
139 |     import traceback
140 |     traceback.print_exc()
141 |     sys.exit(1)
142 | 
143 | # ── Session summary print check ───────────────────────────────────────────────
144 | print("\n11. Session summary printout...")
145 | print(f"[OK] session_id          : {session_id}")
146 | print(f"[OK] events_sent         : {received}")
147 | print(f"[OK] anomalies_detected  : {n_anomalies}")
148 | print(f"[OK] diagnoses_generated : {n_diagnoses}")
149 | print(f"[OK] report_path         : {out_path}")
150 | 
151 | # ── Final ─────────────────────────────────────────────────────────────────────
152 | print()
153 | print("=" * 60)
154 | print("AVIEXA DEMO VERIFICATION COMPLETE")
155 | print("=" * 60)
156 | print("[OK] All 11 checks passed")
157 | print()
158 | print("To run the full live demo:")
159 | print("  python aviexa.py demo gradient-explosion")
160 | print()
</content>
</file>
</files>
<environment_details>
# VSCode Visible Files
reports\pdf_generator.py

# VSCode Open Tabs
anomaly/models.py,.gitignore,anomaly/detectors/classifier.py,anomaly/detectors/gradient_detector.py,anomaly/detectors/loss_detector.py,anomaly/detectors/shape_detector.py,anomaly/detectors/__init__.py,anomaly/detectors/detector.py,verify_layer2.py,bob/models.py,bob/response_parser.py,bob/__init__.py,verify_layer3.py,api/app.py,api/__init__.py,bob/client.py,verify_layer4.py,reports/__init__.py,api/session_store.py,reports/chart_builder.py

# Current Time
Current time in ISO 8601 UTC format: 2026-05-16T15:49:00.633Z
User time zone: Asia/Calcutta, UTC+5:30

# Current Cost
$0.02

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**

# Current Mode
<slug>code</slug>
<name>💻 Code</name>
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

I'll implement a real PyTorch training demo path for Aviexa. Let me create a TODO list to track the implementation steps.

<update_todo_list>
<todos>
[ ] Create real PyTorch training function that captures actual telemetry
[ ] Add real-gradient-explosion scenario to aviexa.py CLI
[ ] Update verify_demo.py to test both synthetic and real demos
[ ] Test the implementation
</todos>
</update_todo_list>

---

**User:**

[update_todo_list] Result:
Todo list updated successfully.
<environment_details>
# VSCode Visible Files
reports\pdf_generator.py

# VSCode Open Tabs
anomaly/models.py,.gitignore,anomaly/detectors/classifier.py,anomaly/detectors/gradient_detector.py,anomaly/detectors/loss_detector.py,anomaly/detectors/shape_detector.py,anomaly/detectors/__init__.py,anomaly/detectors/detector.py,verify_layer2.py,bob/models.py,bob/response_parser.py,bob/__init__.py,verify_layer3.py,api/app.py,api/__init__.py,bob/client.py,verify_layer4.py,reports/__init__.py,api/session_store.py,reports/chart_builder.py

# Current Time
Current time in ISO 8601 UTC format: 2026-05-16T15:49:09.118Z
User time zone: Asia/Calcutta, UTC+5:30

# Current Cost
$0.06

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**

# Current Mode
<slug>code</slug>
<name>💻 Code</name>
====

REMINDERS

Below is your current list of reminders for this task. Keep them updated as you progress.

| # | Content | Status |
|---|---------|--------|
| 1 | Create real PyTorch training function that captures actual telemetry | Pending |
| 2 | Add real-gradient-explosion scenario to aviexa.py CLI | Pending |
| 3 | Update verify_demo.py to test both synthetic and real demos | Pending |
| 4 | Test the implementation | Pending |


IMPORTANT: When task status changes, remember to call the `update_todo_list` tool to update your progress.

</environment_details>

---

**Assistant:**

Now let me add the real PyTorch training function to aviexa.py. I'll insert it before the existing telemetry builders.

<apply_diff>
<path>aviexa.py</path>
<diff>
<<<<<<< SEARCH
:start_line:192
-------
# ── Telemetry builders ────────────────────────────────────────────────────────

def _telemetry_gradient_explosion(session_id: str) -> list:
=======
# ── Real PyTorch Training ─────────────────────────────────────────────────────

def _run_real_gradient_explosion_training(session_id: str) -> tuple[list, dict]:
    """
    Run a real tiny PyTorch model with intentionally bad learning rate.
    Returns (telemetry_events, training_stats).
    
    - Uses torch.manual_seed for reproducibility
    - Intentionally high LR (10.0) to trigger gradient explosion
    - Captures real loss and gradient norms from actual training
    - Runs 10 steps, takes ~2 seconds on CPU
    """
    import torch
    import torch.nn as nn
    
    # Seed for reproducibility
    torch.manual_seed(42)
    
    # Tiny model: 2-layer MLP
    class TinyNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(8, 16)
            self.fc2 = nn.Linear(16, 1)
        
        def forward(self, x):
            return self.fc2(torch.relu(self.fc1(x))).squeeze(1)
    
    model = TinyNet()
    
    # Intentionally bad learning rate to cause gradient explosion
    optimizer = torch.optim.SGD(model.parameters(), lr=10.0)  # 10,000x too high!
    criterion = nn.MSELoss()
    
    # Synthetic training data (no downloads needed)
    N = 64
    X = torch.randn(N, 8)
    Y = torch.randn(N)
    
    events = []
    max_grad_norm = 0.0
    final_loss = 0.0
    
    print("\n[Real Training] Running PyTorch gradient explosion demo...")
    print(f"[Real Training] Model: 2-layer MLP (8→16→1)")
    print(f"[Real Training] Learning rate: 10.0 (intentionally high)")
    print(f"[Real Training] Steps: 10")
    
    for step in range(1, 11):
        # Mini-batch
        batch_size = 16
        idx = torch.randint(0, N, (batch_size,))
        xb, yb = X[idx], Y[idx]
        
        # Forward pass
        optimizer.zero_grad()
        pred = model(xb)
        loss = criterion(pred, yb)
        
        # Backward pass
        loss.backward()
        
        # Capture real gradient norms per layer
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
                    "has_nan": bool(torch.isnan(param.grad).any()),
                    "has_inf": bool(torch.isinf(param.grad).any()),
                })
        
        # Capture loss
        loss_val = loss.item()
        final_loss = loss_val
        events.append({
            "session_id": session_id,
            "event_type": "loss",
            "step": step,
            "loss_value": loss_val,
        })
        
        print(f"[Real Training]   Step {step:2d}  loss={loss_val:.4f}  "
              f"max_grad={max([p.grad.norm().item() for p in model.parameters() if p.grad is not None]):.2f}")
        
        # Optimizer step
        optimizer.step()
    
    stats = {
        "max_grad_norm": max_grad_norm,
        "final_loss": final_loss,
        "total_events": len(events),
    }
    
    print(f"[Real Training] Complete! Max gradient norm: {max_grad_norm:.2f}")
    print(f"[Real Training] Total events captured: {len(events)}")
    
    return events, stats


# ── Telemetry builders ────────────────────────────────────────────────────────

def _telemetry_gradient_explosion(session_id: str) -> list:
>>>>>>> REPLACE
</diff>
</apply_diff>

