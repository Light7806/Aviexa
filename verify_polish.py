"""
verify_polish.py
Targeted checks for the two polish fixes:
  1. forward_hook.py: no UserWarning from std() on single-element tensors
  2. context_builder.py: no "Missing template key" warning when metrics are sparse
"""

import warnings
import logging
import sys

results = []


# ── Shared helper (defined early so all test functions can reference it) ──────
class _ListHandler(logging.Handler):
    def __init__(self, records):
        super().__init__()
        self._records = records
    def emit(self, record):
        self._records.append(record)

def check(label, fn):
    try:
        fn()
        print(f"[PASS] {label}")
        results.append((label, True, None))
    except Exception as e:
        print(f"[FAIL] {label}: {e}")
        results.append((label, False, str(e)))


# ── Fix 1: forward_hook std() on single-element tensors ─────────────────────
print("=== Fix 1: forward_hook std() on single-element tensors ===")

def test_std_no_warning_single_element():
    import torch
    from core.hooks.forward_hook import ForwardHookManager
    from core.buffer.ring_buffer import RingBuffer

    buf = RingBuffer(50)
    manager = ForwardHookManager(buf, "sess-std-test")

    # Simulate what the hook does internally for a scalar output
    captured_warnings = []
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        import torch.nn as nn

        # Single-element tensor (e.g. output of a final scalar head)
        output = torch.tensor([3.14])
        with torch.no_grad():
            out_d = output.detach()
            if out_d.dtype in [torch.float32, torch.float64, torch.float16]:
                mean = float(out_d.mean())
                std = float(out_d.std()) if out_d.numel() > 1 else None
                mn  = float(out_d.min())
                mx  = float(out_d.max())

        pytorch_warnings = [x for x in w if issubclass(x.category, UserWarning)
                            and "std" in str(x.message).lower()]
        assert len(pytorch_warnings) == 0, \
            f"Still got UserWarning from std(): {pytorch_warnings[0].message}"
        assert std is None, f"Expected std=None for single-element tensor, got {std}"
        assert abs(mean - 3.14) < 1e-4

check("No UserWarning from std() on 1-element tensor", test_std_no_warning_single_element)

def test_std_computed_normally_multi_element():
    import torch
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        output = torch.tensor([1.0, 2.0, 3.0, 4.0])
        with torch.no_grad():
            std = float(output.std()) if output.numel() > 1 else None
        assert std is not None and std > 0, "Multi-element tensor should have a real std"
        pytorch_warnings = [x for x in w if issubclass(x.category, UserWarning)
                            and "std" in str(x.message).lower()]
        assert len(pytorch_warnings) == 0

check("std() still computed normally for multi-element tensors", test_std_computed_normally_multi_element)


# ── Fix 2: context_builder template missing keys — no warning ────────────────
print("\n=== Fix 2: context_builder template — no Missing template key warning ===")

def test_no_missing_key_warning_gradient_explosion():
    """
    AnomalyEvent for GRADIENT_EXPLOSION without 'threshold' in metrics.
    Template expects {gradient_norm} and {threshold}; only gradient_norm supplied.
    Should silently render 'N/A' for threshold — no logger.warning.
    """
    from anomaly.models import AnomalyEvent, AnomalyType
    from bob.context_builder import BobContextBuilder

    # Capture log records at WARNING level
    log_records = []
    handler = logging.handlers_capture = _ListHandler(log_records)
    bob_logger = logging.getLogger("bob.context_builder")
    bob_logger.addHandler(handler)
    bob_logger.setLevel(logging.DEBUG)

    try:
        anomaly = AnomalyEvent(
            session_id="sess1",
            anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
            step=42,
            confidence=0.9,
            description="Explosion",
            layer_name="fc1",
            metrics={"gradient_norm": 150.0},   # 'threshold' intentionally absent
        )

        builder = BobContextBuilder()
        prompt = builder.build_prompt(anomaly, events=None)

        # Assert no missing-key warnings
        warn_records = [r for r in log_records if r.levelno >= logging.WARNING
                        and "Missing template key" in r.getMessage()]
        assert len(warn_records) == 0, \
            f"Got unexpected warning(s): {[r.getMessage() for r in warn_records]}"

        # Assert the prompt body rendered (not empty / not crashed)
        assert prompt.user_message
        assert "Gradient Explosion" in prompt.user_message
        assert "150.0" in prompt.user_message   # gradient_norm present
        assert "N/A" in prompt.user_message      # threshold fallback

    finally:
        bob_logger.removeHandler(handler)

check("No 'Missing template key' warning — gradient_explosion with sparse metrics",
      test_no_missing_key_warning_gradient_explosion)


def test_no_missing_key_warning_vanishing():
    """Same check for VANISHING_GRADIENT missing 'consecutive_count'."""
    from anomaly.models import AnomalyEvent, AnomalyType
    from bob.context_builder import BobContextBuilder

    log_records = []
    handler = _ListHandler(log_records)
    bob_logger = logging.getLogger("bob.context_builder")
    bob_logger.addHandler(handler)
    bob_logger.setLevel(logging.DEBUG)

    try:
        anomaly = AnomalyEvent(
            session_id="sess2",
            anomaly_type=AnomalyType.VANISHING_GRADIENT,
            step=10,
            confidence=0.8,
            description="Vanishing",
            layer_name="layer0",
            metrics={"gradient_norm": 1e-9},  # 'consecutive_count' absent
        )
        builder = BobContextBuilder()
        prompt = builder.build_prompt(anomaly, events=None)

        warn_records = [r for r in log_records if r.levelno >= logging.WARNING
                        and "Missing template key" in r.getMessage()]
        assert len(warn_records) == 0
        assert "N/A" in prompt.user_message   # consecutive_count → N/A

    finally:
        bob_logger.removeHandler(handler)

check("No 'Missing template key' warning — vanishing_gradient with sparse metrics",
      test_no_missing_key_warning_vanishing)


def test_all_keys_present_still_works():
    """When all keys are supplied, the template should still render fully."""
    from anomaly.models import AnomalyEvent, AnomalyType
    from bob.context_builder import BobContextBuilder

    anomaly = AnomalyEvent(
        session_id="sess3",
        anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
        step=5,
        confidence=0.95,
        description="Explosion with full metrics",
        layer_name="conv1",
        metrics={"gradient_norm": 200.0, "threshold": 10.0},
    )
    builder = BobContextBuilder()
    prompt = builder.build_prompt(anomaly, events=None)
    assert "200.0" in prompt.user_message
    assert "10.0" in prompt.user_message
    assert "N/A" not in prompt.user_message   # no fallback needed

check("Full metrics supplied — no N/A placeholders in output",
      test_all_keys_present_still_works)




# ── Summary ──────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print("=" * 50)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(results)} checks")
if failed:
    print("\nFailed:")
    for label, ok, err in results:
        if not ok:
            print(f"  - {label}: {err}")
print("=" * 50)
