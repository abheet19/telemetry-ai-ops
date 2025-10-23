from fastapi import APIRouter,HTTPException
from app.models import TelemetryRecord
from app.core.telemetry_queue import TelemetryQueue
from app.ai.ai_analyzer import AIAnalyzer

router =APIRouter()
queue = TelemetryQueue()
analyzer = AIAnalyzer()

@router.get("/health",tags=["system"])
def health_check():
    return {"status":"ok","service":"telemetry_ai_ops"}

@router.get("/telemetry",tags=["telemetry"])
def get_sample_telemetry():
    return{
        "device":"optical_switch_1",
        "signal_strength": -22.5,
        "osnr":35.8,
        "temperature":72.1
    }
@router.post("/ingest")
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
            "ai_insights": insights
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))