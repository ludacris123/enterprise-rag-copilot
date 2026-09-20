from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

def test_grounded_chat():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"question": "When must I claim domestic travel?", "filters": {"department": "finance"}})
        assert response.status_code == 200
        body = response.json()
        assert body["citations"]
        assert "trace_id" in body

def test_upload_requires_supported_type():
    with TestClient(app) as client:
        response = client.post("/api/v1/documents", files={"file": ("x.exe", b"bad", "application/octet-stream")}, data={"department": "security"})
        assert response.status_code == 415
