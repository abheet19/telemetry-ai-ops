from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response=client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "telemetry_ai_ops" 

def test_telemetry():
    response = client.get("/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "device" in data
    assert isinstance(data["signal_strength"], float)
    assert isinstance(data["osnr"], float)
    assert isinstance(data["temperature"], float)

def test_ingest_valid_payload(monkeypatch):
   
    # Mock AIAnalyzer response to isolate FastAPI logic
    from app.ai import ai_analyzer
    monkeypatch.setattr(
        ai_analyzer.AIAnalyzer, "analyze_telemetry", lambda self, data: {"status": "mocked", "issues": []}
    )

    payload = {
        "device_id": "switch_1",
        "wavelength": 1550.1,
        "osnr": 25.0,
        "ber": 1e-8,
        "power_dbm": -2.5
    }

    response = client.post("/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "queued_packets" in data
    assert data["status"] == "success"
    assert "ai_insights" in data

def test_ingest_invalid_payload():
    bad_payload = {
        "device_id": "switch_1",
        # Missing wavelength, osnr, etc.
    }

    response = client.post("/ingest", json=bad_payload)
    assert response.status_code == 422  # Unprocessable Entity (validation error)
