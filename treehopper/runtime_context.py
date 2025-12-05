# treehopper/runtime_context.py
from typing import Optional
import contextvars

# Per-task (per-run) run_id stored in context
_RUN_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "treehopper_run_id", default=None
)


def set_run_id(run_id: str):
    """Set run_id for the current async context."""
    return _RUN_ID_CTX.set(run_id)


def get_run_id() -> Optional[str]:
    """Return run_id scoped to this async task (or None)."""
    return _RUN_ID_CTX.get()


def reset_run_id(token):
    """Reset run_id back to previous state (required in FastAPI)."""
    _RUN_ID_CTX.reset(token)
