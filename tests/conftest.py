# tests/conftest.py
import sys
import types

# import json
# import shutil
# import time
# import tempfile
# import pathlib
import pytest
from fastapi.testclient import TestClient


# ---- Mock external AI provider modules to avoid network calls ----
def _make_dummy_module(name: str):
    m = types.SimpleNamespace()
    # add a no-op "Client" or function attributes as needed
    m.Client = lambda *a, **kw: None
    m.create = lambda *a, **kw: {"id": "mock"}
    return m


@pytest.fixture(autouse=True, scope="session")
def mock_ai_providers():
    """Install fake `openai`, `anthropic`, `google.generativeai` modules."""
    fake_openai = types.ModuleType("openai")
    fake_openai.ChatCompletion = types.SimpleNamespace(
        create=lambda **kw: {"choices": [{"message": {"content": "mock"}}]}
    )
    fake_openai.create = lambda **kw: {"id": "mock"}
    sys.modules.setdefault("openai", fake_openai)

    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Client = lambda *a, **kw: None
    sys.modules.setdefault("anthropic", fake_anthropic)

    # google.generativeai: make the parent package and the submodule
    g_parent = types.ModuleType("google")
    g_gen = types.ModuleType("google.generativeai")
    g_gen.get_text = lambda **kw: {"candidates": [{"content": "mock"}]}
    sys.modules.setdefault("google", g_parent)
    sys.modules.setdefault("google.generativeai", g_gen)

    yield

    for k in ("openai", "anthropic", "google", "google.generativeai"):
        if k in sys.modules:
            sys.modules.pop(k)


# ---- Temporary treehopper registry (isolated tests) ----
@pytest.fixture
def tmp_registry(tmp_path, monkeypatch):
    # create a fake ~/.treehopper path inside tmp
    root = tmp_path / ".treehopper"
    registry = root / "registry"
    runtime = root / "runtime"
    registry.mkdir(parents=True)
    runtime.mkdir(parents=True)

    monkeypatch.setenv("TH_ROOT", str(root))
    monkeypatch.setenv("RUNTIME_DIR", str(runtime))
    # If your code uses TH_ROOT/REGISTRY_DIR constants, monkeypatch those or set env and import after set
    yield {"root": root, "registry": registry, "runtime": runtime}


# ---- FastAPI TestClient if app importable ----
@pytest.fixture
def app_client():
    try:
        from treehopper.chain_runtime_app import app  # noqa
    except Exception:
        # fallback: if no app, return None
        yield None
        return
    client = TestClient(app)
    yield client
