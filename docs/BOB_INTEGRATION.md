# IBM Bob Integration

Aviexa uses IBM Bob as the reasoning engine for ML training anomalies. Aviexa does the instrumentation and signal classification; Bob receives the relevant context and returns ranked hypotheses plus code-level fixes.

## Why Bob Is Used

The hackathon challenge asks teams to show how IBM Bob helps builders work faster. Aviexa uses Bob for the part that benefits most from codebase reasoning:

- understanding the anomaly type in context,
- connecting telemetry signals to likely code causes,
- ranking root-cause hypotheses,
- proposing concrete patches,
- producing an exportable diagnosis trail.

## Integration Components

```text
bob/client.py             Bob client, mock mode, retries, fallback behavior
bob/context_builder.py    Builds the anomaly and code context packet
bob/prompt_templates.py   JSON-constrained prompt templates
bob/response_parser.py    Parses hypotheses and code fixes into typed models
bob/models.py             Prompt, response, hypothesis, and fix schemas
```

## Context Packet

The context builder prepares a prompt with:

- anomaly type and confidence,
- affected layer or event metadata,
- recent telemetry history,
- relevant file and code context when available,
- session metadata,
- expected structured response schema.

The goal is to avoid generic free-text prompting. Bob receives a narrow, high-signal debugging packet.

## Response Contract

Bob responses are parsed into:

- summary,
- ranked hypotheses,
- confidence values,
- evidence,
- affected files,
- code fixes,
- risk level,
- review requirement.

This lets Aviexa display diagnoses in the API, VS Code extension, CLI output, and PDF reports.

## Mock Mode

`BobClient` supports mock mode. Mock mode is used when `IBM_BOB_API_KEY` and `IBM_BOB_BASE_URL` are not configured.

This is deliberate:

- judges can run the demo without private credentials,
- CI and local verification remain deterministic,
- the rest of the Aviexa pipeline can be tested offline,
- the Bob integration boundary is still visible in code.

## Real Bob Configuration

Set these environment variables before running the API or CLI:

```powershell
$env:IBM_BOB_API_KEY="your-key"
$env:IBM_BOB_BASE_URL="https://..."
$env:IBM_BOB_MODEL="bob-enterprise-v1"
```

Then run:

```powershell
python aviexa.py health
python aviexa.py demo real-gradient-explosion
```

Current note: `_call_api()` in `bob/client.py` is intentionally isolated as the real network boundary. The hackathon demo defaults to mock mode because the public judge environment may not have access to team credentials.

## Bob Proof for Submission

For the final hackathon submission, include:

- the public repository containing the `bob/` integration code,
- generated Aviexa PDF reports from `aviexa-reports/`,
- the official exported IBM Bob report from the IBM Bob tool,
- video footage showing Bob diagnosis/fix output in the Aviexa workflow.
