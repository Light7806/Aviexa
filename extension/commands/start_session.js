// extension/commands/start_session.js
// Handles the 'aviexa.startSession' VS Code command.

'use strict';

const vscode = require('vscode');
const https = require('https');
const http = require('http');

const API_BASE = 'http://localhost:8765';
const POLL_INTERVAL_MS = 500;

/**
 * Manages the polling loop for a session.
 * Writes telemetry updates to the MetricsPanel and anomaly alerts to DiagnosisPanel.
 */
class SessionPoller {
  /**
   * @param {string} sessionId
   * @param {import('../panels/metrics_panel').MetricsPanel} metricsPanel
   * @param {import('../panels/diagnosis_panel').DiagnosisPanel} diagnosisPanel
   */
  constructor(sessionId, metricsPanel, diagnosisPanel) {
    this.sessionId = sessionId;
    this.metricsPanel = metricsPanel;
    this.diagnosisPanel = diagnosisPanel;
    this._timer = null;
    this._lastAnomalyCount = 0;
    this._running = false;
  }

  start() {
    if (this._running) return;
    this._running = true;
    this._poll();
  }

  stop() {
    this._running = false;
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  }

  async _poll() {
    if (!this._running) return;

    try {
      const session = await apiGet(`/session/${this.sessionId}`);
      const telemetry = await apiGet(`/session/${this.sessionId}/telemetry?limit=1`);

      // Push latest metrics into the chart panel
      const lastEvent = (telemetry.events || []).slice(-1)[0];
      if (lastEvent) {
        this.metricsPanel.update({
          step: lastEvent.step,
          loss: lastEvent.loss_value,
          gradient_norm: lastEvent.gradient_norm,
          cpu_mb: lastEvent.cpu_allocated_mb,
          cuda_mb: lastEvent.cuda_allocated_mb,
        });
      }

      // Check for new anomalies
      const anomalyCount = session.anomaly_count || 0;
      if (anomalyCount > this._lastAnomalyCount) {
        this._lastAnomalyCount = anomalyCount;
        const anomaliesResp = await apiGet(`/session/${this.sessionId}/anomalies?limit=1`);
        const latestAnomaly = (anomaliesResp.anomalies || []).slice(-1)[0];
        if (latestAnomaly) {
          this.metricsPanel.showAnomaly(latestAnomaly);

          // Also fetch the latest diagnosis and show in DiagnosisPanel
          try {
            const diagResp = await apiGet(`/session/${this.sessionId}/diagnoses?limit=1`);
            const latestDiag = (diagResp.diagnoses || []).slice(-1)[0];
            if (latestDiag) {
              this.diagnosisPanel.show({ anomaly: latestAnomaly, diagnosis: latestDiag });
            }
          } catch (_) { /* diagnosis may not be ready yet */ }
        }
      }
    } catch (err) {
      // Non-fatal — backend may be starting up
    }

    if (this._running) {
      this._timer = setTimeout(() => this._poll(), POLL_INTERVAL_MS);
    }
  }
}

/**
 * Register the aviexa.startSession command.
 *
 * @param {vscode.ExtensionContext} ctx
 * @param {{ metricsPanel: any, diagnosisPanel: any, state: Object }} shared
 *        shared.state holds { sessionId, poller } across commands
 */
function register(ctx, shared) {
  return vscode.commands.registerCommand('aviexa.startSession', async () => {
    // 1. Prompt for training script path
    const scriptPath = await vscode.window.showInputBox({
      prompt: 'Path to your training script (optional)',
      placeHolder: 'e.g. train.py',
      value: shared.state.scriptPath || '',
    });

    // Allow empty — session works without a script path
    if (scriptPath === undefined) return; // user pressed Escape

    vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: 'Aviexa: Starting session…', cancellable: false },
      async () => {
        try {
          // 2. POST /session/start
          const body = { script_path: scriptPath || null, metadata: {} };
          const result = await apiPost('/session/start', body);
          const sessionId = result.session_id;

          // 3. Store session ID
          shared.state.sessionId = sessionId;
          shared.state.scriptPath = scriptPath;
          ctx.workspaceState.update('aviexa.sessionId', sessionId);

          // 4. Open or reveal both panels
          const metricsPanel = shared.metricsPanel.createOrShow(ctx);
          const diagnosisPanel = shared.diagnosisPanel.createOrShow(ctx);

          // 5. Start polling
          if (shared.state.poller) shared.state.poller.stop();
          shared.state.poller = new SessionPoller(sessionId, metricsPanel, diagnosisPanel);
          shared.state.poller.start();

          vscode.window.showInformationMessage(
            `Aviexa session started: ${sessionId.slice(0, 8)}…`
          );
        } catch (err) {
          vscode.window.showErrorMessage(`Aviexa: Failed to start session — ${err.message}`);
        }
      }
    );
  });
}

// ── HTTP helpers ────────────────────────────────────────────────────────────

/** @param {string} path @returns {Promise<any>} */
function apiGet(path) {
  return new Promise((resolve, reject) => {
    http.get(API_BASE + path, res => {
      let body = '';
      res.on('data', chunk => (body += chunk));
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { reject(new Error('Invalid JSON: ' + body.slice(0, 80))); }
      });
    }).on('error', reject);
  });
}

/** @param {string} path @param {Object} data @returns {Promise<any>} */
function apiPost(path, data) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(data);
    const url = new URL(API_BASE + path);
    const options = {
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    };
    const req = http.request(options, res => {
      let body = '';
      res.on('data', chunk => (body += chunk));
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { reject(new Error('Invalid JSON: ' + body.slice(0, 80))); }
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

module.exports = { register, SessionPoller, apiGet, apiPost };
