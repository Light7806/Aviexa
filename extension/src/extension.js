// extension/src/extension.js
// Aviexa VS Code extension — entry point.
// Registers commands, manages panels, and connects to the FastAPI backend.

'use strict';

const vscode = require('vscode');
const http = require('http');
const { MetricsPanel } = require('../panels/metrics_panel');
const { DiagnosisPanel } = require('../panels/diagnosis_panel');
const { register: registerStartSession } = require('../commands/start_session');
const { register: registerApplyFix } = require('../commands/apply_fix');

/**
 * Shared mutable state across commands and panels.
 * Kept here (extension host process) rather than WebView to avoid serialisation issues.
 * @type {{ sessionId: string|null, scriptPath: string|null, poller: any, appliedFixes: number, apiUrl: string }}
 */
const state = {
  sessionId: null,
  scriptPath: null,
  poller: null,
  appliedFixes: 0,
  apiUrl: 'http://localhost:8765',
};

/**
 * Called by VS Code when the extension is activated.
 * Activation event: onCommand:aviexa.startSession  (see package.json)
 *
 * @param {vscode.ExtensionContext} ctx
 */
function activate(ctx) {
  // Shared references given to commands so they can open / update panels
  const shared = {
    metricsPanel: MetricsPanel,
    diagnosisPanel: DiagnosisPanel,
    state,
  };

  // Register commands
  ctx.subscriptions.push(registerStartSession(ctx, shared));
  ctx.subscriptions.push(registerApplyFix(ctx, shared));

  ctx.subscriptions.push(
    vscode.commands.registerCommand('aviexa.inspectWorkspace', async () => {
      const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!folder) {
        vscode.window.showWarningMessage('Aviexa: Open a folder first.');
        return;
      }

      const port = vscode.workspace.getConfiguration('aviexa').get('apiPort', 8765);
      const url = `http://127.0.0.1:${port}/inspect?path=${encodeURIComponent(folder)}`;

      try {
        const data = await getJson(url);
        const high = data.findings.filter((f) => f.severity === 'high').length;
        const medium = data.findings.filter((f) => f.severity === 'medium').length;
        const panel = vscode.window.createWebviewPanel(
          'aviexaInspection',
          'Aviexa Workspace Inspection',
          vscode.ViewColumn.Beside,
          {}
        );
        panel.webview.html = renderInspectionHtml(data);
        vscode.window.showInformationMessage(
          `Aviexa: ${data.findings.length} ML finding(s): ${high} high, ${medium} medium.`
        );
      } catch (err) {
        vscode.window.showErrorMessage(`Aviexa: Inspection failed. Start backend with "python aviexa.py api". ${err.message}`);
      }
    })
  );

  // Register stop command (inline — simple enough to not need its own file)
  ctx.subscriptions.push(
    vscode.commands.registerCommand('aviexa.stopSession', () => {
      if (state.poller) {
        state.poller.stop();
        state.poller = null;
      }
      vscode.window.showInformationMessage('Aviexa: Session monitoring stopped.');
    })
  );

  // Register show-metrics command (reveals panel without starting a new session)
  ctx.subscriptions.push(
    vscode.commands.registerCommand('aviexa.showMetrics', () => {
      MetricsPanel.createOrShow(ctx);
    })
  );

  // Register show-diagnosis command
  ctx.subscriptions.push(
    vscode.commands.registerCommand('aviexa.showDiagnosis', () => {
      DiagnosisPanel.createOrShow(ctx);
    })
  );

  // Register export-report command
  ctx.subscriptions.push(
    vscode.commands.registerCommand('aviexa.exportReport', async () => {
      if (!state.sessionId) {
        vscode.window.showWarningMessage('Aviexa: No active session to export report for.');
        return;
      }

      const apiUrl = vscode.workspace.getConfiguration('aviexa').get('apiUrl', 'http://localhost:8765');
      const reportUrl = `${apiUrl}/session/${state.sessionId}/report`;

      try {
        // Open the report URL in external browser
        await vscode.env.openExternal(vscode.Uri.parse(reportUrl));
        vscode.window.showInformationMessage('Aviexa: Opening PDF report in browser...');
      } catch (err) {
        vscode.window.showErrorMessage(`Aviexa: Failed to open report — ${err.message}`);
      }
    })
  );

  // Restore previous session if one was active before the window was closed
  const savedSessionId = ctx.workspaceState.get('aviexa.sessionId');
  if (savedSessionId) {
    state.sessionId = savedSessionId;
  }

  console.log('Aviexa extension activated');
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(body || `HTTP ${res.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(err);
        }
      });
    }).on('error', reject);
  });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderInspectionHtml(data) {
  const findings = data.findings.map((finding) => `
    <article class="finding ${escapeHtml(finding.severity)}">
      <strong>${escapeHtml(finding.severity.toUpperCase())} - ${escapeHtml(finding.id)}</strong>
      <code>${escapeHtml(finding.file)}:${finding.line}</code>
      <p>${escapeHtml(finding.message)}</p>
      <p><b>Fix:</b> ${escapeHtml(finding.fix)}</p>
    </article>
  `).join('');

  return `<!doctype html>
  <html>
  <head>
    <style>
      body { font-family: var(--vscode-font-family); padding: 18px; color: var(--vscode-foreground); }
      .summary, .finding { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 12px; margin: 10px 0; }
      .high strong { color: #f97316; }
      .medium strong { color: #22c55e; }
      code { display: block; margin: 6px 0; }
    </style>
  </head>
  <body>
    <h1>Aviexa Workspace Inspection</h1>
    <section class="summary">
      <p><b>Project:</b> ${escapeHtml(data.project)}</p>
      <p><b>Python files:</b> ${data.python_files}</p>
      <p><b>Findings:</b> ${data.findings.length}</p>
    </section>
    ${findings || '<p>No common ML risks found.</p>'}
  </body>
  </html>`;
}

/**
 * Called by VS Code when the extension is deactivated (window close / reload).
 */
function deactivate() {
  if (state.poller) {
    state.poller.stop();
    state.poller = null;
  }
  console.log('Aviexa extension deactivated');
}

module.exports = { activate, deactivate };
