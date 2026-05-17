"""
bob/context_builder.py
Builds rich context packets for IBM Bob from anomalies and telemetry.
Critical file for diagnosis quality.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from anomaly.models import AnomalyEvent, TelemetryEvent, AnomalyType
from bob.models import BobPrompt, SourceSnippet
from bob.prompt_templates import (
    DEFAULT_SYSTEM_PROMPT,
    get_prompt_template,
    get_prompt_version
)

logger = logging.getLogger(__name__)


class BobContextBuilder:
    """
    Builds context packets for IBM Bob diagnosis.
    
    Assembles:
    - Anomaly details and metrics
    - Recent telemetry events
    - Relevant source code snippets
    - Project metadata
    """
    
    # Directories to exclude from source collection
    EXCLUDE_DIRS = {
        '.venv', 'venv', '__pycache__', '.git', 'node_modules',
        'build', 'dist', '.pytest_cache', '.mypy_cache', 'htmlcov',
        '.tox', 'eggs', '.eggs'
    }
    
    # File extensions to consider
    RELEVANT_EXTENSIONS = {'.py', '.txt', '.md', '.json', '.yaml', '.yml'}
    
    # Max file size to read (1MB)
    MAX_FILE_SIZE = 1024 * 1024
    
    # Max snippet length
    MAX_SNIPPET_LENGTH = 2000
    
    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize context builder.
        
        Args:
            repo_root: Root directory of the project (optional)
        """
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
    
    def build_prompt(
        self,
        anomaly: AnomalyEvent,
        events: Optional[List[TelemetryEvent]] = None,
        repo_root: Optional[Path] = None
    ) -> BobPrompt:
        """
        Build complete prompt for IBM Bob.
        
        Args:
            anomaly: Anomaly event to diagnose
            events: Recent telemetry events for context
            repo_root: Project root directory
            
        Returns:
            BobPrompt ready to send to Bob
        """
        if repo_root:
            self.repo_root = Path(repo_root)
        
        # Get template for anomaly type
        template = get_prompt_template(anomaly.anomaly_type)
        version = get_prompt_version(anomaly.anomaly_type)
        
        # Build context components
        telemetry_summary = self._build_telemetry_summary(anomaly, events)
        source_snippets = self._build_source_snippets(anomaly)
        
        # Format template with anomaly data
        user_message = self._format_template(
            template,
            anomaly,
            telemetry_summary,
            source_snippets
        )
        
        # Build context dict
        # Handle both enum and string for anomaly_type
        if hasattr(anomaly.anomaly_type, 'value'):
            anomaly_type_str = anomaly.anomaly_type.value
        else:
            anomaly_type_str = str(anomaly.anomaly_type)
        
        context = {
            "anomaly_type": anomaly_type_str,
            "step": anomaly.step,
            "layer_name": anomaly.layer_name,
            "confidence": anomaly.confidence,
            "metrics": anomaly.metrics,
            "description": anomaly.description,
        }
        
        # Build metadata
        metadata = {
            "repo_root": str(self.repo_root),
            "event_count": len(events) if events else 0,
        }
        
        return BobPrompt(
            anomaly_id=anomaly.anomaly_id,
            session_id=anomaly.session_id,
            anomaly_type=context["anomaly_type"],
            prompt_version=version,
            system_message=DEFAULT_SYSTEM_PROMPT,
            user_message=user_message,
            context=context,
            metadata=metadata
        )
    
    def _build_telemetry_summary(
        self,
        anomaly: AnomalyEvent,
        events: Optional[List[TelemetryEvent]]
    ) -> str:
        """Build a compact but concrete summary of recent telemetry events.

        Includes actual metric values (gradient norms, loss readings) so
        Bob receives real numbers to reason about, not just event counts.
        """
        if not events:
            return "No recent telemetry events available."

        # Filter events around anomaly step
        window = 10
        relevant_events = [
            e for e in events
            if abs(e.step - anomaly.step) <= window
        ]

        if not relevant_events:
            return f"No telemetry events within {window} steps of anomaly."

        summary_lines = [
            f"Telemetry snapshot ({len(relevant_events)} events near step {anomaly.step}):",
            ""
        ]

        # Import here to avoid circular issues at module level
        from collections import defaultdict
        from anomaly.models import BackwardEvent, LossEvent

        by_type: dict = defaultdict(list)
        for event in relevant_events[-20:]:
            by_type[event.event_type].append(event)

        for event_type, type_events in by_type.items():
            # Handle both enum and string for event_type
            if hasattr(event_type, 'value'):
                event_type_str = event_type.value
            else:
                event_type_str = str(event_type)

            if event_type_str == "backward":
                # Emit actual gradient norm per step
                norm_parts = []
                for ev in type_events[-8:]:
                    gn = getattr(ev, "gradient_norm", None)
                    if gn is not None:
                        norm_parts.append(f"step{ev.step}={gn:.4g}")
                detail = ", ".join(norm_parts) if norm_parts else f"{len(type_events)} events"
                summary_lines.append(f"- backward gradient_norms: {detail}")
            elif event_type_str == "loss":
                # Emit actual loss values per step
                loss_parts = []
                for ev in type_events[-8:]:
                    lv = getattr(ev, "loss_value", None)
                    if lv is not None:
                        loss_parts.append(f"step{ev.step}={lv:.4g}")
                detail = ", ".join(loss_parts) if loss_parts else f"{len(type_events)} events"
                summary_lines.append(f"- loss values: {detail}")
            else:
                summary_lines.append(f"- {event_type_str}: {len(type_events)} events")

        return "\n".join(summary_lines)


    def _build_source_snippets(self, anomaly: AnomalyEvent) -> str:
        """Collect relevant source code snippets."""
        snippets = self._collect_source_snippets(anomaly)
        
        if not snippets:
            return "No source code snippets available."
        
        snippet_lines = ["Relevant source code:", ""]
        
        for snippet in snippets[:5]:  # Limit to 5 snippets
            snippet_lines.append(f"### {snippet.file_path}")
            if snippet.start_line and snippet.end_line:
                snippet_lines.append(f"Lines {snippet.start_line}-{snippet.end_line}")
            if snippet.reason:
                snippet_lines.append(f"Relevance: {snippet.reason}")
            snippet_lines.append("```python")
            snippet_lines.append(snippet.content[:self.MAX_SNIPPET_LENGTH])
            snippet_lines.append("```")
            snippet_lines.append("")
        
        return "\n".join(snippet_lines)
    
    def _collect_source_snippets(self, anomaly: AnomalyEvent) -> List[SourceSnippet]:
        """Collect relevant source files based on anomaly type."""
        snippets = []
        
        try:
            # Find relevant files
            relevant_files = self._find_relevant_files(anomaly)
            
            for file_path in relevant_files[:10]:  # Limit to 10 files
                try:
                    snippet = self._read_file_snippet(file_path, anomaly)
                    if snippet:
                        snippets.append(snippet)
                except Exception as e:
                    logger.debug(f"Could not read {file_path}: {e}")
        
        except Exception as e:
            logger.warning(f"Error collecting source snippets: {e}")
        
        return snippets
    
    def _find_relevant_files(self, anomaly: AnomalyEvent) -> List[Path]:
        """Find files relevant to the anomaly."""
        relevant_files = []
        
        if not self.repo_root.exists():
            return relevant_files
        
        # Keywords to search for based on anomaly type
        keywords = self._get_search_keywords(anomaly.anomaly_type)
        
        try:
            for file_path in self.repo_root.rglob("*.py"):
                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in self.EXCLUDE_DIRS):
                    continue
                
                # Skip if too large
                if file_path.stat().st_size > self.MAX_FILE_SIZE:
                    continue
                
                # Check if file is relevant
                if self._is_file_relevant(file_path, keywords, anomaly):
                    relevant_files.append(file_path)
        
        except Exception as e:
            logger.debug(f"Error finding relevant files: {e}")
        
        return relevant_files
    
    def _get_search_keywords(self, anomaly_type: AnomalyType) -> List[str]:
        """Get search keywords for anomaly type."""
        # Handle both enum and string
        if isinstance(anomaly_type, str):
            try:
                anomaly_type = AnomalyType(anomaly_type)
            except ValueError:
                return ['train', 'model', 'forward']
        
        keyword_map = {
            AnomalyType.GRADIENT_EXPLOSION: ['optimizer', 'backward', 'clip_grad', 'lr', 'learning_rate'],
            AnomalyType.VANISHING_GRADIENT: ['activation', 'sigmoid', 'tanh', 'relu', 'initialization'],
            AnomalyType.LOSS_DIVERGENCE: ['loss', 'criterion', 'learning_rate', 'optimizer'],
            AnomalyType.LOSS_PLATEAU: ['scheduler', 'learning_rate', 'optimizer', 'lr_scheduler'],
            AnomalyType.SHAPE_MISMATCH: ['Linear', 'Conv', 'reshape', 'view', 'flatten', 'forward'],
            AnomalyType.MEMORY_LEAK: ['detach', 'no_grad', 'backward', 'optimizer'],
        }
        return keyword_map.get(anomaly_type, ['train', 'model', 'forward'])
    
    def _is_file_relevant(self, file_path: Path, keywords: List[str], anomaly: AnomalyEvent) -> bool:
        """Check if file is relevant to anomaly."""
        # Prioritize demo and training scripts
        if 'demo' in str(file_path) or 'train' in str(file_path):
            return True
        
        # Check filename
        filename_lower = file_path.name.lower()
        if any(kw.lower() in filename_lower for kw in keywords):
            return True
        
        return False
    
    def _read_file_snippet(self, file_path: Path, anomaly: AnomalyEvent) -> Optional[SourceSnippet]:
        """Read a file and create a snippet."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Limit content length
            if len(content) > self.MAX_SNIPPET_LENGTH:
                content = content[:self.MAX_SNIPPET_LENGTH] + "\n... (truncated)"
            
            relative_path = file_path.relative_to(self.repo_root)
            
            # Handle both enum and string for anomaly_type
            if hasattr(anomaly.anomaly_type, 'value'):
                anomaly_type_str = anomaly.anomaly_type.value
            else:
                anomaly_type_str = str(anomaly.anomaly_type)
            
            return SourceSnippet(
                file_path=str(relative_path),
                content=content,
                relevance_score=0.8,
                reason=f"Relevant to {anomaly_type_str}"
            )
        
        except Exception as e:
            logger.debug(f"Error reading {file_path}: {e}")
            return None
    
    def _format_template(
        self,
        template: str,
        anomaly: AnomalyEvent,
        telemetry_summary: str,
        source_snippets: str
    ) -> str:
        """Format template with anomaly data.

        Uses string.Formatter.parse() to enumerate every placeholder
        in the template *before* calling format(), so missing metric
        fields are silently substituted with "N/A" instead of emitting
        a warning and doing a second formatting pass.
        """
        import string

        # Base fields always present
        format_dict: Dict[str, Any] = {
            "anomaly_type": anomaly.anomaly_type.value if hasattr(anomaly.anomaly_type, "value") else str(anomaly.anomaly_type),
            "layer_name": anomaly.layer_name or "unknown",
            "step": anomaly.step,
            "telemetry_summary": telemetry_summary,
            "source_snippets": source_snippets,
        }

        # Merge anomaly metrics (e.g. gradient_norm, threshold, …)
        format_dict.update(anomaly.metrics)

        # Pre-fill every placeholder the template references that is still missing,
        # so format() never raises KeyError and never needs a second pass.
        for _, field_name, _, _ in string.Formatter().parse(template):
            if field_name is not None and field_name not in format_dict:
                format_dict[field_name] = "N/A"

        return template.format(**format_dict)


# Made with Bob
