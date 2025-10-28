import asyncio
import types
import pytest

# Import the module under test
from app.services import pipeline as pipeline_mod


# ---- Helper mocks ----
class MockResponse:
    def __init__(self, json_data=None, status=200):
        self._json = json_data or {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code} error")

    def json(self):
        return self._json

class MockAsyncClient:
    """
    Minimal async context-manager that mimics httpx.AsyncClient used in pipeline.
    Behavior is controlled by passing get_resp and post_resp to the constructor.
    The post() method will set pipeline state to False so the loop stops after one run.
    """
    def __init__(self, get_resp=None, post_resp=None, raise_on_get=False):
        self._get_resp = get_resp
        self._post_resp = post_resp or {"ok": True}
        self._raise_on_get = raise_on_get

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        if self._raise_on_get:
            # Simulate network error
            raise Exception("simulated fetch error")
        return MockResponse(self._get_resp, status=200)

    async def post(self, url, json):
        # stop pipeline after successful post so the loop ends
        pipeline_mod.set_pipeline_state(False)
        return MockResponse(self._post_resp, status=200)

# ---- Test fixtures ----
@pytest.fixture(autouse=True)
def noop_sleep(monkeypatch):
    """Replace asyncio.sleep with a fast no-op to speed tests."""
    async def _nop(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", _nop)
    yield


# ---- Tests ----
def test_set_and_get_pipeline_state():
    # Ensure setter/getter behave
    pipeline_mod.set_pipeline_state(False)
    assert pipeline_mod.is_pipeline_running() is False

    pipeline_mod.set_pipeline_state(True)
    assert pipeline_mod.is_pipeline_running() is True


@pytest.mark.asyncio
async def test_telemetry_pipeline_no_data(monkeypatch, capsys):
    """
    Case: /telemetry/fetch returns {"data": []}
    Expectation:
      - pipeline prints "No telemetry data fetched. Skipping batch."
      - pipeline stops after first loop (MockAsyncClient will call set_pipeline_state(False) only on post,
        so we make get set pipeline state False explicitly inside the mock by using a small wrapper).
    """
    # Prepare a MockAsyncClient that returns empty data and will set pipeline False inside get
    class NoDataClient(MockAsyncClient):
        async def get(self, url):
            # emulate fetch returning empty data and stop pipeline afterwards
            pipeline_mod.set_pipeline_state(False)
            return MockResponse({"data": []}, status=200)

    # Replace httpx.AsyncClient with our mock
    monkeypatch.setattr("httpx.AsyncClient", lambda: NoDataClient(get_resp={"data": []}))

    # Ensure pipeline runs
    pipeline_mod.set_pipeline_state(True)

    # Execute
    await pipeline_mod.telemetry_pipeline()

    # Capture output and assert expected message
    captured = capsys.readouterr()
    assert "[Pipeline] Starting telemetry ingestion loop..." in captured.out
    assert "[Pipeline] No telemetry data fetched. Skipping batch." in captured.out


@pytest.mark.asyncio
async def test_telemetry_pipeline_success_batch(monkeypatch, capsys):
    """
    Case: /telemetry/fetch returns a list of telemetry records, /ingest/batch returns 200.
    Expectation:
      - pipeline posts the batch
      - pipeline prints a success message including batch size
      - pipeline stops (MockAsyncClient.post sets pipeline state False)
    """
    sample_data = [
        {"device_id": "switch_1", "osnr": 30.1, "ber": 1e-9, "wavelength": 1550.1, "power_dbm": -20.0},
        {"device_id": "switch_2", "osnr": 25.4, "ber": 1e-6, "wavelength": 1550.3, "power_dbm": -22.0},
        {"device_id": "amp_1", "osnr": 28.0, "ber": 1e-9, "wavelength": 1550.5, "power_dbm": -18.0},
        {"device_id": "transp_1", "osnr": 21.0, "ber": 1e-3, "wavelength": 1550.7, "power_dbm": -25.0},
    ]

    # Monkeypatch AsyncClient to our Mock that returns sample_data on get and stops pipeline on post
    monkeypatch.setattr("httpx.AsyncClient", lambda: MockAsyncClient(get_resp={"data": sample_data}, post_resp={"status": "ok"}))

    pipeline_mod.set_pipeline_state(True)
    await pipeline_mod.telemetry_pipeline()

    captured = capsys.readouterr()
    assert "[Pipeline] Starting telemetry ingestion loop..." in captured.out
    assert "Batch of 4 telemetry records ingested successfully." in captured.out


@pytest.mark.asyncio
async def test_telemetry_pipeline_fetch_error(monkeypatch, capsys):
    """
    Case: AsyncClient.get raises an exception (network / parsing error).
    Behavior:
      - The mock get() will set the pipeline to False (so the loop will stop after one run),
        then raise an exception to simulate a fetch error.
      - The pipeline should catch the exception and print a '[Pipeline Error]' message.
    """
    # Create a mock client where get() sets pipeline state False and then raises
    class RaisingClient(MockAsyncClient):
        async def get(self, url):
            # Stop the pipeline so the loop exits after handling this exception
            pipeline_mod.set_pipeline_state(False)
            # Simulate network error
            raise Exception("simulated fetch error")

    # Patch httpx.AsyncClient to return our failing client
    monkeypatch.setattr("httpx.AsyncClient", lambda: RaisingClient())

    # Ensure pipeline is on initially
    pipeline_mod.set_pipeline_state(True)

    # Run pipeline; it should handle the raised exception and then exit
    await pipeline_mod.telemetry_pipeline()

    captured = capsys.readouterr()
    assert "[Pipeline] Starting telemetry ingestion loop..." in captured.out
    # Ensure pipeline printed an error message
    assert "[Pipeline Error]" in captured.out or "simulated fetch error" in captured.out.lower()