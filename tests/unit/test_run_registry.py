# tests/unit/test_run_registry.py
import importlib

# import pytest


def test_run_registry_module_importable():
    mod = importlib.import_module("treehopper.utils.run_registry")
    assert hasattr(mod, "record_chain_run")
