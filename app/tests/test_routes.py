from fastapi.testclient import TestClient
from app.main import app
import pytest
from app.routes.telemetry import queue
from unittest.mock import AsyncMock
import httpx

client = TestClient(app)


def test_health():
    response = client.get("/health")
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


def test_queue_status():
    queue.clear()
    assert queue.size() == 0

    queue.enqueue({"device_id": "switch1", "osnr": 30.1})
    response = client.get("/queue/status")

    assert response.status_code == 200
    body = response.json()
    assert body["queued_packets"] == 1


def test_pipeline_toggle():
    response = client.post("/pipeline/toggle?state=false")
    assert response.status_code == 200
    assert response.json()["pipeline_running"] is False

    response2 = client.post("/pipeline/toggle?state=true")
    assert response2.status_code == 200
    assert response2.json()["pipeline_running"] is True


def test_pipeline_status():
    res = client.get("/pipeline/status")
    assert res.status_code == 200
    assert "running" in res.json()


@pytest.mark.asyncio
async def test_ingest_batch_success(monkeypatch):
    # Create fake AIBatcher with mock enqueue
    fake_batcher = AsyncMock()
    fake_batcher.enqueue = AsyncMock()

    # Import the running FastAPI app from main
    from app.main import app

    # Inject fake batcher into app state so route finds it
    app.state.ai_batcher = fake_batcher

    # Prevent queue real behavior (just no-op)
    monkeypatch.setattr("app.routes.telemetry.queue.enqueue", lambda x: None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Make sure this matches TelemetryRecord required fields exactly.
        sample_records = [
            {
                "device_id": "switch_1",
                "wavelength": 1550.3,
                "osnr": 34.8,
                "ber": 1e-9,
                "power_dbm": -21.5,
            },
            {
                "device_id": "amp_1",
                "wavelength": 1550.5,
                "osnr": 28.2,
                "ber": 2e-8,
                "power_dbm": -19.7,
            },
        ]
        resp = await ac.post("/ingest/batch", json=sample_records)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["count"] == 2
    assert fake_batcher.enqueue.await_count == 2


@pytest.mark.asyncio
async def test_ingest_batch_failure(monkeypatch):
    """Test batch ingestion when AI batcher throws exception."""
    fake_batcher = AsyncMock()
    fake_batcher.enqueue = AsyncMock(side_effect=RuntimeError("AI batcher failed"))

    from app.main import app

    app.state.ai_batcher = fake_batcher

    monkeypatch.setattr("app.routes.telemetry.queue.enqueue", lambda x: None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        sample_records = [
            {
                "device_id": "switch_1",
                "wavelength": 1550.3,
                "osnr": 34.8,
                "ber": 1e-9,
                "power_dbm": -21.5,
            }
        ]
        resp = await ac.post("/ingest/batch", json=sample_records)

    assert resp.status_code == 500
    data = resp.json()
    assert "detail" in data
    assert "AI batcher failed" in data["detail"]
