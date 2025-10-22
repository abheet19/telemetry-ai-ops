from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response=client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" 

def test_telemetry():
    response =client.get('/telemetry')
    assert response.status_code == 200

    data=response.json()
    assert "device" in data
    assert isinstance(data["signal_strength"],float)
