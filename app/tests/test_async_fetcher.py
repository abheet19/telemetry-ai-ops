import importlib
from unittest.mock import patch, AsyncMock
import app.utils.async_fetcher as async_fetcher
import pytest

@pytest.mark.asyncio
async def test_fetch_telemetry():
    device_id = "switch_test"
    record = await async_fetcher.fetch_telemetry(device_id)
    assert record.device_id == device_id
    assert 18.0 <= record.osnr <= 36.0
    assert record.ber in [1e-9, 1e-6, 1e-3]
    assert -22.0 <= record.power_dbm <= 18.0

@pytest.mark.asyncio
async def test_collect_all_devices():
    devices = ["switch_1", "switch_2", "amplifier_1"]
    results = await async_fetcher.collect_all_devices(devices)
    assert len(results) == 3
    for record in results:
        assert record.osnr >= 18.0
        assert record.ber in [1e-9, 1e-6, 1e-3]

def test_main_block(monkeypatch):
    # Mock TelemetryRecord-like objects
    mock_results = [AsyncMock(model_dump=lambda: {"device_id": "mock"}) for _ in range(5)]

    # Define a **normal** function (not async) that returns our mock results
    def mock_run(coro):
        # We can optionally run the coroutine to avoid warnings
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(coro)
            loop.close()
        except Exception:
            pass
        return mock_results

    # Patch asyncio.run with our synchronous mock
    monkeypatch.setattr(async_fetcher.asyncio, "run", mock_run)

    # Run main() and ensure it executes the print loop without errors
    async_fetcher.main()