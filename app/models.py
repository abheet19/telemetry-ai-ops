from pydantic import BaseModel, Field
from typing import Optional


class TelemetryRecord(BaseModel):
    device_id: str = Field(..., description="Unique ID of network device")
    wavelength: float = Field(
        ..., gt=1500, lt=1600, description="Optical Wavelength in nm"
    )
    osnr: float = Field(
        ..., gt=0, lt=40, description="Optical Signal to Noise Ratio in dB"
    )
    ber: float = Field(..., ge=0, le=1, description="Bit Error Rate (0 to 1)")
    power_dbm: Optional[float] = Field(None, description="Optical Power in dBm")
