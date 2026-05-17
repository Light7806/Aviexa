"""
bob/prompt_templates.py
Versioned prompt templates for IBM Bob per anomaly type.
Instructs Bob to return structured JSON with diagnosis and fixes.
"""

from anomaly.models import AnomalyType


DEFAULT_SYSTEM_PROMPT = """You are Bob, an expert AI assistant specializing in PyTorch deep learning debugging and optimization.

Your role is to analyze training anomalies, diagnose root causes, and suggest concrete code fixes.

Always respond with valid JSON in this exact format:
{
  "summary": "Brief overview of the issue",
  "hypotheses": [
    {
      "title": "Hypothesis name",
      "explanation": "Detailed explanation",
      "confidence": 0.85,
      "evidence": ["Evidence point 1", "Evidence point 2"],
      "affected_files": ["file1.py", "file2.py"]
    }
  ],
  "fixes": [
    {
      "file_path": "path/to/file.py",
      "start_line": 10,
      "end_line": 12,
      "original_code": "old code here",
      "replacement_code": "new code here",
      "explanation": "Why this fix helps",
      "risk_level": "low|medium|high",
      "requires_review": true
    }
  ]
}

Be specific, actionable, and prioritize fixes by impact."""


GRADIENT_EXPLOSION_TEMPLATE = """# Gradient Explosion Detected

## Anomaly Details
- **Type**: Gradient Explosion
- **Layer**: {layer_name}
- **Step**: {step}
- **Gradient Norm**: {gradient_norm}
- **Threshold Exceeded**: {threshold}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose why gradients are exploding and suggest fixes. Common causes:
- Learning rate too high
- Missing gradient clipping
- Poor weight initialization
- Unstable loss function
- Batch normalization issues

Provide ranked hypotheses and concrete code fixes with line numbers."""


VANISHING_GRADIENT_TEMPLATE = """# Vanishing Gradient Detected

## Anomaly Details
- **Type**: Vanishing Gradient
- **Layer**: {layer_name}
- **Step**: {step}
- **Gradient Norm**: {gradient_norm}
- **Consecutive Low Steps**: {consecutive_count}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose why gradients are vanishing and suggest fixes. Common causes:
- Sigmoid/tanh activation saturation
- Too many layers without residual connections
- Poor weight initialization
- Missing batch/layer normalization
- Learning rate too low

Provide ranked hypotheses and concrete code fixes with line numbers."""


LOSS_DIVERGENCE_TEMPLATE = """# Loss Divergence Detected

## Anomaly Details
- **Type**: Loss Divergence
- **Step**: {step}
- **Current Loss**: {current_loss}
- **Slope**: {slope}
- **Window Size**: {window_size}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose why loss is diverging and suggest fixes. Common causes:
- Learning rate too high
- Unstable loss function
- Data preprocessing issues
- Numerical instability
- Incorrect loss reduction

Provide ranked hypotheses and concrete code fixes with line numbers."""


LOSS_PLATEAU_TEMPLATE = """# Loss Plateau Detected

## Anomaly Details
- **Type**: Loss Plateau
- **Step**: {step}
- **Current Loss**: {current_loss}
- **Slope**: {slope}
- **Variance**: {variance}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose why loss has plateaued and suggest fixes. Common causes:
- Learning rate too low or needs scheduling
- Model capacity insufficient
- Data lacks signal
- Optimizer stuck in local minimum
- Need for learning rate warmup/decay

Provide ranked hypotheses and concrete code fixes with line numbers."""


SHAPE_MISMATCH_TEMPLATE = """# Shape Mismatch Detected

## Anomaly Details
- **Type**: Shape Mismatch
- **Layer**: {layer_name}
- **Step**: {step}
- **Expected Shape**: {expected_shape}
- **Actual Shape**: {actual_shape}
- **Reason**: {mismatch_reason}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose the shape mismatch and suggest fixes. Common causes:
- Incorrect layer dimensions
- Missing reshape/flatten operations
- Batch size assumptions
- Incorrect input preprocessing
- Model architecture mismatch

Provide ranked hypotheses and concrete code fixes with line numbers."""


MEMORY_LEAK_TEMPLATE = """# Memory Leak Detected

## Anomaly Details
- **Type**: Memory Leak
- **Step**: {step}
- **Current Memory**: {current_mb} MB
- **Baseline Memory**: {baseline_mb} MB
- **Growth Ratio**: {growth_ratio}x

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Diagnose the memory leak and suggest fixes. Common causes:
- Accumulating gradients without clearing
- Retaining computation graphs
- Growing lists/caches
- Not detaching tensors
- Memory-intensive operations in loop

Provide ranked hypotheses and concrete code fixes with line numbers."""


UNKNOWN_TEMPLATE = """# Training Anomaly Detected

## Anomaly Details
- **Type**: {anomaly_type}
- **Step**: {step}

## Telemetry Context
{telemetry_summary}

## Source Code
{source_snippets}

## Task
Analyze the training anomaly and suggest potential fixes.

Provide ranked hypotheses and concrete code fixes with line numbers."""


# Template mapping
TEMPLATES = {
    AnomalyType.GRADIENT_EXPLOSION: GRADIENT_EXPLOSION_TEMPLATE,
    AnomalyType.VANISHING_GRADIENT: VANISHING_GRADIENT_TEMPLATE,
    AnomalyType.LOSS_DIVERGENCE: LOSS_DIVERGENCE_TEMPLATE,
    AnomalyType.LOSS_PLATEAU: LOSS_PLATEAU_TEMPLATE,
    AnomalyType.SHAPE_MISMATCH: SHAPE_MISMATCH_TEMPLATE,
    AnomalyType.MEMORY_LEAK: MEMORY_LEAK_TEMPLATE,
    AnomalyType.UNKNOWN: UNKNOWN_TEMPLATE,
}

# Version mapping
VERSIONS = {
    AnomalyType.GRADIENT_EXPLOSION: "1.0",
    AnomalyType.VANISHING_GRADIENT: "1.0",
    AnomalyType.LOSS_DIVERGENCE: "1.0",
    AnomalyType.LOSS_PLATEAU: "1.0",
    AnomalyType.SHAPE_MISMATCH: "1.0",
    AnomalyType.MEMORY_LEAK: "1.0",
    AnomalyType.UNKNOWN: "1.0",
}


def get_prompt_template(anomaly_type: AnomalyType) -> str:
    """
    Get prompt template for anomaly type.
    
    Args:
        anomaly_type: Type of anomaly (enum or string)
        
    Returns:
        Prompt template string
    """
    # Handle both enum and string
    if isinstance(anomaly_type, str):
        try:
            anomaly_type = AnomalyType(anomaly_type)
        except ValueError:
            return UNKNOWN_TEMPLATE
    
    return TEMPLATES.get(anomaly_type, UNKNOWN_TEMPLATE)


def get_prompt_version(anomaly_type: AnomalyType) -> str:
    """
    Get prompt version for anomaly type.
    
    Args:
        anomaly_type: Type of anomaly (enum or string)
        
    Returns:
        Version string
    """
    # Handle both enum and string
    if isinstance(anomaly_type, str):
        try:
            anomaly_type = AnomalyType(anomaly_type)
        except ValueError:
            return "1.0"
    
    return VERSIONS.get(anomaly_type, "1.0")


