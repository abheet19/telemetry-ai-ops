from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.routes.telemetry import queue

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


def test_batch_ingest():
    payload = [
        {"device_id": "switch_1", "wavelength": 1550.3, "osnr": 30.0, "ber": 1e-9, "power_dbm": -20.5},
        {"device_id": "amp_2", "wavelength": 1550.5, "osnr": 18.5, "ber": 1e-3, "power_dbm": -23.1}
    ]
    response = client.post("/ingest/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["count"] == 2

@pytest.mark.asyncio
async def test_fetch_all_telemetry(monkeypatch):
   
    response = client.get("/telemetry/fetch")

    assert response.status_code == 200, "Expected 200 OK response"

    data = response.json()

    assert "device_count" in data
    assert "data" in data
    assert isinstance(data["device_count"], int)
    assert isinstance(data["data"], list)

    assert data["device_count"] == len(data["data"])

    for record in data["data"]:
        assert "device_id" in record
        assert "osnr" in record
        assert "ber" in record
        assert "wavelength" in record
        assert "power_dbm" in record

        assert isinstance(record["device_id"], str)
        assert isinstance(record["osnr"], float)
        assert isinstance(record["ber"], float)
        assert isinstance(record["wavelength"], float)
        assert isinstance(record["power_dbm"], float)

        assert 10.0 <= record["osnr"] <= 40.0
        assert 1e-10 <= record["ber"] <= 1e-2
        assert 1500.0 <= record["wavelength"] <= 1560.0


def test_clear_queue():
    #Ensure a clean queue before testing
    queue.clear()
    assert queue.size() == 0  # sanity check before starting

    queue.enqueue({"device_id": "switch1", "osnr": 30.1})
    queue.enqueue({"device_id": "switch2", "osnr": 31.1})
    assert len(queue.queue) == 2  # sanity check

    response = client.delete("/queue/clear")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Telemetry queue cleared."

    assert queue.size() == 0