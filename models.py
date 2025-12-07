from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TelemetryIn(BaseModel):
    vehicle_id: str = Field(..., min_length=1)
    timestamp: datetime
    rpm: int = Field(..., ge=0)
    speed: int = Field(..., ge=0)
    temp: int
    tps_percent: Optional[float] = None
    batt_volt: Optional[float] = None
    fuel_trim_short: Optional[float] = None
    o2_volt: Optional[float] = None
    map_kpa: Optional[int] = None
    dtc_code: Optional[str] = None
    vehicle_model: Optional[str] = None


class AIAdvice(BaseModel):
    summary: str
    estimated_cost_idr: Optional[int] = None
    estimated_cost_text: Optional[str] = None
    urgency: Optional[str] = None
    sources: Optional[list[str]] = None


class TelemetryOut(TelemetryIn):
    status: list[str]
    ai_advice: Optional[AIAdvice] = None

