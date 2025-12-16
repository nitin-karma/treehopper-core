def test_detached_chain_run(client, auth_headers):
    payload = {"file_path": "shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}

    r = client.post(
        "/api/v1/chains/dynamic_doc_intel/run",
        headers={
            **auth_headers,
            "x-treehopper-detached": "1",
        },
        json=payload,
    )

    assert r.status_code == 200
    data = r.json()

    assert data["detached"] is True
    assert "run_id" in data
