from fastapi import APIRouter, HTTPException
from app.models import TelemetryRecord
from app.core.telemetry_queue import TelemetryQueue
from app.ai.ai_analyzer import AIAnalyzer
from app.utils.async_fetcher import collect_all_devices
from fastapi import BackgroundTasks
from app.services.pipeline import (
    telemetry_pipeline,
    is_pipeline_running,
    set_pipeline_state,
)
import asyncio

router = APIRouter()
queue = TelemetryQueue()
analyzer = AIAnalyzer()


@router.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "telemetry_ai_ops"}


@router.get("/telemetry", tags=["telemetry"])
def get_sample_telemetry():
    return {
        "device": "optical_switch_1",
        "signal_strength": -22.5,
        "osnr": 35.8,
        "temperature": 72.1,
    }


@router.get("/telemetry/fetch", tags=["telemetry"])
async def fetch_all_telemetry():
    devices = ["switch_1", "switch_2", "amplifier_1", "transponder_1"]
    results = await collect_all_devices(devices)
    return {"device_count": len(results), "data": [r.model_dump() for r in results]}


@router.post("/ingest", tags=["telemetry"])
async def ingest_telemetry(record: TelemetryRecord):
    """
    Ingest telemetry data:
    - Validates input
    - Queues it
    - Runs AI health analysis
    """
    try:
        record_dict = record.model_dump()
        queue.enqueue(record_dict)
        insights = analyzer.analyze_telemetry(record_dict)
        return {
            "status": "success",
            "queued_packets": queue.size(),
            "ai_insights": insights,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/status", tags=["telemetry"])
def queue_status():
    return {"queued_packets": queue.size()}


@router.delete("/queue/clear", tags=["telemetry"])
def clear_queue():
    queue.clear()
    return {"status": "success", "message": "Telemetry queue cleared."}


@router.post("/ingest/batch", tags=["telemetry"])
async def ingest_batch(
    records: list[TelemetryRecord], background_tasks: BackgroundTasks
):
    try:
        for record in records:
            queue.enqueue(record.model_dump())
            background_tasks.add_task(analyzer.run_ai_analysis, record.model_dump())
        return {"status": "queued", "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/toggle", tags=["pipeline"])
async def toggle_pipeline(state: bool):
    """Enable or disable background pipeline."""
    set_pipeline_state(state)
    if state:
        asyncio.create_task(telemetry_pipeline())
        return {
            "status": "ok",
            "pipeline_running": True,
            "message": "Pipeline Restarted",
        }
    else:
        return {
            "status": "ok",
            "pipeline_running": False,
            "message": "Pipeline Stopped",
        }


@router.get("/pipeline/status", tags=["pipeline"])
def pipeline_status():
    return {
        "running": is_pipeline_running(),
        "message": (
            "Pipeline active and fetching telemetry"
            if is_pipeline_running()
            else "Pipeline stopped"
        ),
    }
