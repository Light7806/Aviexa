"""
verify_layer1.py
Full smoke-test and import check for Aviexa Layer 1 foundation.
Run with: python verify_layer1.py
"""

import sys
print("Python:", sys.version)

results = []

def check(label, fn):
    try:
        fn()
        print(f"[PASS] {label}")
        results.append((label, True, None))
    except Exception as e:
        print(f"[FAIL] {label}: {e}")
        results.append((label, False, str(e)))


# ───────────────── IMPORT CHECKS ─────────────────
print("\n=== IMPORT CHECKS ===")

def imp_anomaly_models():
    from anomaly.models import (
        EventType, AnomalyType, TelemetryEvent,
        ForwardEvent, BackwardEvent, LossEvent,
        MemoryEvent, ShapeEvent, AnomalyEvent
    )

check("anomaly.models imports", imp_anomaly_models)

def imp_ring_buffer():
    from core.buffer.ring_buffer import RingBuffer

check("core.buffer.ring_buffer imports", imp_ring_buffer)

def imp_forward_hook():
    from core.hooks.forward_hook import ForwardHookManager, attach_forward_hooks

check("core.hooks.forward_hook imports", imp_forward_hook)

def imp_backward_hook():
    from core.hooks.backward_hook import BackwardHookManager, attach_backward_hooks

check("core.hooks.backward_hook imports", imp_backward_hook)

def imp_loss_hook():
    from core.hooks.loss_hook import LossTracker, create_loss_tracker

check("core.hooks.loss_hook imports", imp_loss_hook)

def imp_shape_tracker():
    from core.tracker.shape_tracker import ShapeTracker

check("core.tracker.shape_tracker imports", imp_shape_tracker)

def imp_memory_tracker():
    from core.tracker.memory_tracker import MemoryTracker

check("core.tracker.memory_tracker imports", imp_memory_tracker)

def imp_session():
    from core.session import AviexaSession

check("core.session imports", imp_session)

def imp_core_top():
    from core import AviexaSession

check("core (top-level) imports", imp_core_top)


# ───────────────── FUNCTIONAL TESTS ─────────────────
print("\n=== FUNCTIONAL SMOKE TESTS ===")

def test_ring_buffer_basics():
    from core.buffer.ring_buffer import RingBuffer
    from anomaly.models import LossEvent

    buf = RingBuffer(capacity=5)
    for i in range(7):
        ev = LossEvent(session_id="test", step=i, loss_value=float(i))
        buf.append(ev)
    assert len(buf) == 5, f"Expected 5, got {len(buf)}"
    assert buf.dropped_count == 2, f"Expected 2 dropped, got {buf.dropped_count}"
    assert buf.total_written == 7
    snap = buf.snapshot()
    assert len(snap) == 5
    latest = buf.latest(3)
    assert len(latest) == 3

check("RingBuffer: capacity/overflow/snapshot/latest/dropped_count", test_ring_buffer_basics)

def test_event_types():
    from anomaly.models import EventType, AnomalyType
    assert EventType.FORWARD == "forward"
    assert EventType.BACKWARD == "backward"
    assert EventType.LOSS == "loss"
    assert EventType.MEMORY == "memory"
    assert EventType.SHAPE == "shape"
    assert EventType.SESSION == "session"
    all_anomaly = [
        AnomalyType.GRADIENT_EXPLOSION, AnomalyType.VANISHING_GRADIENT,
        AnomalyType.LOSS_DIVERGENCE, AnomalyType.LOSS_PLATEAU,
        AnomalyType.SHAPE_MISMATCH, AnomalyType.MEMORY_LEAK, AnomalyType.UNKNOWN
    ]
    assert len(all_anomaly) == 7

check("EventType (6) + AnomalyType (7) all values present", test_event_types)

def test_anomaly_event_confidence():
    from anomaly.models import AnomalyEvent, AnomalyType
    ev = AnomalyEvent(
        session_id="test", anomaly_type=AnomalyType.GRADIENT_EXPLOSION,
        step=1, confidence=0.95, description="explosion detected"
    )
    assert ev.anomaly_id is not None
    assert ev.confidence == 0.95

check("AnomalyEvent: UUID + confidence field", test_anomaly_event_confidence)

def test_shape_tracker():
    from core.tracker.shape_tracker import ShapeTracker
    from core.buffer.ring_buffer import RingBuffer

    buf = RingBuffer(100)
    st = ShapeTracker(buf, "sess1")
    st.validate_shape("layer1", (32, 128))   # register first
    ok = st.validate_shape("layer1", (64, 128))  # dynamic batch OK
    assert ok is True
    bad = st.validate_shape("layer1", (32, 256))  # feature dim mismatch
    assert bad is False
    evs = buf.snapshot()
    mismatches = [e for e in evs if hasattr(e, "is_mismatch") and e.is_mismatch]
    assert len(mismatches) >= 1, "Expected at least one mismatch event in buffer"

check("ShapeTracker: register / dynamic-batch OK / feature-dim mismatch", test_shape_tracker)

def test_loss_tracker():
    import torch
    from core.hooks.loss_hook import LossTracker
    from core.buffer.ring_buffer import RingBuffer

    buf = RingBuffer(100)
    lt = LossTracker(buf, "sess2")
    lt.record_loss(torch.tensor(1.23), step=5)
    lt.record_loss(float("nan"), step=6)
    evs = buf.snapshot()
    assert len(evs) == 2
    assert abs(evs[0].loss_value - 1.23) < 1e-4
    assert evs[1].has_nan is True

check("LossTracker: tensor + nan detection", test_loss_tracker)

def test_memory_tracker():
    from core.tracker.memory_tracker import MemoryTracker
    from core.buffer.ring_buffer import RingBuffer

    buf = RingBuffer(100)
    mt = MemoryTracker(buf, "sess3")
    mt.record_memory(step=1)
    evs = buf.snapshot()
    assert len(evs) == 1

check("MemoryTracker: record_memory (CPU-only safe)", test_memory_tracker)

def test_session_lifecycle():
    import torch
    from core.session import AviexaSession

    s = AviexaSession(buffer_capacity=1000)
    assert s.session_id is not None
    assert s.is_active is False

    s.start()
    assert s.is_active is True

    s.increment_step()
    s.record_loss(torch.tensor(0.5))
    s.record_memory()

    evs = s.get_events()
    assert len(evs) >= 1

    stats = s.get_stats()
    assert "session_id" in stats
    assert "buffer_stats" in stats
    assert stats["current_step"] == 1

    s.stop()
    assert s.is_active is False

check("AviexaSession: full lifecycle (start/step/record_loss/record_memory/stop)", test_session_lifecycle)

def test_session_context_manager():
    from core.session import AviexaSession

    with AviexaSession() as s2:
        s2.start()
        s2.increment_step()
    assert not s2.is_active

check("AviexaSession: context manager (__enter__/__exit__)", test_session_context_manager)

def test_session_no_model():
    import torch
    from core.session import AviexaSession

    s = AviexaSession()
    s.start()   # no model, no optimizer
    s.increment_step()
    s.record_loss(torch.tensor(2.5))
    s.stop()

check("AviexaSession: works without model/optimizer", test_session_no_model)

def test_ring_buffer_extend_and_clear():
    from core.buffer.ring_buffer import RingBuffer
    from anomaly.models import LossEvent

    buf = RingBuffer(20)
    evs = [LossEvent(session_id="t", step=i, loss_value=float(i)) for i in range(10)]
    buf.extend(evs)
    assert len(buf) == 10
    buf.clear()
    assert len(buf) == 0

check("RingBuffer: extend + clear", test_ring_buffer_extend_and_clear)

def test_no_layer1_imports_bob_api():
    """Verify Layer 1 does NOT import from bob, api, extension, or anomaly.detectors."""
    import importlib, types
    forbidden = ["bob", "api", "extension", "reports", "anomaly.detectors"]
    modules_to_check = [
        "core.session",
        "core.buffer.ring_buffer",
        "core.hooks.forward_hook",
        "core.hooks.backward_hook",
        "core.hooks.loss_hook",
        "core.tracker.shape_tracker",
        "core.tracker.memory_tracker",
    ]
    for mod_name in modules_to_check:
        mod = importlib.import_module(mod_name)
        src_file = getattr(mod, "__file__", "") or ""
        if src_file:
            code = open(src_file).read()
            for forbidden_mod in forbidden:
                assert f"import {forbidden_mod}" not in code and f"from {forbidden_mod}" not in code, \
                    f"{mod_name} illegally imports from {forbidden_mod}"

check("Layer independence: no forbidden imports (bob/api/extension/reports)", test_no_layer1_imports_bob_api)

# ───────────────── SUMMARY ─────────────────
print("\n" + "="*50)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(results)} checks")
if failed:
    print("\nFailed checks:")
    for label, ok, err in results:
        if not ok:
            print(f"  - {label}: {err}")
print("="*50)
