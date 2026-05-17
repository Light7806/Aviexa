// extension/panels/metrics_panel.js
// Live metrics WebView panel — loss curve, gradient norms, memory, anomaly alerts.

'use strict';

const vscode = require('vscode');

/**
 * Manages the live metrics WebView panel.
 * Receives telemetry data from extension.js via postMessage and renders charts.
 */
class MetricsPanel {
  /** @type {MetricsPanel | undefined} */
  static current = undefined;
  static VIEW_TYPE = 'aviexa.metricsPanel';

  /** @param {vscode.WebviewPanel} panel @param {vscode.ExtensionContext} ctx */
  constructor(panel, ctx) {
    this._panel = panel;
    this._ctx = ctx;
    this._disposables = [];

    this._panel.webview.html = this._buildHtml();

    // Clean up when the panel is closed by the user
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
  }

  /**
   * Create or reveal the metrics panel.
   * @param {vscode.ExtensionContext} ctx
   * @returns {MetricsPanel}
   */
  static createOrShow(ctx) {
    const column = vscode.ViewColumn.Two;

    if (MetricsPanel.current) {
      MetricsPanel.current._panel.reveal(column);
      return MetricsPanel.current;
    }

    const panel = vscode.window.createWebviewPanel(
      MetricsPanel.VIEW_TYPE,
      'Aviexa — Live Metrics',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [],
      }
    );

    MetricsPanel.current = new MetricsPanel(panel, ctx);
    return MetricsPanel.current;
  }

  /**
   * Push a telemetry update into the WebView.
   * @param {{ loss?: number[], gradients?: Object, memory?: Object, anomaly?: Object }} data
   */
  update(data) {
    if (!this._panel) return;
    this._panel.webview.postMessage({ type: 'update', payload: data });
  }

  /**
   * Push a new anomaly alert banner into the WebView.
   * @param {Object} anomaly  AnomalyEvent payload
   */
  showAnomaly(anomaly) {
    if (!this._panel) return;
    this._panel.webview.postMessage({ type: 'anomaly', payload: anomaly });
  }

  dispose() {
    MetricsPanel.current = undefined;
    this._panel.dispose();
    this._disposables.forEach(d => d.dispose());
    this._disposables = [];
  }

  _buildHtml() {
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aviexa Live Metrics</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, 'Segoe UI', sans-serif);
      background: var(--vscode-editor-background, #1e1e1e);
      color: var(--vscode-foreground, #cccccc);
      padding: 16px;
    }
    h2 { font-size: 14px; margin-bottom: 8px; color: var(--vscode-textLink-foreground, #4ec9b0); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card {
      background: var(--vscode-editorWidget-background, #252526);
      border: 1px solid var(--vscode-widget-border, #454545);
      border-radius: 6px;
      padding: 12px;
    }
    canvas { max-height: 180px; }
    #anomaly-banner {
      display: none;
      margin-bottom: 16px;
      padding: 10px 14px;
      border-radius: 6px;
      background: #5a1a1a;
      border-left: 4px solid #f14c4c;
      font-size: 13px;
    }
    #anomaly-banner.visible { display: block; }
    #anomaly-banner strong { color: #f48771; }
    .stat-row { display: flex; justify-content: space-between; font-size: 12px; margin-top: 4px; }
    .stat-val { font-weight: 600; color: var(--vscode-textLink-foreground, #4ec9b0); }
  </style>
</head>
<body>
  <div id="anomaly-banner">
    <strong>⚠ Anomaly Detected: </strong><span id="anomaly-desc"></span>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Loss Curve</h2>
      <canvas id="loss-chart"></canvas>
    </div>
    <div class="card">
      <h2>Gradient Norms</h2>
      <canvas id="grad-chart"></canvas>
    </div>
    <div class="card">
      <h2>Memory Usage</h2>
      <canvas id="mem-chart"></canvas>
    </div>
    <div class="card">
      <h2>Session Stats</h2>
      <div class="stat-row"><span>Step</span><span class="stat-val" id="stat-step">—</span></div>
      <div class="stat-row"><span>Last Loss</span><span class="stat-val" id="stat-loss">—</span></div>
      <div class="stat-row"><span>Anomalies</span><span class="stat-val" id="stat-anomalies">0</span></div>
      <div class="stat-row"><span>CPU MB</span><span class="stat-val" id="stat-cpu">—</span></div>
      <div class="stat-row"><span>CUDA MB</span><span class="stat-val" id="stat-cuda">—</span></div>
    </div>
  </div>

  <script>
    const MAX_POINTS = 100;

    function makeChart(id, label, color) {
      const ctx = document.getElementById(id).getContext('2d');
      return new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{ label, data: [], borderColor: color, backgroundColor: color + '22',
                        borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true }]
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#888', maxTicksLimit: 5 }, grid: { color: '#333' } },
            y: { ticks: { color: '#888' }, grid: { color: '#333' } }
          }
        }
      });
    }

    function pushPoint(chart, x, y) {
      chart.data.labels.push(x);
      chart.data.datasets[0].data.push(y);
      if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
      }
      chart.update('none');
    }

    const lossChart = makeChart('loss-chart', 'Loss', '#4ec9b0');
    const gradChart = makeChart('grad-chart', 'Grad Norm', '#c792ea');
    const memChart  = makeChart('mem-chart',  'CPU MB',    '#82aaff');

    let anomalyCount = 0;

    window.addEventListener('message', ({ data: msg }) => {
      if (msg.type === 'update') {
        const p = msg.payload;
        if (p.step !== undefined) {
          document.getElementById('stat-step').textContent = p.step;
          if (p.loss != null) {
            pushPoint(lossChart, p.step, p.loss);
            document.getElementById('stat-loss').textContent = p.loss.toFixed(4);
          }
          if (p.gradient_norm != null) pushPoint(gradChart, p.step, p.gradient_norm);
          if (p.cpu_mb != null) {
            pushPoint(memChart, p.step, p.cpu_mb);
            document.getElementById('stat-cpu').textContent = p.cpu_mb.toFixed(1) + ' MB';
          }
          if (p.cuda_mb != null) {
            document.getElementById('stat-cuda').textContent = p.cuda_mb.toFixed(1) + ' MB';
          }
        }
      } else if (msg.type === 'anomaly') {
        anomalyCount++;
        document.getElementById('stat-anomalies').textContent = anomalyCount;
        const banner = document.getElementById('anomaly-banner');
        document.getElementById('anomaly-desc').textContent =
          msg.payload.anomaly_type + ' at step ' + msg.payload.step;
        banner.classList.add('visible');
        setTimeout(() => banner.classList.remove('visible'), 8000);
      }
    });
  </script>
</body>
</html>`;
  }
}

module.exports = { MetricsPanel };
