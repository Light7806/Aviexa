# Aviexa Architecture

Aviexa is a four-layer diagnostic system for PyTorch training runs.

## Layer 1: Training Interceptor

Ownership: `core/`, telemetry-emitting demo scripts, and `aviexa.py run`.

Responsibilities:

- capture loss values,
- capture gradient norms,
- capture tensor shape events,
- associate telemetry with a session id,
- keep the training loop lightweight.

Important files:

- `core/buffer/ring_buffer.py`
- `core/hooks/forward_hook.py`
- `core/hooks/backward_hook.py`
- `core/hooks/loss_hook.py`
- `demo/external_project/train_bad_lr.py`

## Layer 2: Anomaly Detection

Ownership: `anomaly/`.

Responsibilities:

- classify gradient explosion,
- classify vanishing gradients,
- classify loss divergence,
- classify loss plateau,
- classify shape mismatch,
- normalize raw telemetry into anomaly events.

Important files:

- `anomaly/models.py`
- `anomaly/detectors/gradient_detector.py`
- `anomaly/detectors/loss_detector.py`
- `anomaly/detectors/shape_detector.py`
- `anomaly/detectors/classifier.py`

## Layer 3: IBM Bob Reasoning

Ownership: `bob/`.

Responsibilities:

- build a structured prompt from anomaly and code context,
- constrain Bob output into a parseable JSON-like schema,
- parse hypotheses and code fixes,
- provide deterministic mock mode for public demos.

Important files:

- `bob/context_builder.py`
- `bob/prompt_templates.py`
- `bob/client.py`
- `bob/response_parser.py`
- `bob/models.py`

## Layer 4: Developer Surfaces

Ownership: `api/`, `extension/`, `reports/`, and CLI commands.

Responsibilities:

- expose sessions, telemetry, anomalies, diagnoses, fixes, and reports through FastAPI,
- provide CLI demos and external-script execution,
- generate charts and PDF reports,
- provide a VS Code extension proof of concept.

Important files:

- `api/app.py`
- `api/routes.py`
- `api/session_store.py`
- `reports/pdf_generator.py`
- `reports/chart_builder.py`
- `extension/src/extension.js`
- `extension/panels/metrics_panel.js`
- `extension/panels/diagnosis_panel.js`

## Runtime Flow

```text
Training script
  -> telemetry events
  -> Aviexa API session
  -> anomaly detector
  -> Bob context builder
  -> Bob client
  -> parsed diagnosis and fixes
  -> CLI/API/VS Code/PDF report
```

## API Flow

1. `POST /session/start` creates a session.
2. `POST /session/{id}/telemetry` ingests telemetry events.
3. The detector emits anomalies.
4. Bob receives diagnosis prompts for detected anomalies.
5. `GET /session/{id}/anomalies` returns detected anomalies.
6. `GET /session/{id}/diagnoses` returns Bob diagnoses.
7. `POST /session/{id}/fixes/applied` records applied fixes.
8. `GET /session/{id}/report` exports a PDF.

## Design Constraints

- The demo must run without external downloads.
- The demo must run without a private Bob API key.
- Generated reports must be large enough to prove real content, not empty stubs.
- Bob output must be structured enough to drive UI and patch workflows.
- The project must visibly demonstrate IBM Bob's role in the solution.
