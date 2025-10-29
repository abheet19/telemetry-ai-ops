import asyncio
import httpx
from app.core.telemetry_queue import TelemetryQueue

queue = TelemetryQueue()
PIPELINE_RUNNING = True


def set_pipeline_state(state: bool):
    global PIPELINE_RUNNING
    PIPELINE_RUNNING = state


def is_pipeline_running():
    return PIPELINE_RUNNING


async def telemetry_pipeline():
    """
    Simulates real ingestion:
    - Fetches telemetry from /telemetry/fetch
    - Sends all telemetry as one batch to /ingest/batch
    - Waits and repeats in a loop
    """
    print("[Pipeline] Starting telemetry ingestion loop...")

    while is_pipeline_running():
        # Step 1 -fetch telemetry from local API
        try:
            async with httpx.AsyncClient() as client:
                fetch_resp = await client.get("http://localhost:8000/telemetry/fetch")
                fetch_resp.raise_for_status()
                telemetry_data = fetch_resp.json()["data"]

            if not telemetry_data:
                print("[Pipeline] No telemetry data fetched. Skipping batch.")
                await asyncio.sleep(5)
                continue

            # Step 2 - Send entire telemetry batch to /ingest/batch
            async with httpx.AsyncClient() as client:
                batch_resp = await client.post(
                    "http://localhost:8000/ingest/batch", json=telemetry_data
                )
                batch_resp.raise_for_status()

            print(
                f"[Pipeline] Batch of {len(telemetry_data)} telemetry records ingested successfully."
            )

            await asyncio.sleep(10)

        except Exception as e:
            print(f"[Pipeline Error] {e}")
            await asyncio.sleep(5)  # Simulates pipeline delay
