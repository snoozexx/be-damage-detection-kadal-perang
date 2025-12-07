from typing import Any, Dict
import os
import json
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import select
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from database import database, TelemetryRecord
from models import TelemetryIn, TelemetryOut
from services.ai_service import analyze_damage
from utils.auto_migrate import run_migrations


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

@app.on_event("startup")
async def startup():
    await database.connect()
    run_migrations() 

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


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
        
    db_data = {
        "vehicle_id": payload.vehicle_id,
        "timestamp": payload.timestamp.replace(tzinfo=None),
        "rpm": 0,
        "temp": 0,
        "dtc_code": None,
        "tps_percent": None,
        "batt_volt": None,
        "fuel_trim_short": None,
        "o2_volt": None,
        "map_kpa": None,
        "vehicle_model": None,
        "status": statuses,
        "ai_advice": None,
    }

    stmt = insert(TelemetryRecord).values(**db_data)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["vehicle_id"]
    )

    await database.execute(stmt)


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

@app.post("/api/telemetry/db", response_model=TelemetryOut, tags=["Telemetry"])
async def ingest_telemetry_db(payload: TelemetryIn):
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

    ai_result = None
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

    ai_advice_dict = None
    if ai_result:
        if isinstance(ai_result, str):
            try:
                ai_advice_dict = json.loads(ai_result)
            except:
                ai_advice_dict = {"raw": ai_result}
        else:
            ai_advice_dict = ai_result

    record["ai_advice"] = ai_advice_dict  

    db_data = {
        "vehicle_id": payload.vehicle_id,
        "timestamp": payload.timestamp.replace(tzinfo=None),
        "rpm": payload.rpm,
        "temp": payload.temp,
        "dtc_code": payload.dtc_code,
        "tps_percent": payload.tps_percent,
        "batt_volt": payload.batt_volt,
        "fuel_trim_short": payload.fuel_trim_short,
        "o2_volt": payload.o2_volt,
        "map_kpa": payload.map_kpa,
        "vehicle_model": payload.vehicle_model,
        "status": statuses,
        "ai_advice": ai_advice_dict,
    }

    existing = await database.fetch_one(
        select(TelemetryRecord).where(TelemetryRecord.vehicle_id == payload.vehicle_id)
    )

    if existing:
        query = (
            TelemetryRecord
            .__table__
            .update()
            .where(TelemetryRecord.vehicle_id == payload.vehicle_id)
            .values(**db_data)
        )
    else:
        query = TelemetryRecord.__table__.insert().values(**db_data)

    await database.execute(query)

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

    # Send to global websocket
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
    query = (
        select(TelemetryRecord)
        .where(TelemetryRecord.vehicle_id == vehicle_id)
        .order_by(TelemetryRecord.timestamp.desc())
        .limit(1)
    )
    record = await database.fetch_one(query)

    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    record_dict = dict(record)

    if "speed" not in record_dict:
        record_dict["speed"] = 0.0  
    if "ai_advice" not in record_dict:
        record_dict["ai_advice"] = None
    if "status" not in record_dict:
        record_dict["status"] = ["NORMAL"]

    return jsonable_encoder(record_dict)

@app.get("/api/vehicles", tags=["Telemetry"])
async def list_vehicles():
    """Mengembalikan daftar semua ID kendaraan yang aktif di vehicle_store."""
    return list(vehicle_store.keys())

# main.py

@app.get("/api/vehicles/db", tags=["Telemetry"])
async def list_db_vehicles():
    """Mengembalikan daftar semua ID kendaraan unik dari database."""
    
    query = select(TelemetryRecord.vehicle_id.distinct())
    
    results = await database.fetch_all(query)
    
    vehicle_ids = [r['vehicle_id'] for r in results]
    
    return vehicle_ids


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
