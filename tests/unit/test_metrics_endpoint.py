# tests/unit/test_metrics_endpoint.py
def test_metrics_endpoint(app_client):
    if app_client is None:
        import pytest

        pytest.skip("app not importable")
    resp = app_client.get("/metrics")
    assert resp.status_code == 200
    d = resp.json()
    assert "counters" in d and "gauges" in d
