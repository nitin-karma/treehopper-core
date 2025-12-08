# tests/unit/test_cancellation.py
import importlib


def test_cancellation_module_importable():
    mod = importlib.import_module("treehopper.treehopper_cancellation")
    assert hasattr(mod, "create_cancel_marker")
    assert hasattr(mod, "cancel_batch")
