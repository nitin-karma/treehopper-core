def test_health_endpoint(client):
    r = client.get("/api/v1/sys/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_rejected(client):
    r = client.get("/api/v1/dev/agents")
    assert r.status_code in (401, 403)


def test_list_agents_with_key(client, auth_headers):
    r = client.get("/api/v1/dev/agents", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_chain_list(client, auth_headers):
    r = client.get("/api/v1/dev/chains", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
