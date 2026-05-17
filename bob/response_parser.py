"""
bob/response_parser.py
Robust parsing of IBM Bob responses.
Handles JSON, markdown-wrapped JSON, and fallback text parsing.
"""

import json
import re
import logging
from typing import Union, Dict, Any, Optional

from anomaly.models import AnomalyEvent
from bob.models import BobResponse, Hypothesis, CodeFix, RiskLevel

logger = logging.getLogger(__name__)


class BobResponseParser:
    """
    Parses IBM Bob responses into structured BobResponse objects.
    
    Features:
    - Strict JSON parsing
    - Markdown code fence unwrapping
    - Fallback text parsing
    - Never crashes on malformed input
    """
    
    def parse(
        self,
        raw_response: Union[str, Dict[str, Any]],
        anomaly: AnomalyEvent,
        model: Optional[str] = None
    ) -> BobResponse:
        """
        Parse Bob response into structured format.
        
        Args:
            raw_response: Raw response from Bob (string or dict)
            anomaly: Original anomaly event
            model: Model name used
            
        Returns:
            Parsed BobResponse object
        """
        # If already a dict, use it directly
        if isinstance(raw_response, dict):
            return self._parse_dict(raw_response, anomaly, model, None)
        
        # Try JSON parsing
        try:
            data = self._parse_json(raw_response)
            return self._parse_dict(data, anomaly, model, raw_response)
        except Exception as e:
            logger.debug(f"JSON parsing failed: {e}")
        
        # Try unwrapping markdown code fence
        try:
            unwrapped = self._unwrap_markdown(raw_response)
            data = self._parse_json(unwrapped)
            return self._parse_dict(data, anomaly, model, raw_response)
        except Exception as e:
            logger.debug(f"Markdown unwrap failed: {e}")
        
        # Fallback to text parsing
        logger.debug("Using fallback text parsing for Bob response")
        return self._fallback_parse(raw_response, anomaly, model)
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Parse JSON from text."""
        return json.loads(text)
    
    def _unwrap_markdown(self, text: str) -> str:
        """Unwrap JSON from markdown code fence."""
        # Match ```json ... ``` or ``` ... ```
        pattern = r'```(?:json)?\s*\n(.*?)\n```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        return text
    
    def _parse_dict(
        self,
        data: Dict[str, Any],
        anomaly: AnomalyEvent,
        model: Optional[str],
        raw_response: Optional[str]
    ) -> BobResponse:
        """Parse dictionary into BobResponse."""
        # Extract summary
        summary = data.get('summary', 'No summary provided')
        
        # Parse hypotheses
        hypotheses = []
        for h_data in data.get('hypotheses', []):
            try:
                if isinstance(h_data, str):
                    h_data = {
                        "title": "Bob hypothesis",
                        "explanation": h_data,
                        "confidence": 0.5,
                        "evidence": [],
                        "affected_files": []
                    }
                hypothesis = Hypothesis(
                    title=h_data.get('title', 'Untitled Hypothesis'),
                    explanation=h_data.get('explanation', ''),
                    confidence=float(h_data.get('confidence', 0.5)),
                    evidence=h_data.get('evidence', []),
                    affected_files=h_data.get('affected_files', [])
                )
                hypotheses.append(hypothesis)
            except Exception as e:
                logger.warning(f"Error parsing hypothesis: {e}")
        
        # Parse fixes
        fixes = []
        for f_data in data.get('fixes', []):
            try:
                if isinstance(f_data, str):
                    f_data = {
                        "file_path": "unknown",
                        "replacement_code": "",
                        "explanation": f_data,
                        "risk_level": "medium",
                        "requires_review": True
                    }
                # Parse risk level
                risk_str = f_data.get('risk_level', 'medium').lower()
                try:
                    risk_level = RiskLevel(risk_str)
                except ValueError:
                    risk_level = RiskLevel.MEDIUM
                
                fix = CodeFix(
                    file_path=f_data.get('file_path', 'unknown'),
                    start_line=f_data.get('start_line'),
                    end_line=f_data.get('end_line'),
                    original_code=f_data.get('original_code'),
                    replacement_code=f_data.get('replacement_code', ''),
                    explanation=f_data.get('explanation', ''),
                    risk_level=risk_level,
                    requires_review=f_data.get('requires_review', True)
                )
                fixes.append(fix)
            except Exception as e:
                logger.warning(f"Error parsing fix: {e}")
        
        return BobResponse(
            anomaly_id=anomaly.anomaly_id,
            session_id=anomaly.session_id,
            summary=summary,
            hypotheses=hypotheses,
            fixes=fixes,
            raw_response=raw_response,
            model=model
        )
    
    def _fallback_parse(
        self,
        raw_response: str,
        anomaly: AnomalyEvent,
        model: Optional[str]
    ) -> BobResponse:
        """Fallback parsing when JSON fails."""
        # Extract summary from first paragraph
        lines = raw_response.strip().split('\n')
        summary = lines[0] if lines else "Unable to parse response"
        
        # Create a single fallback hypothesis
        hypothesis = Hypothesis(
            title="Analysis from Bob",
            explanation=raw_response[:500],  # First 500 chars
            confidence=0.5,
            evidence=["Raw text response - structured parsing failed"],
            affected_files=[]
        )
        
        return BobResponse(
            anomaly_id=anomaly.anomaly_id,
            session_id=anomaly.session_id,
            summary=summary,
            hypotheses=[hypothesis],
            fixes=[],
            raw_response=raw_response,
            model=model
        )


def parse_bob_response(
    raw_response: Union[str, Dict[str, Any]],
    anomaly: AnomalyEvent,
    model: Optional[str] = None
) -> BobResponse:
    """
    Convenience function to parse Bob response.
    
    Args:
        raw_response: Raw response from Bob
        anomaly: Original anomaly event
        model: Model name used
        
    Returns:
        Parsed BobResponse object
    """
    parser = BobResponseParser()
    return parser.parse(raw_response, anomaly, model)

# Made with Bob
