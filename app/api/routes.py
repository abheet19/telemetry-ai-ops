from fastapi import APIRouter

router =APIRouter()

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


