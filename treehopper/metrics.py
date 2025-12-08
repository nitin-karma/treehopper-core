# treehopper/metrics.py
from fastapi import APIRouter
from treehopper.logging import metrics as _metrics

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """
    Returns a JSON snapshot of in-process metrics.
    Prometheus scraping would hit this endpoint in advanced setups (or expose text format).
    """
    return _metrics().snapshot()
