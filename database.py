from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from databases import Database
import os
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and "+asyncpg" in DATABASE_URL:
    SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
else:
    SYNC_DATABASE_URL = DATABASE_URL

engine = create_engine(SYNC_DATABASE_URL)

database = Database(DATABASE_URL)


Base = declarative_base()

class TelemetryRecord(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)

    rpm = Column(Integer, nullable=False)
    temp = Column(Integer, nullable=False)
    dtc_code = Column(String, nullable=True)
    tps_percent = Column(Float, nullable=True)
    batt_volt = Column(Float, nullable=True)
    fuel_trim_short = Column(Float, nullable=True)
    o2_volt = Column(Float, nullable=True)
    map_kpa = Column(Float, nullable=True)
    vehicle_model = Column(String, nullable=True)

    status = Column(JSON, nullable=False) 
    ai_advice = Column(JSON, nullable=True)

def create_db_and_tables():
    Base.metadata.create_all(engine)