from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, func
from app.core.database import Base


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


class AIResult(Base):
    __tablename__ = "ai_results"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    osnr = Column(Float)
    ber = Column(Float)
    power_dbm = Column(Float)
    wavelength = Column(Float)
    status = Column(String)
    message = Column(String)
    ai_output = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
