from typing import Any, Dict
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder

from models import TelemetryIn, TelemetryOut
from services.ai_service import analyze_damage


app = FastAPI(
    title="OtoSense API",
    description="Backend IoT + AI untuk pemeliharaan armada UMKM.",
    version="0.1.0",
)

_origins_env = os.getenv("ALLOW_ORIGINS")
_allow_origins = ["*"] if not _origins_env else [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vehicle_store: Dict[str, Dict[str, Any]] = {}
ws_by_vehicle: Dict[str, list[WebSocket]] = {}
ws_global: list[WebSocket] = []


def _compute_status(
    rpm: int, 
    temp: int, 
    dtc_code: str | None,
    tps_percent: float | None,
    batt_volt: float | None,
    fuel_trim_short: float | None,
) -> list[str]:
    statuses: list[str] = []
    critical = False
    
    if temp > 100:
        statuses.append("OVERHEAT")
        critical = True
    if rpm > 6000:
        statuses.append("OVERSPEED")
    
    if dtc_code:
        critical = True
        
    if batt_volt is not None and batt_volt < 11.5:
        statuses.append("LOW_BATTERY")
        
    if rpm < 1000 and tps_percent is not None and tps_percent > 5.0:
        statuses.append("IDLE_TPS_ERROR")
        
    if fuel_trim_short is not None and (fuel_trim_short > 15.0 or fuel_trim_short < -15.0):
        statuses.append("AFR_ISSUE")
        
    if critical:
        statuses.append("CRITICAL")
    if not statuses:
        return ["NORMAL"]
    return statuses


@app.post("/api/telemetry", response_model=TelemetryOut, tags=["Telemetry"])
async def ingest_telemetry(payload: TelemetryIn):
    statuses = _compute_status(
        payload.rpm, 
        payload.temp, 
        payload.dtc_code,
        payload.tps_percent,
        payload.batt_volt,
        payload.fuel_trim_short
    )

    record = payload.dict(exclude_none=True)
    record["timestamp"] = payload.timestamp.isoformat()
    record["status"] = statuses

    if ("CRITICAL" in statuses) or payload.dtc_code:
        ai_result = analyze_damage(
            payload.dtc_code,
            payload.temp,
            payload.vehicle_model,
            payload.tps_percent, 
            payload.batt_volt, 
            payload.o2_volt, 
            payload.map_kpa
        )
        record["ai_advice"] = ai_result
    else:
        record["ai_advice"] = None

    vehicle_store[payload.vehicle_id] = record

    encoded = jsonable_encoder(record)

    if payload.vehicle_id in ws_by_vehicle:
        dead_ws = []
        for ws in ws_by_vehicle[payload.vehicle_id]:
            try:
                await ws.send_json(encoded)
            except:
                dead_ws.append(ws)
        for ws in dead_ws:
            ws_by_vehicle[payload.vehicle_id].remove(ws)

    dead_ws = []
    for ws in ws_global:
        try:
            await ws.send_json(encoded)
        except:
            dead_ws.append(ws)
    for ws in dead_ws:
        ws_global.remove(ws)

    return encoded


@app.get("/api/status/{vehicle_id}", response_model=TelemetryOut, tags=["Telemetry"])
async def get_status(vehicle_id: str):
    record = vehicle_store.get(vehicle_id)
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return jsonable_encoder(record)

@app.get("/api/vehicles", tags=["Telemetry"])
async def list_vehicles():
    """Mengembalikan daftar semua ID kendaraan yang aktif di vehicle_store."""
    return list(vehicle_store.keys())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{vehicle_id}")
async def ws_vehicle(websocket: WebSocket, vehicle_id: str):
    await websocket.accept()
    ws_by_vehicle.setdefault(vehicle_id, []).append(websocket)

    if vehicle_id in vehicle_store:
        await websocket.send_json(jsonable_encoder(vehicle_store[vehicle_id]))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if vehicle_id in ws_by_vehicle and websocket in ws_by_vehicle[vehicle_id]:
            ws_by_vehicle[vehicle_id].remove(websocket)


@app.websocket("/ws")
async def ws_all(websocket: WebSocket):
    await websocket.accept()
    ws_global.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_global:
            ws_global.remove(websocket)
