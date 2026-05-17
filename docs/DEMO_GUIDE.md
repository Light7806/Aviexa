# Aviexa Demo Guide

This guide is the recommended judge walkthrough for the hackathon demo.

## Demo Goal

Show that Aviexa can:

1. observe a PyTorch training run,
2. detect a real training anomaly,
3. route structured context to IBM Bob,
4. return a diagnosis and suggested fix,
5. export a report proving the workflow.

## Fast Demo: Synthetic Gradient Explosion

Use this when time is short.

```powershell
python aviexa.py demo gradient-explosion
```

Expected result:

- Aviexa starts a session.
- Synthetic backward and loss telemetry is sent.
- A gradient anomaly is detected.
- Bob returns ranked hypotheses and suggested fixes.
- A PDF is saved under `aviexa-reports/`.

Talking point: this proves the full API, detector, Bob parsing, fix recording, and PDF reporting path without relying on a GPU or internet access.

## Strong Demo: Real PyTorch Gradient Explosion

Use this as the primary technical demo.

```powershell
python aviexa.py demo real-gradient-explosion
```

Expected result:

- Aviexa runs an actual PyTorch training loop.
- The learning rate is intentionally unstable.
- Loss and gradient values diverge.
- Aviexa classifies one or more training anomalies.
- Bob produces diagnosis objects and fixes.
- A PDF report is exported.

Talking point: this is not a static mock. The telemetry comes from a real PyTorch run.

## Shape Mismatch Demo

```powershell
python aviexa.py demo shape-mismatch
```

Expected result:

- A shape event with `is_mismatch=True` is sent.
- Aviexa detects a shape mismatch anomaly.
- Bob suggests a model dimension fix.
- A PDF report is exported.

Talking point: Aviexa handles both numeric training instability and structural model errors.

## External Script Demo

```powershell
python aviexa.py run demo\external_project\train_bad_lr.py --report --scenario-name run_train_bad_lr
```

Expected result:

- Aviexa launches the external script as a subprocess.
- The script emits `AVIEXA_TELEMETRY: {...}` lines.
- Aviexa captures those events, detects an anomaly, generates Bob diagnoses, and writes a PDF.

Talking point: existing projects do not need to become Aviexa apps. They can emit telemetry and let Aviexa process it.

## Verification Command

```powershell
python verify_demo.py
```

This verifies:

- import health
- CLI health command
- API health
- synthetic gradient explosion
- real PyTorch gradient explosion
- shape mismatch
- external training script execution
- PDF report generation
- Bob mock-mode diagnosis path

## Suggested 2-Minute Video Script

1. Open with the problem: ML training failures waste GPU hours because raw stack traces do not explain training dynamics.
2. Run `python aviexa.py demo real-gradient-explosion`.
3. Point out telemetry count, anomaly count, diagnosis count, and report path.
4. Open the generated PDF report.
5. Explain that IBM Bob receives structured anomaly context and returns ranked root-cause hypotheses and fixes.
6. Run `python aviexa.py demo shape-mismatch` to show a second anomaly class.
7. Close with the developer value: faster diagnosis, less guessing, exportable proof of AI-assisted debugging.
