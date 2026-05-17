"""
verify_layer3.py
Verification script for Layer 3: IBM Bob Integration
Tests context building, prompt templates, response parsing, and mock client.
"""

import sys
import json

print("=" * 60)
print("LAYER 3 VERIFICATION - IBM Bob Integration")
print("=" * 60)

# Test 1: Imports
print("\n1. Testing imports...")
try:
    from bob import (
        BobClient,
        BobContextBuilder,
        BobResponseParser,
        BobPrompt,
        BobResponse,
        Hypothesis,
        CodeFix,
        DiagnosticReport,
        SourceSnippet
    )
    from bob.prompt_templates import get_prompt_template, get_prompt_version
    from anomaly.models import AnomalyEvent, AnomalyType, BackwardEvent, TelemetryEvent
    print("[OK] All imports successful")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test 2: Prompt Templates
print("\n2. Testing prompt templates...")
try:
    for anomaly_type in AnomalyType:
        template = get_prompt_template(anomaly_type)
        version = get_prompt_version(anomaly_type)
        assert isinstance(template, str), f"Template for {anomaly_type} is not a string"
        assert len(template) > 0, f"Template for {anomaly_type} is empty"
        assert isinstance(version, str), f"Version for {anomaly_type} is not a string"
    print(f"[OK] All {len(list(AnomalyType))} anomaly types have templates and versions")
except Exception as e:
    print(f"[FAIL] Prompt template test failed: {e}")
    sys.exit(1)

# Test 3: Build Context
print("\n3. Testing context building...")
try:
    # Create sample anomaly
    anomaly = AnomalyEvent(
        session_id="test-session",
        anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
        step=100,
        layer_name="layer1.weight",
        confidence=0.85,
        description="Test gradient explosion",
        metrics={
            "gradient_norm": 150.0,
            "threshold": 100.0,
            "rolling_mean": 5.0
        }
    )
    
    # Build context
    builder = BobContextBuilder()
    prompt = builder.build_prompt(anomaly)
    
    assert isinstance(prompt, BobPrompt)
    assert prompt.anomaly_id == anomaly.anomaly_id
    assert prompt.session_id == anomaly.session_id
    assert "gradient" in prompt.user_message.lower()
    assert "json" in prompt.system_message.lower()
    assert len(prompt.user_message) > 100
    print(f"[OK] Context built successfully ({len(prompt.user_message)} chars)")
except Exception as e:
    print(f"[FAIL] Context building test failed: {e}")
    sys.exit(1)

# Test 4: Response Parser - Valid JSON
print("\n4. Testing response parser with valid JSON...")
try:
    valid_json = {
        "summary": "Test summary",
        "hypotheses": [
            {
                "title": "Test Hypothesis",
                "explanation": "Test explanation",
                "confidence": 0.8,
                "evidence": ["Evidence 1", "Evidence 2"],
                "affected_files": ["test.py"]
            }
        ],
        "fixes": [
            {
                "file_path": "test.py",
                "start_line": 10,
                "end_line": 12,
                "original_code": "old code",
                "replacement_code": "new code",
                "explanation": "Fix explanation",
                "risk_level": "low",
                "requires_review": False
            }
        ]
    }
    
    parser = BobResponseParser()
    response = parser.parse(valid_json, anomaly, "test-model")
    
    assert isinstance(response, BobResponse)
    assert response.summary == "Test summary"
    assert len(response.hypotheses) == 1
    assert len(response.fixes) == 1
    assert response.hypotheses[0].confidence == 0.8
    print("[OK] Valid JSON parsed successfully")
except Exception as e:
    print(f"[FAIL] Valid JSON parsing failed: {e}")
    sys.exit(1)

# Test 5: Response Parser - Markdown Wrapped JSON
print("\n5. Testing response parser with markdown-wrapped JSON...")
try:
    markdown_json = """```json
{
  "summary": "Markdown test",
  "hypotheses": [],
  "fixes": []
}
```"""
    
    response = parser.parse(markdown_json, anomaly, "test-model")
    assert isinstance(response, BobResponse)
    assert response.summary == "Markdown test"
    print("[OK] Markdown-wrapped JSON parsed successfully")
except Exception as e:
    print(f"[FAIL] Markdown JSON parsing failed: {e}")
    sys.exit(1)

# Test 6: Response Parser - Fallback Text
print("\n6. Testing response parser with plain text fallback...")
try:
    plain_text = "This is just plain text without JSON structure."
    
    response = parser.parse(plain_text, anomaly, "test-model")
    assert isinstance(response, BobResponse)
    assert len(response.summary) > 0
    assert len(response.hypotheses) >= 1  # Should have fallback hypothesis
    print("[OK] Plain text fallback parsing successful")
except Exception as e:
    print(f"[FAIL] Fallback parsing failed: {e}")
    sys.exit(1)

# Test 7: Mock Bob Client
print("\n7. Testing mock Bob client...")
try:
    client = BobClient(use_mock=True)
    assert client.use_mock == True
    
    # Test diagnose with prompt
    response = client.diagnose(prompt, anomaly)
    assert isinstance(response, BobResponse)
    assert len(response.summary) > 0
    assert len(response.hypotheses) > 0
    print(f"[OK] Mock client returned {len(response.hypotheses)} hypotheses")
except Exception as e:
    print(f"[FAIL] Mock client test failed: {e}")
    sys.exit(1)

# Test 8: Diagnose Anomaly End-to-End
print("\n8. Testing diagnose_anomaly end-to-end...")
try:
    # Create sample telemetry events
    from typing import List
    events: List[TelemetryEvent] = [
        BackwardEvent(
            session_id="test-session",
            step=i,
            layer_name="layer1.weight",
            gradient_norm=1.0 + i * 0.1
        )
        for i in range(95, 105)
    ]
    
    # Diagnose anomaly
    response = client.diagnose_anomaly(anomaly, events)
    
    assert isinstance(response, BobResponse)
    assert response.anomaly_id == anomaly.anomaly_id
    assert response.session_id == anomaly.session_id
    assert len(response.hypotheses) > 0
    
    # Check hypothesis quality
    hypothesis = response.hypotheses[0]
    assert len(hypothesis.title) > 0
    assert len(hypothesis.explanation) > 0
    assert 0.0 <= hypothesis.confidence <= 1.0
    
    print(f"[OK] End-to-end diagnosis successful")
    print(f"     Summary: {response.summary[:60]}...")
    print(f"     Hypotheses: {len(response.hypotheses)}")
    print(f"     Fixes: {len(response.fixes)}")
except Exception as e:
    print(f"[FAIL] End-to-end diagnosis failed: {e}")
    sys.exit(1)

# Test 9: Mock Responses for Different Anomaly Types
print("\n9. Testing mock responses for different anomaly types...")
try:
    anomaly_types_to_test = [
        AnomalyType.GRADIENT_EXPLOSION,
        AnomalyType.VANISHING_GRADIENT,
        AnomalyType.LOSS_DIVERGENCE,
        AnomalyType.LOSS_PLATEAU,
        AnomalyType.SHAPE_MISMATCH
    ]
    
    for anom_type in anomaly_types_to_test:
        test_anomaly = AnomalyEvent(
            session_id="test",
            anomaly_type=anom_type,
            step=10,
            confidence=0.8,
            description=f"Test {anom_type.value}"
        )
        
        response = client.diagnose_anomaly(test_anomaly)
        assert len(response.hypotheses) > 0, f"No hypotheses for {anom_type}"
        assert len(response.summary) > 0, f"No summary for {anom_type}"
    
    print(f"[OK] Mock responses generated for {len(anomaly_types_to_test)} anomaly types")
except Exception as e:
    print(f"[FAIL] Mock response generation failed: {e}")
    sys.exit(1)

# Test 10: Layer Independence
print("\n10. Testing layer independence...")
try:
    import bob.client as client_module
    import bob.context_builder as context_module
    import bob.response_parser as parser_module
    
    forbidden_imports = ['api', 'extension', 'reports']
    
    for module in [client_module, context_module, parser_module]:
        module_dict = dir(module)
        for forbidden in forbidden_imports:
            assert forbidden not in module_dict, f"Layer 3 should not import {forbidden}"
    
    print("[OK] Layer 3 is independent (no imports from api/extension/reports)")
except Exception as e:
    print(f"[FAIL] Layer independence test failed: {e}")
    sys.exit(1)

# Test 11: No Real Network Required
print("\n11. Testing that no real network calls are made...")
try:
    # Client should work without API key
    client_no_key = BobClient()
    assert client_no_key.use_mock == True, "Should default to mock mode without API key"
    
    # Should still work
    response = client_no_key.diagnose_anomaly(anomaly)
    assert isinstance(response, BobResponse)
    
    print("[OK] Verification works without IBM_BOB_API_KEY")
except Exception as e:
    print(f"[FAIL] Network independence test failed: {e}")
    sys.exit(1)

# Test 12: Health Check
print("\n12. Testing health check...")
try:
    health = client.health_check()
    assert health == True, "Mock client should always be healthy"
    print("[OK] Health check passed")
except Exception as e:
    print(f"[FAIL] Health check failed: {e}")
    sys.exit(1)

# Test 13: Diagnoses are actually populated (not empty BobResponse)
print("\n13. Verifying diagnosis content is non-empty (not a silent empty response)...")
try:
    for anom_type in [AnomalyType.GRADIENT_EXPLOSION, AnomalyType.VANISHING_GRADIENT,
                      AnomalyType.LOSS_DIVERGENCE, AnomalyType.LOSS_PLATEAU, AnomalyType.SHAPE_MISMATCH]:
        test_anomaly = AnomalyEvent(
            session_id="test-diag-content",
            anomaly_type=anom_type,
            step=5,
            confidence=0.9,
            description=f"Content check for {anom_type.value}",
            metrics={"gradient_norm": 99.0, "threshold": 10.0,
                     "consecutive_count": 3, "current_loss": 4.5,
                     "slope": 0.2, "window_size": 10, "variance": 0.01,
                     "expected_shape": "(32, 128)", "actual_shape": "(32, 256)",
                     "mismatch_reason": "dim 1 mismatch"},
        )
        response = client.diagnose_anomaly(test_anomaly)

        assert len(response.hypotheses) > 0, \
            f"[FAIL] diagnose_anomaly returned 0 hypotheses for {anom_type.value}"
        assert len(response.summary) > 10, \
            f"[FAIL] diagnose_anomaly returned a trivially short summary for {anom_type.value}"
        assert response.anomaly_id == test_anomaly.anomaly_id, \
            f"[FAIL] anomaly_id mismatch in response for {anom_type.value}"
        assert response.session_id == test_anomaly.session_id, \
            f"[FAIL] session_id mismatch in response for {anom_type.value}"

    print(f"[OK] All 5 anomaly types returned populated diagnoses")
except AssertionError as e:
    print(str(e))
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Diagnosis content verification failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("LAYER 3 VERIFICATION COMPLETE")
print("=" * 60)
print("[OK] All 13 tests passed")
print("\nLayer 3 components verified:")
print("  - BobClient (with mock mode)")
print("  - BobContextBuilder (context assembly)")
print("  - BobResponseParser (JSON/text parsing)")
print("  - BobPrompt/BobResponse models")
print("  - Prompt templates for all anomaly types")
print("  - Diagnosis content non-empty for all anomaly types")
print("\nReady for Layer 4: API + VS Code Extension")

# Made with Bob
