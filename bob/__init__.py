"""
bob package
IBM Bob integration for AI-powered training diagnostics.
"""

from bob.client import BobClient
from bob.context_builder import BobContextBuilder
from bob.response_parser import BobResponseParser, parse_bob_response
from bob.models import (
    BobPrompt,
    BobResponse,
    Hypothesis,
    CodeFix,
    DiagnosticReport,
    SourceSnippet,
    RiskLevel,
    DiagnosticStatus
)

__all__ = [
    "BobClient",
    "BobContextBuilder",
    "BobResponseParser",
    "parse_bob_response",
    "BobPrompt",
    "BobResponse",
    "Hypothesis",
    "CodeFix",
    "DiagnosticReport",
    "SourceSnippet",
    "RiskLevel",
    "DiagnosticStatus",
]

# Made with Bob
