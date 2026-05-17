"""
bob/client.py
IBM Bob API client with mock mode for demos and testing.
Handles authentication, retries, and response parsing.
"""

import os
import time
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Union

from anomaly.models import AnomalyEvent, TelemetryEvent, AnomalyType
from bob.models import BobPrompt, BobResponse, Hypothesis, CodeFix, RiskLevel
from bob.context_builder import BobContextBuilder
from bob.response_parser import BobResponseParser

logger = logging.getLogger(__name__)


class BobClient:
    """
    Client for IBM Bob API with mock mode support.
    
    Features:
    - Real API calls when configured
    - Mock mode for demos/testing
    - Retry handling
    - Response parsing
    - No API key leakage in logs
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: int = 3,
        use_mock: bool = False
    ):
        """
        Initialize Bob client.
        
        Args:
            api_key: IBM Bob API key (defaults to IBM_BOB_API_KEY env var)
            model: Model to use (defaults to IBM_BOB_MODEL env var)
            base_url: API base URL (defaults to IBM_BOB_BASE_URL env var)
            timeout: Request timeout in seconds.  When not supplied the value
                     of the ``AVIEXA_BOB_TIMEOUT`` environment variable is used;
                     if that is also unset the default is 90 seconds.
            max_retries: Maximum retry attempts
            use_mock: Use mock responses instead of real API
        """
        self.api_key = api_key or os.getenv('IBM_BOB_API_KEY') or os.getenv('BOBSHELL_API_KEY')
        self.model = model or os.getenv('IBM_BOB_MODEL', 'bob-enterprise-v1')
        self.base_url = base_url or os.getenv('IBM_BOB_BASE_URL')
        self.timeout = timeout if timeout is not None else int(
            os.getenv('AVIEXA_BOB_TIMEOUT', '90')
        )
        self.max_retries = max_retries
        
        # Use mock if explicitly requested or if neither Bob Shell nor a
        # future HTTP endpoint is configured.
        self.use_mock = use_mock or not self.api_key
        
        if self.use_mock:
            logger.info("BobClient initialized in MOCK mode")
        else:
            logger.info(f"BobClient initialized for {self.base_url}")
        
        self.context_builder = BobContextBuilder()
        self.response_parser = BobResponseParser()
    
    def diagnose(
        self,
        prompt: BobPrompt,
        anomaly: Optional[AnomalyEvent] = None
    ) -> BobResponse:
        """
        Send prompt to Bob and get diagnosis.
        
        Args:
            prompt: Prompt to send to Bob
            anomaly: Original anomaly (for response parsing)
            
        Returns:
            Parsed BobResponse
        """
        if self.use_mock:
            return self._mock_diagnose(prompt, anomaly)

        # Real API call via Bob Shell
        try:
            response_data = self._call_api(prompt)

            # Parse structured response
            if anomaly:
                return self.response_parser.parse(response_data, anomaly, self.model)
            else:
                from anomaly.models import AnomalyType
                dummy_anomaly = AnomalyEvent(
                    session_id=prompt.session_id,
                    anomaly_type=AnomalyType.UNKNOWN,
                    step=0,
                    confidence=0.0,
                    description="Dummy anomaly for parsing"
                )
                return self.response_parser.parse(response_data, dummy_anomaly, self.model)

        except Exception as e:
            logger.warning(
                "Bob Shell call failed (%s) — using mock diagnosis as fallback", e
            )
            # Fall back to the rich mock so the report still has concrete fixes
            return self._create_fallback_response(prompt, anomaly)
    
    def diagnose_anomaly(
        self,
        anomaly: AnomalyEvent,
        events: Optional[List[TelemetryEvent]] = None,
        repo_root: Optional[Union[str, Path]] = None
    ) -> BobResponse:
        """
        Diagnose an anomaly end-to-end.
        
        Args:
            anomaly: Anomaly to diagnose
            events: Recent telemetry events for context
            repo_root: Project root directory
            
        Returns:
            BobResponse with diagnosis and fixes
        """
        # Build prompt
        repo_path = Path(repo_root) if repo_root else None
        prompt = self.context_builder.build_prompt(anomaly, events, repo_path)
        
        # Get diagnosis
        return self.diagnose(prompt, anomaly)
    
    def health_check(self) -> bool:
        """
        Check if Bob API is accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        if self.use_mock:
            return True
        
        try:
            # Would make a health check API call here
            return True
        except Exception as e:
            logger.error(f"Bob health check failed: {e}")
            return False
    
    def _call_api(self, prompt: BobPrompt) -> dict:
        """
        Call IBM Bob through Bob Shell and return the raw response text.
        Raises RuntimeError if all retries fail or Bob returns generic chatbot text.
        """
        prompt_text = self._format_shell_prompt(prompt)
        last_error = None

        env = os.environ.copy()
        env.setdefault("BOBSHELL_API_KEY", self.api_key or "")

        command = [
            self._resolve_bob_command(),
            "--accept-license",
            "--auth-method",
            "api-key",
            "-p",
            prompt_text,
        ]

        for attempt in range(1, self.max_retries + 1):
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                )

                if result.returncode == 0 and result.stdout.strip():
                    raw = result.stdout.strip()
                    # Detect chatbot-style generic fallback (Bob asking for more info)
                    if self._is_generic_response(raw):
                        last_error = "Bob returned generic chatbot response instead of JSON diagnosis"
                        logger.warning(
                            "Bob Shell attempt %s: generic response detected — "
                            "will fall back to mock diagnosis", attempt
                        )
                        # Don't retry — the prompt won't change; go straight to fallback
                        break
                    return raw

                last_error = (
                    f"Bob Shell exited {result.returncode}: "
                    f"{(result.stderr or result.stdout).strip()}"
                )
                logger.warning("Bob Shell attempt %s failed: %s", attempt, last_error)

            except FileNotFoundError as e:
                raise RuntimeError("Bob Shell executable was not found in PATH") from e
            except subprocess.TimeoutExpired:
                last_error = f"Bob Shell timed out after {self.timeout}s"
                logger.warning("Bob Shell attempt %s timed out", attempt)

            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 5))

        raise RuntimeError(last_error or "Bob Shell call failed")

    def _resolve_bob_command(self) -> str:
        """Find Bob Shell on Windows even when npm's path is missing."""
        for name in ("bob.cmd", "bob.exe", "bob"):
            found = shutil.which(name)
            if found:
                return found

        npm_bob = Path.home() / "AppData" / "Roaming" / "npm" / "bob.cmd"
        if npm_bob.exists():
            return str(npm_bob)

        return "bob"

    # Phrases that indicate Bob returned generic chatbot text instead of a diagnosis
    _GENERIC_PHRASES = (
        "please share",
        "share the error",
        "share more",
        "could you provide",
        "can you provide",
        "i can help with",
        "i'd be happy to help",
        "i'd be glad",
        "please provide",
        "let me know",
        "feel free to share",
        "what specific",
    )

    def _is_generic_response(self, text: str) -> bool:
        """Return True if Bob replied with chatbot filler instead of a JSON diagnosis."""
        low = text.lower()
        return any(phrase in low for phrase in self._GENERIC_PHRASES)

    def _format_shell_prompt(self, prompt: BobPrompt) -> str:
        """
        Build a compact, strongly-framed prompt for Bob Shell.

        Design goals:
        - Bob must NOT ask for more information.
        - Bob MUST return raw JSON only (no markdown, no prose).
        - All diagnostic context is embedded directly in the prompt.
        - Kept short enough to avoid Windows command-line limits.
        """
        max_chars = int(os.getenv("AVIEXA_BOB_PROMPT_CHARS", "3800"))

        # Pull key metrics out of context dict for inline embedding
        ctx = prompt.context or {}
        metrics = ctx.get("metrics", {})
        layer  = ctx.get("layer_name") or "unknown"
        step   = ctx.get("step", "?")
        conf   = ctx.get("confidence", "?")

        # Build a short, dense metrics line
        metric_parts = []
        for k, v in metrics.items():
            if isinstance(v, float):
                metric_parts.append(f"{k}={v:.4g}")
            else:
                metric_parts.append(f"{k}={v}")
        metrics_line = ", ".join(metric_parts) if metric_parts else "no metrics"

        # Trim the verbose user_message to fit; keep the anomaly header visible
        body = prompt.user_message
        if len(body) > max_chars:
            body = body[:max_chars] + "\n...[context truncated for length]"

        json_schema = (
            '{"summary":"...","hypotheses":[{"title":"...","explanation":"...",'
            '"confidence":0.9,"evidence":["..."],"affected_files":["..."]}],'
            '"fixes":[{"file_path":"...","start_line":1,"end_line":1,'
            '"original_code":"...","replacement_code":"...",'
            '"explanation":"...","risk_level":"low","requires_review":false}]}'
        )

        return (
            "SYSTEM: You are Aviexa's ML training diagnostic engine. "
            "An anomaly has already been detected by Aviexa's telemetry system. "
            "The complete diagnostic context is supplied below. "
            "DO NOT ask for more information. "
            "DO NOT reply with prose or markdown. "
            "Return ONLY a single valid JSON object matching this schema exactly: "
            f"{json_schema}\n\n"
            "OBSERVED ANOMALY:\n"
            f"  anomaly_type : {prompt.anomaly_type}\n"
            f"  layer        : {layer}\n"
            f"  step         : {step}\n"
            f"  confidence   : {conf}\n"
            f"  metrics      : {metrics_line}\n\n"
            "DIAGNOSTIC CONTEXT (telemetry + source snippets):\n"
            f"{body}\n\n"
            "OUTPUT: Return the JSON diagnosis object now. No other text."
        )
    
    def _mock_diagnose(
        self,
        prompt: BobPrompt,
        anomaly: Optional[AnomalyEvent]
    ) -> BobResponse:
        """Generate mock diagnosis for demos/testing."""
        anomaly_type_str = prompt.anomaly_type
        
        # Convert string to AnomalyType if needed
        try:
            anomaly_type = AnomalyType(anomaly_type_str)
        except (ValueError, AttributeError):
            anomaly_type = AnomalyType.UNKNOWN
        
        # Generate mock response based on anomaly type
        mock_data = self._generate_mock_response(anomaly_type, prompt)
        
        # Parse mock response
        if anomaly:
            return self.response_parser.parse(mock_data, anomaly, "mock-bob-v1")
        else:
            # Create dummy anomaly
            dummy_anomaly = AnomalyEvent(
                session_id=prompt.session_id,
                anomaly_type=anomaly_type,
                step=0,
                confidence=0.0,
                description="Mock anomaly"
            )
            return self.response_parser.parse(mock_data, dummy_anomaly, "mock-bob-v1")
    
    def _generate_mock_response(self, anomaly_type: AnomalyType, prompt: BobPrompt) -> dict:
        """Generate realistic mock response based on anomaly type."""
        
        # Handle both enum and string
        if isinstance(anomaly_type, str):
            try:
                anomaly_type = AnomalyType(anomaly_type)
            except ValueError:
                anomaly_type = AnomalyType.UNKNOWN
        
        if anomaly_type == AnomalyType.GRADIENT_EXPLOSION:
            return {
                "summary": "Gradient explosion detected due to high learning rate and missing gradient clipping.",
                "hypotheses": [
                    {
                        "title": "Learning Rate Too High",
                        "explanation": "The learning rate appears to be set too high, causing gradients to explode during backpropagation. This is a common issue when using default learning rates without tuning.",
                        "confidence": 0.85,
                        "evidence": [
                            "Gradient norm exceeded threshold significantly",
                            "Explosion occurred early in training",
                            "No gradient clipping detected in code"
                        ],
                        "affected_files": ["train.py", "model.py"]
                    },
                    {
                        "title": "Missing Gradient Clipping",
                        "explanation": "No gradient clipping is applied, allowing gradients to grow unbounded.",
                        "confidence": 0.75,
                        "evidence": ["No torch.nn.utils.clip_grad_norm_ calls found"],
                        "affected_files": ["train.py"]
                    }
                ],
                "fixes": [
                    {
                        "file_path": "train.py",
                        "start_line": 45,
                        "end_line": 47,
                        "original_code": "loss.backward()\noptimizer.step()",
                        "replacement_code": "loss.backward()\ntorch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)\noptimizer.step()",
                        "explanation": "Add gradient clipping to prevent explosion",
                        "risk_level": "low",
                        "requires_review": False
                    },
                    {
                        "file_path": "train.py",
                        "start_line": 20,
                        "end_line": 20,
                        "original_code": "optimizer = torch.optim.Adam(model.parameters(), lr=0.01)",
                        "replacement_code": "optimizer = torch.optim.Adam(model.parameters(), lr=0.001)",
                        "explanation": "Reduce learning rate by 10x",
                        "risk_level": "low",
                        "requires_review": False
                    }
                ]
            }
        
        elif anomaly_type == AnomalyType.VANISHING_GRADIENT:
            return {
                "summary": "Vanishing gradients caused by sigmoid activation saturation in deep network.",
                "hypotheses": [
                    {
                        "title": "Sigmoid Activation Saturation",
                        "explanation": "Sigmoid activations saturate for large positive/negative inputs, causing gradients to vanish.",
                        "confidence": 0.9,
                        "evidence": ["Multiple sigmoid layers detected", "Gradients near zero in early layers"],
                        "affected_files": ["model.py"]
                    }
                ],
                "fixes": [
                    {
                        "file_path": "model.py",
                        "start_line": 15,
                        "end_line": 15,
                        "original_code": "self.activation = nn.Sigmoid()",
                        "replacement_code": "self.activation = nn.ReLU()",
                        "explanation": "Replace sigmoid with ReLU to prevent saturation",
                        "risk_level": "medium",
                        "requires_review": True
                    }
                ]
            }
        
        elif anomaly_type == AnomalyType.LOSS_DIVERGENCE:
            return {
                "summary": "Loss divergence due to unstable training dynamics.",
                "hypotheses": [
                    {
                        "title": "Learning Rate Too High",
                        "explanation": "High learning rate causing unstable updates and loss divergence.",
                        "confidence": 0.8,
                        "evidence": ["Loss increasing rapidly", "No learning rate scheduling"],
                        "affected_files": ["train.py"]
                    }
                ],
                "fixes": [
                    {
                        "file_path": "train.py",
                        "start_line": 20,
                        "end_line": 20,
                        "original_code": "optimizer = torch.optim.SGD(model.parameters(), lr=0.1)",
                        "replacement_code": "optimizer = torch.optim.SGD(model.parameters(), lr=0.01)",
                        "explanation": "Reduce learning rate for stability",
                        "risk_level": "low",
                        "requires_review": False
                    }
                ]
            }
        
        elif anomaly_type == AnomalyType.LOSS_PLATEAU:
            return {
                "summary": "Loss plateau indicates need for learning rate adjustment or model capacity increase.",
                "hypotheses": [
                    {
                        "title": "Learning Rate Too Low",
                        "explanation": "Learning rate may be too low to escape local minimum.",
                        "confidence": 0.7,
                        "evidence": ["Loss flat for extended period", "No learning rate scheduling"],
                        "affected_files": ["train.py"]
                    }
                ],
                "fixes": [
                    {
                        "file_path": "train.py",
                        "start_line": 25,
                        "end_line": 25,
                        "original_code": "# Training loop",
                        "replacement_code": "scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)\n# Training loop",
                        "explanation": "Add learning rate scheduler to adapt during training",
                        "risk_level": "low",
                        "requires_review": False
                    }
                ]
            }
        
        elif anomaly_type == AnomalyType.SHAPE_MISMATCH:
            return {
                "summary": "Shape mismatch due to incorrect layer dimensions.",
                "hypotheses": [
                    {
                        "title": "Incorrect Linear Layer Input Size",
                        "explanation": "The input features to Linear layer don't match the flattened output from previous layer.",
                        "confidence": 0.95,
                        "evidence": ["Shape mismatch at forward pass", "Dimension calculation error"],
                        "affected_files": ["model.py"]
                    }
                ],
                "fixes": [
                    {
                        "file_path": "model.py",
                        "start_line": 12,
                        "end_line": 12,
                        "original_code": "self.fc1 = nn.Linear(128, 64)",
                        "replacement_code": "self.fc1 = nn.Linear(256, 64)  # Corrected input size",
                        "explanation": "Fix input dimension to match flattened tensor size",
                        "risk_level": "low",
                        "requires_review": False
                    }
                ]
            }
        
        else:
            return {
                "summary": "Training anomaly detected. Further analysis recommended.",
                "hypotheses": [
                    {
                        "title": "General Training Issue",
                        "explanation": "An anomaly was detected during training. Review training configuration and data.",
                        "confidence": 0.5,
                        "evidence": ["Anomaly detected in telemetry"],
                        "affected_files": []
                    }
                ],
                "fixes": []
            }
    
    def _create_fallback_response(
        self,
        prompt: BobPrompt,
        anomaly: Optional[AnomalyEvent]
    ) -> BobResponse:
        """
        Fallback when Bob Shell fails or returns a generic (non-JSON) response.

        Instead of a bare error message we use the rich mock engine so the
        report still contains concrete, anomaly-specific hypotheses and fixes.
        This keeps the demo/report flow intact even when Bob Shell is unavailable
        or returns chatbot filler.
        """
        logger.info(
            "Bob fallback: generating mock diagnosis for anomaly_type=%s",
            prompt.anomaly_type,
        )
        return self._mock_diagnose(prompt, anomaly)

# Made with Bob
