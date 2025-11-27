from pathlib import Path
import requests

BASE_URL = "http://localhost:1567"
API_KEY = {"x-api-key": "demo-key-123"}

SAMPLE_TEXT_FILE = Path(__file__).parent / "chipset_report.txt"


def test_001_formatter_file_upload():
    assert SAMPLE_TEXT_FILE.exists(), "Missing test file chipset_report.txt"

    with open(SAMPLE_TEXT_FILE, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/v1/agents/formatter",
            headers=API_KEY,
            files={"file": ("chipset_report.txt", f, "text/plain")},
        )
    print("Formatter response:", r.text)
    assert r.status_code == 200
    data = r.json()
    assert "formatted" in data
    assert len(data["formatted"]) > 10  # ensure not empty
    return data["formatted"]


def test_002_summarizer():
    formatted = test_001_formatter_file_upload()

    r = requests.post(
        f"{BASE_URL}/api/v1/agents/summarizer",
        headers=API_KEY,
        json={"document_text": formatted},
    )
    print("Summarizer response:", r.text)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert len(data["summary"]) > 20  # ensure meaningful text
    return data["summary"]


def test_003_sentiment():
    summary = test_002_summarizer()
    r = requests.post(
        f"{BASE_URL}/api/v1/agents/sentiment",
        headers=API_KEY,
        json={"summary": summary},
    )
    print("Sentiment response:", r.text)
    assert r.status_code == 200
    data = r.json()
    assert "sentiment" in data
    assert data["sentiment"] in ("optimistic", "neutral", "pessimistic")
    assert float(data["confidence"]) >= 0
    return data


def test_004_advisor():
    summary = test_002_summarizer()
    sentiment = test_003_sentiment()

    r = requests.post(
        f"{BASE_URL}/api/v1/agents/advisor",
        headers=API_KEY,
        json={
            "formatted": {"executive_summary": summary},
            "sentiment": sentiment,
        },
    )
    print("Advisor response:", r.text)
    assert r.status_code == 200
    data = r.json()
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) >= 1
    return data


def test_005_emailer():
    summary = test_002_summarizer()
    sentiment = test_003_sentiment()
    recommendations = test_004_advisor()

    r = requests.post(
        f"{BASE_URL}/api/v1/agents/emailer",
        headers=API_KEY,
        json={
            "formatted": {"executive_summary": summary},
            "sentiment": sentiment,
            "recommendations": recommendations,
        },
    )
    print("Emailer response:", r.text)
    assert r.status_code == 200
    data = r.json()
    assert "email_html" in data
    assert data["email_html"].startswith("<")  # sanity HTML check
    assert "</h2>" in data["email_html"]


def test_006_full_pipeline_via_chain():
    assert SAMPLE_TEXT_FILE.exists()

    body = {
        "chain": [
            {
                "path": "/api/v1/agents/formatter",
                "params": {"file_path": str(SAMPLE_TEXT_FILE)},
            },
            {"path": "/api/v1/agents/summarizer", "params": {}},
            {"path": "/api/v1/agents/sentiment", "params": {}},
            {"path": "/api/v1/agents/advisor", "params": {}},
            {"path": "/api/v1/agents/emailer", "params": {}},
        ]
    }

    r = requests.post(
        f"{BASE_URL}/api/v1/dev/chain",
        headers=API_KEY,
        json=body,
    )
    print("Chain output:", r.text)
    assert r.status_code == 200

    result = r.json()
    assert "result" in result
    assert "email_html" in result["result"]
    assert "<h3>Recommended Actions</h3>" in result["result"]["email_html"]
