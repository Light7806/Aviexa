const state = {
  sessionId: null,
  lastFix: null,
  fixRecorded: false,
};

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch {}
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function setStatus(id, ok, text) {
  const el = $(id);
  el.className = `status-pill ${ok ? "ok" : "bad"}`;
  el.querySelector("span:last-child").textContent = text;
}

function flash(type, message) {
  const el = $("launch-result");
  el.className = `notice ${type}`;
  el.textContent = message;
}

function clearFlash() {
  $("launch-result").className = "notice hidden";
}

function showResults() {
  $("results-area").classList.remove("hidden");
  $("results-area").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setLoading(show, msg = "Running demo…", sub = "This takes a few seconds") {
  $("loading-overlay").classList.toggle("hidden", !show);
  $("loading-msg").textContent = msg;
  $("loading-sub").textContent = sub;
}

function updateMetrics(data) {
  $("m-files").textContent = data.python_files || 0;
  $("m-findings").textContent = (data.findings || []).length;
  $("m-anomalies").textContent = (data.anomalies || []).length;
  $("m-diagnoses").textContent = (data.diagnoses || []).length;
}

async function checkHealth() {
  try {
    const health = await api("/health");
    setStatus("chip-backend", true, health.bob_mock ? "Backend online · Bob mock" : "Backend online · Bob live");
  } catch {
    setStatus("chip-backend", false, "Backend offline");
  }
}

async function checkVSCode() {
  const btn = $("check-vscode-btn");
  btn.disabled = true;
  btn.textContent = "Checking…";
  try {
    const result = await api("/vscode/status");
    if (result.available) {
      setStatus("chip-vscode", true, `VS Code ready ${result.version || ""}`.trim());
      flash("success", "VS Code CLI is available.");
    } else {
      setStatus("chip-vscode", false, "VS Code not found");
      flash("error", result.message);
    }
  } catch (error) {
    setStatus("chip-vscode", false, "VS Code check failed");
    flash("error", error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Check VS Code";
  }
}

async function openVSCode() {
  const folderPath = $("folder-path").value.trim() || "demo\\external_project";
  const btn = $("open-vscode-btn");
  btn.disabled = true;
  btn.textContent = "Opening…";
  try {
    const result = await api("/vscode/open", {
      method: "POST",
      body: JSON.stringify({ path: folderPath }),
    });
    flash(result.ok ? "success" : "error", result.message);
  } catch (error) {
    flash("error", error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Open in VS Code";
  }
}

async function inspectFolder() {
  const folderPath = $("folder-path").value.trim() || "demo\\external_project";
  const btn = $("inspect-btn");
  btn.disabled = true;
  btn.textContent = "Inspecting…";
  try {
    let data;
    try {
      data = await api(`/inspect?path=${encodeURIComponent(folderPath)}`);
    } catch (error) {
      if (folderPath.replaceAll("/", "\\").toLowerCase() !== "demo\\external_project") {
        throw error;
      }
      data = await api("/demo/inspect");
    }
    renderInspection(data);
    updateMetrics({ ...data, anomalies: [], diagnoses: [] });
    $("diagnosis-output").className = "panel-body empty";
    $("diagnosis-output").textContent = "Run Demo to generate Bob diagnosis and a report.";
    $("report-output").className = "panel-body empty";
    $("report-output").textContent = "The report link appears after Run Demo.";
    clearFlash();
    showResults();
  } catch (error) {
    flash("error", `Inspection failed: ${error.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Inspect Folder";
  }
}

async function runDemo() {
  const folderPath = $("folder-path").value.trim() || "demo\\external_project";
  const btn = $("golden-demo-btn");
  btn.disabled = true;
  btn.textContent = "Running…";
  setLoading(true, "Running Aviexa demo…", "Inspecting code, detecting issue, asking Bob, building PDF");
  try {
    let data;
    try {
      data = await api("/demo/golden", {
        method: "POST",
        body: JSON.stringify({ project_path: folderPath }),
      });
    } catch (error) {
      const inspection = await api("/demo/inspect");
      const demo = await api("/demo/run/gradient-explosion", { method: "POST" });
      data = {
        ...demo,
        project_path: inspection.project,
        python_files: inspection.python_files,
        findings: inspection.findings || [],
        inventory: inspection.inventory || {},
      };
    }
    state.sessionId = data.session_id;
    state.lastFix = (data.applied_fixes || [])[0] || null;
    state.fixRecorded = false;

    renderInspection(data);
    renderDiagnosis(data);
    renderReport(data);
    updateMetrics(data);
    clearFlash();
    showResults();
  } catch (error) {
    flash("error", `Demo failed: ${error.message}`);
  } finally {
    setLoading(false);
    btn.disabled = false;
    btn.textContent = "Run Demo";
  }
}

function renderInspection(data) {
  const findings = data.findings || [];
  if (!findings.length) {
    $("inspect-output").className = "panel-body empty";
    $("inspect-output").textContent = `No risky patterns found in ${data.project || data.project_path || "project"}.`;
    return;
  }

  $("inspect-output").className = "panel-body";
  $("inspect-output").innerHTML = `
    <p class="context-line">${esc(data.project || data.project_path)} · ${data.python_files || 0} Python file(s)</p>
    ${findings.map((f) => `
      <div class="finding-card">
        <strong>${esc(f.severity).toUpperCase()} · ${esc(String(f.id).replaceAll("-", " "))}</strong>
        <code>${esc(f.file)}:${esc(f.line)}</code>
        <p>${esc(f.message)}</p>
        <small>${esc(f.fix)}</small>
      </div>
    `).join("")}
  `;
}

function renderDiagnosis(data) {
  const anomalies = data.anomalies || [];
  const diagnoses = data.diagnoses || [];
  const fix = (data.applied_fixes || [])[0];

  $("diagnosis-output").className = "panel-body";
  $("diagnosis-output").innerHTML = `
    ${anomalies.map((a) => `
      <div class="diagnosis-card warning">
        <span>Detected problem</span>
        <strong>${esc(formatType(a.anomaly_type || "training_issue"))}</strong>
        <p>${esc(a.description || "Aviexa detected unstable training behavior.")}</p>
      </div>
    `).join("")}
    ${diagnoses.map((d) => `
      <div class="diagnosis-card bob">
        <span>IBM Bob diagnosis</span>
        <strong>${esc(d.summary || "Training instability diagnosis generated")}</strong>
        <p>${esc(d.explanation || d.root_cause || "Bob generated a structured root-cause hypothesis and fix.")}</p>
      </div>
    `).join("")}
    ${fix ? `
      <div class="fix-card">
        <span>Suggested fix</span>
        <pre>${esc(fix.replacement_code)}</pre>
        <p>${esc(fix.explanation)}</p>
        <button id="record-fix-btn" class="button primary small" type="button">Record Fix for PDF</button>
        <small id="record-fix-note">This records the suggested fix in the PDF evidence trail.</small>
      </div>
    ` : ""}
  `;

  const btn = $("record-fix-btn");
  if (btn) btn.addEventListener("click", recordFix);
}

async function recordFix() {
  if (!state.sessionId || !state.lastFix || state.fixRecorded) return;
  const btn = $("record-fix-btn");
  const note = $("record-fix-note");
  btn.disabled = true;
  btn.textContent = "Recording…";

  const f = state.lastFix;
  try {
    await api(`/session/${state.sessionId}/fixes/applied`, {
      method: "POST",
      body: JSON.stringify({
        file_path: f.file_path,
        start_line: f.start_line,
        end_line: f.end_line,
        original_code: f.original_code,
        replacement_code: f.replacement_code,
        explanation: f.explanation,
        risk_level: f.risk_level || "low",
        status: "applied",
        metadata: { source: "web-demo-confirmation" },
      }),
    });
    state.fixRecorded = true;
    btn.textContent = "Fix Recorded";
    note.textContent = "Fix recorded. Export the PDF to show the report trail.";
  } catch (error) {
    btn.disabled = false;
    btn.textContent = "Record Fix for PDF";
    note.textContent = error.message;
  }
}

function renderReport(data) {
  $("report-output").className = "panel-body";
  $("report-output").innerHTML = `
    <div class="report-row">
      <div>
        <strong>Aviexa diagnostic report</strong>
        <p>Session ${esc(data.session_id)}</p>
      </div>
      <a class="button primary" href="${esc(data.report_url)}" target="_blank" rel="noopener">Export PDF</a>
    </div>
  `;
}

function formatType(type) {
  return String(type).replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

window.addEventListener("DOMContentLoaded", () => {
  $("check-vscode-btn").addEventListener("click", checkVSCode);
  $("open-vscode-btn").addEventListener("click", openVSCode);
  $("inspect-btn").addEventListener("click", inspectFolder);
  $("golden-demo-btn").addEventListener("click", runDemo);
  $("folder-path").addEventListener("keydown", (event) => {
    if (event.key === "Enter") inspectFolder();
  });
  checkHealth();
});
