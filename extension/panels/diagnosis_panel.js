// extension/panels/diagnosis_panel.js
// Bob diagnosis WebView panel — hypotheses, code fixes, Apply Fix + Export buttons.

'use strict';

const vscode = require('vscode');
const path = require('path');

/**
 * Manages the Bob diagnosis WebView panel.
 * Shows anomaly details, top-3 hypotheses with confidence bars,
 * and code fix suggestions with Apply Fix / Export Report actions.
 */
class DiagnosisPanel {
  /** @type {DiagnosisPanel | undefined} */
  static current = undefined;
  static VIEW_TYPE = 'aviexa.diagnosisPanel';

  /** @param {vscode.WebviewPanel} panel @param {vscode.ExtensionContext} ctx */
  constructor(panel, ctx) {
    this._panel = panel;
    this._ctx = ctx;
    this._disposables = [];
    this._currentDiagnosis = null;

    this._panel.webview.html = this._buildHtml(null);

    // Handle messages coming back from the WebView (button clicks)
    this._panel.webview.onDidReceiveMessage(
      msg => this._handleWebViewMessage(msg),
      null,
      this._disposables
    );

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
  }

  /**
   * Create or reveal the diagnosis panel.
   * @param {vscode.ExtensionContext} ctx
   * @returns {DiagnosisPanel}
   */
  static createOrShow(ctx) {
    const column = vscode.ViewColumn.Three;

    if (DiagnosisPanel.current) {
      DiagnosisPanel.current._panel.reveal(column);
      return DiagnosisPanel.current;
    }

    const panel = vscode.window.createWebviewPanel(
      DiagnosisPanel.VIEW_TYPE,
      'Aviexa — Bob Diagnosis',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [],
      }
    );

    DiagnosisPanel.current = new DiagnosisPanel(panel, ctx);
    return DiagnosisPanel.current;
  }

  /**
   * Display a Bob diagnosis result.
   * @param {{ anomaly: Object, diagnosis: Object }} data
   */
  show(data) {
    this._currentDiagnosis = data;
    this._panel.webview.html = this._buildHtml(data);
    this._panel.reveal();
  }

  /**
   * @param {{ command: string, payload?: any }} msg
   */
  async _handleWebViewMessage(msg) {
    if (msg.command === 'applyFix') {
      await vscode.commands.executeCommand('aviexa.applyFix', msg.payload);
    } else if (msg.command === 'exportReport') {
      await vscode.commands.executeCommand('aviexa.exportReport', this._currentDiagnosis);
    }
  }

  dispose() {
    DiagnosisPanel.current = undefined;
    this._panel.dispose();
    this._disposables.forEach(d => d.dispose());
    this._disposables = [];
  }

  /** @param {{ anomaly: Object, diagnosis: Object } | null} data */
  _buildHtml(data) {
    const diagnosisJson = data ? JSON.stringify(data) : 'null';

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aviexa Bob Diagnosis</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, 'Segoe UI', sans-serif);
      background: var(--vscode-editor-background, #1e1e1e);
      color: var(--vscode-foreground, #cccccc);
      padding: 16px;
      font-size: 13px;
    }
    h1 { font-size: 15px; margin-bottom: 4px; color: var(--vscode-textLink-foreground, #4ec9b0); }
    h2 { font-size: 13px; margin: 14px 0 6px; text-transform: uppercase;
         letter-spacing: 0.08em; color: #888; }
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 11px; font-weight: 600; background: #2d4a3e; color: #4ec9b0;
      margin-bottom: 8px;
    }
    .summary {
      background: var(--vscode-editorWidget-background, #252526);
      border: 1px solid var(--vscode-widget-border, #454545);
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 14px;
      line-height: 1.5;
    }
    .hypothesis {
      background: var(--vscode-editorWidget-background, #252526);
      border: 1px solid var(--vscode-widget-border, #454545);
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 8px;
    }
    .hyp-title { font-weight: 600; margin-bottom: 4px; }
    .confidence-bar-track {
      height: 6px; background: #333; border-radius: 3px; margin: 6px 0;
    }
    .confidence-bar-fill {
      height: 100%; border-radius: 3px; background: #4ec9b0;
      transition: width 0.4s ease;
    }
    .conf-label { font-size: 11px; color: #888; }
    .explanation { font-size: 12px; color: #aaa; margin-top: 4px; line-height: 1.4; }
    .fix-card {
      background: #1a2a1a;
      border: 1px solid #2d4a3e;
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 8px;
    }
    .fix-file { font-size: 11px; color: #888; margin-bottom: 4px; }
    pre {
      background: #111;
      border-radius: 4px;
      padding: 8px;
      overflow-x: auto;
      font-size: 12px;
      line-height: 1.4;
      margin: 6px 0;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .del { color: #f14c4c; }
    .ins { color: #4ec9b0; }
    .actions { display: flex; gap: 8px; margin-top: 10px; }
    button {
      padding: 6px 14px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      font-family: inherit;
    }
    .btn-primary { background: #0e639c; color: #fff; }
    .btn-primary:hover { background: #1177bb; }
    .btn-secondary { background: #3a3a3a; color: #ccc; }
    .btn-secondary:hover { background: #4a4a4a; }
    .empty { color: #555; padding: 32px; text-align: center; }
  </style>
</head>
<body>
  <div id="root"></div>

  <script>
    const vscode = acquireVsCodeApi();
    const data = ${diagnosisJson};

    function render() {
      const root = document.getElementById('root');

      if (!data || !data.diagnosis) {
        root.innerHTML = '<p class="empty">No diagnosis available yet.<br>Anomalies will appear here automatically.</p>';
        return;
      }

      const { anomaly, diagnosis } = data;
      const topHyps = (diagnosis.hypotheses || []).slice(0, 3);
      const fixes   = (diagnosis.fixes || []).slice(0, 3);

      let html = '';

      // Header
      html += '<h1>Bob Diagnosis</h1>';
      if (anomaly) {
        html += '<span class="badge">' + escHtml(anomaly.anomaly_type) + '</span>';
        html += ' <span style="font-size:11px;color:#888">step ' + anomaly.step + ' &middot; confidence ' + (anomaly.confidence * 100).toFixed(0) + '%</span>';
      }

      // Summary
      html += '<h2>Summary</h2>';
      html += '<div class="summary">' + escHtml(diagnosis.summary || '—') + '</div>';

      // Hypotheses
      if (topHyps.length) {
        html += '<h2>Hypotheses</h2>';
        topHyps.forEach(h => {
          const pct = Math.round((h.confidence || 0) * 100);
          html += '<div class="hypothesis">';
          html += '<div class="hyp-title">' + escHtml(h.title) + '</div>';
          html += '<div class="confidence-bar-track"><div class="confidence-bar-fill" style="width:' + pct + '%"></div></div>';
          html += '<div class="conf-label">' + pct + '% confidence</div>';
          html += '<div class="explanation">' + escHtml(h.explanation) + '</div>';
          html += '</div>';
        });
      }

      // Fixes
      if (fixes.length) {
        html += '<h2>Suggested Fixes</h2>';
        fixes.forEach((fix, i) => {
          html += '<div class="fix-card">';
          html += '<div class="fix-file">' + escHtml(fix.file_path) + ' (lines ' + fix.start_line + '–' + fix.end_line + ')</div>';
          html += '<pre><span class="del">- ' + escHtml(fix.original_code || '') + '</span>\\n<span class="ins">+ ' + escHtml(fix.replacement_code || '') + '</span></pre>';
          html += '<div style="font-size:12px;color:#aaa;">' + escHtml(fix.explanation) + '</div>';
          html += '<div class="actions">';
          html += '<button class="btn-primary" onclick="applyFix(' + i + ')">Apply Fix</button>';
          html += '</div>';
          html += '</div>';
        });
      }

      // Export
      html += '<div class="actions" style="margin-top:16px;">';
      html += '<button class="btn-secondary" onclick="exportReport()">Export Report</button>';
      html += '</div>';

      root.innerHTML = html;
    }

    function applyFix(idx) {
      const fix = data.diagnosis.fixes[idx];
      vscode.postMessage({ command: 'applyFix', payload: fix });
    }

    function exportReport() {
      vscode.postMessage({ command: 'exportReport' });
    }

    function escHtml(str) {
      return String(str)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    render();
  </script>
</body>
</html>`;
  }
}

module.exports = { DiagnosisPanel };
