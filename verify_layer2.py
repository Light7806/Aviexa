"""
verify_layer2.py
Verification script for Layer 2: Anomaly Detection
Tests all detectors and the main orchestrator.
"""

import sys
from datetime import datetime

# Test imports
print("=" * 60)
print("LAYER 2 VERIFICATION - Anomaly Detection")
print("=" * 60)

print("\n1. Testing imports...")
try:
    from anomaly.detectors import (
        AnomalyDetector,
        GradientDetector,
        LossDetector,
        ShapeDetector,
        AnomalyClassifier
    )
    from anomaly.models import (
        BackwardEvent,
        LossEvent,
        ShapeEvent,
        AnomalyEvent,
        AnomalyType,
        EventType
    )
    print("[OK] All imports successful")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test 2: Gradient Explosion Detection
print("\n2. Testing gradient explosion detection...")
try:
    detector = GradientDetector(explosion_threshold=10.0)
    
    # Feed normal gradients
    for i in range(5):
        event = BackwardEvent(
            session_id="test",
            step=i,
            layer_name="layer1",
            gradient_norm=1.0 + i * 0.1
        )
        anomalies = detector.update(event)
        assert len(anomalies) == 0, f"False positive at step {i}"
    
    # Feed exploding gradient
    event = BackwardEvent(
        session_id="test",
        step=10,
        layer_name="layer1",
        gradient_norm=100.0
    )
    anomalies = detector.update(event)
    assert len(anomalies) == 1, "Should detect gradient explosion"
    assert anomalies[0].anomaly_type == AnomalyType.GRADIENT_EXPLOSION
    assert anomalies[0].confidence > 0.5
    print(f"[OK] Gradient explosion detected: {anomalies[0].description}")
except Exception as e:
    print(f"[FAIL] Gradient explosion test failed: {e}")
    sys.exit(1)

# Test 3: Vanishing Gradient Detection
print("\n3. Testing vanishing gradient detection...")
try:
    detector = GradientDetector(vanishing_threshold=1e-7, vanishing_consecutive=5)
    
    # Feed vanishing gradients
    anomalies_found = False
    for i in range(10):
        event = BackwardEvent(
            session_id="test",
            step=i,
            layer_name="layer2",
            gradient_norm=1e-8
        )
        anomalies = detector.update(event)
        if anomalies:
            anomalies_found = True
            assert anomalies[0].anomaly_type == AnomalyType.VANISHING_GRADIENT
            print(f"[OK] Vanishing gradient detected at step {i}: {anomalies[0].description}")
            break
    
    assert anomalies_found, "Should detect vanishing gradient"
except Exception as e:
    print(f"[FAIL] Vanishing gradient test failed: {e}")
    sys.exit(1)

# Test 4: Loss Divergence Detection
print("\n4. Testing loss divergence detection...")
try:
    detector = LossDetector(divergence_slope_threshold=0.1, min_samples=5)
    
    # Feed increasing losses
    anomalies_found = False
    for i in range(20):
        event = LossEvent(
            session_id="test",
            step=i,
            loss_value=1.0 + i * 0.5  # Rapidly increasing
        )
        anomalies = detector.update(event)
        if anomalies:
            anomalies_found = True
            assert anomalies[0].anomaly_type == AnomalyType.LOSS_DIVERGENCE
            print(f"[OK] Loss divergence detected at step {i}: {anomalies[0].description}")
            break
    
    assert anomalies_found, "Should detect loss divergence"
except Exception as e:
    print(f"[FAIL] Loss divergence test failed: {e}")
    sys.exit(1)

# Test 5: Loss Plateau Detection
print("\n5. Testing loss plateau detection...")
try:
    detector = LossDetector(
        plateau_slope_threshold=1e-4,
        plateau_variance_threshold=1e-6,
        min_samples=10,
        rolling_window=30
    )
    
    # Feed flat losses
    anomalies_found = False
    for i in range(40):
        event = LossEvent(
            session_id="test",
            step=i,
            loss_value=2.5 + (i % 2) * 0.0001  # Almost flat
        )
        anomalies = detector.update(event)
        if anomalies:
            anomalies_found = True
            assert anomalies[0].anomaly_type == AnomalyType.LOSS_PLATEAU
            print(f"[OK] Loss plateau detected at step {i}: {anomalies[0].description}")
            break
    
    assert anomalies_found, "Should detect loss plateau"
except Exception as e:
    print(f"[FAIL] Loss plateau test failed: {e}")
    sys.exit(1)

# Test 6: Shape Mismatch Detection
print("\n6. Testing shape mismatch detection...")
try:
    detector = ShapeDetector()
    
    # Feed shape mismatch event
    event = ShapeEvent(
        session_id="test",
        step=5,
        layer_name="fc1",
        expected_shape=(32, 128),
        actual_shape=(32, 64),
        is_mismatch=True,
        mismatch_reason="Dimension 1 mismatch: expected 128, got 64"
    )
    anomalies = detector.update(event)
    assert len(anomalies) == 1, "Should detect shape mismatch"
    assert anomalies[0].anomaly_type == AnomalyType.SHAPE_MISMATCH
    assert anomalies[0].confidence > 0.9
    print(f"[OK] Shape mismatch detected: {anomalies[0].description}")
except Exception as e:
    print(f"[FAIL] Shape mismatch test failed: {e}")
    sys.exit(1)

# Test 7: Main Orchestrator
print("\n7. Testing main AnomalyDetector orchestrator...")
try:
    detector = AnomalyDetector()
    
    # Feed mixed events
    events = [
        BackwardEvent(session_id="test", step=1, layer_name="layer1", gradient_norm=1.0),
        LossEvent(session_id="test", step=1, loss_value=2.0),
        BackwardEvent(session_id="test", step=2, layer_name="layer1", gradient_norm=200.0),  # Explosion
        ShapeEvent(
            session_id="test",
            step=3,
            layer_name="fc1",
            expected_shape=(10, 20),
            actual_shape=(10, 30),
            is_mismatch=True,
            mismatch_reason="Test mismatch"
        ),
    ]
    
    all_anomalies = []
    for event in events:
        anomalies = detector.update(event)
        all_anomalies.extend(anomalies)
    
    assert len(all_anomalies) >= 2, f"Should detect at least 2 anomalies, got {len(all_anomalies)}"
    
    # Check that different types were detected
    types_detected = {a.anomaly_type for a in all_anomalies}
    assert AnomalyType.GRADIENT_EXPLOSION in types_detected, "Should detect gradient explosion"
    assert AnomalyType.SHAPE_MISMATCH in types_detected, "Should detect shape mismatch"
    
    print(f"[OK] Orchestrator detected {len(all_anomalies)} anomalies:")
    for anomaly in all_anomalies:
        anomaly_type_str = anomaly.anomaly_type.value if hasattr(anomaly.anomaly_type, 'value') else str(anomaly.anomaly_type)
        print(f"  - {anomaly_type_str} at step {anomaly.step}")
except Exception as e:
    print(f"[FAIL] Orchestrator test failed: {e}")
    sys.exit(1)

# Test 8: Deduplication
print("\n8. Testing anomaly deduplication...")
try:
    detector = AnomalyDetector(dedup_window_steps=10)
    
    # Feed same anomaly multiple times
    anomaly_count = 0
    for i in range(15):
        event = BackwardEvent(
            session_id="test",
            step=i,
            layer_name="layer1",
            gradient_norm=200.0  # Always exploding
        )
        anomalies = detector.update(event)
        anomaly_count += len(anomalies)
    
    # Should only emit once per dedup window
    assert anomaly_count <= 2, f"Deduplication failed: got {anomaly_count} anomalies"
    print(f"[OK] Deduplication working: {anomaly_count} anomalies emitted for 15 events")
except Exception as e:
    print(f"[FAIL] Deduplication test failed: {e}")
    sys.exit(1)

# Test 9: Layer Independence
print("\n9. Testing layer independence...")
try:
    # Verify Layer 2 does not import from Layer 3 or Layer 4
    import anomaly.detectors.detector as detector_module
    import anomaly.detectors.gradient_detector as grad_module
    import anomaly.detectors.loss_detector as loss_module
    
    forbidden_imports = ['bob', 'api', 'extension', 'reports']
    
    for module in [detector_module, grad_module, loss_module]:
        module_dict = dir(module)
        for forbidden in forbidden_imports:
            assert forbidden not in module_dict, f"Layer 2 should not import {forbidden}"
    
    print("[OK] Layer 2 is independent (no imports from bob/api/extension/reports)")
except Exception as e:
    print(f"[FAIL] Layer independence test failed: {e}")
    sys.exit(1)

# Test 10: Classifier
print("\n10. Testing AnomalyClassifier...")
try:
    anomaly = AnomalyClassifier.classify_gradient_explosion(
        session_id="test",
        step=10,
        layer_name="layer1",
        gradient_norm=150.0,
        threshold=100.0,
        rolling_mean=5.0,
        rolling_std=2.0
    )
    assert isinstance(anomaly, AnomalyEvent)
    assert anomaly.anomaly_type == AnomalyType.GRADIENT_EXPLOSION
    assert 0.0 <= anomaly.confidence <= 1.0
    assert "gradient_norm" in anomaly.metrics
    print(f"[OK] Classifier creates valid AnomalyEvent (confidence={anomaly.confidence:.2f})")
except Exception as e:
    print(f"[FAIL] Classifier test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("LAYER 2 VERIFICATION COMPLETE")
print("=" * 60)
print("[OK] All 10 tests passed")
print("\nLayer 2 components verified:")
print("  - AnomalyDetector (main orchestrator)")
print("  - GradientDetector (explosion + vanishing)")
print("  - LossDetector (divergence + plateau)")
print("  - ShapeDetector (mismatch)")
print("  - AnomalyClassifier (event construction)")
print("\nReady for Layer 3: IBM Bob Integration")

# Made with Bob
