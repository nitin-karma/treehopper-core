def test_simple_chain_run(client, auth_headers):
    payload = {"file_path": "shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}

    r = client.post(
        "/api/v1/chains/doc_flow/run",
        headers=auth_headers,
        json=payload,
    )

    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "results" in data
