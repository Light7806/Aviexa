# tests/integration/test_full_pipeline.py
# End-to-end: run bug_gradient_explosion.py through Aviexa
# Assert: anomaly detected -> Bob called -> fix returned
# Uses mock BobClient to avoid real API calls in CI
