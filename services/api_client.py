import os
import json
import re
from typing import Optional, Dict, Any
from openai import OpenAI

API_KEY_TOKEN = os.getenv("KOLOSAL_API_KEY")
BASE_URL = os.getenv("KOLOSAL_BASE_URL")
MODEL = os.getenv("AI_MODEL")

kolosal_client: Optional[OpenAI] = None
try:
    if API_KEY_TOKEN:
        kolosal_client = OpenAI(api_key=API_KEY_TOKEN, base_url=BASE_URL)
    else:
        print("Warning: KOLOSAL_API_KEY or OPENAI_API_KEY not found. API calls will fail.")
except Exception as e:
    print(f"KOLASAL CLIENT INIT ERROR: {e}")
    kolosal_client = None


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text or not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


from typing import Optional, Dict, Any

def call_kolosal(
    dtc_code: Optional[str], 
    temp: int, 
    vehicle_model: Optional[str],
    tps_percent: Optional[float] = None, 
    batt_volt: Optional[float] = None, 
    o2_volt: Optional[float] = None, 
    map_kpa: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    
    if kolosal_client is None:
        return None

    system_prompt = "You are an experienced automotive mechanic. Respond in Indonesian. Reply with JSON only."
    
    sensor_data = (
        f"TPS: {tps_percent or '-'} %\n"
        f"Tegangan Aki: {batt_volt or '-'} V\n"
        f"O2 Sensor: {o2_volt or '-'} V\n"
        f"MAP/Tekanan Intake: {map_kpa or '-'} kPa\n"
    )

    user_prompt = (
        f"Data kendaraan:\n"
        f"Model: {vehicle_model or '-'}\n"
        f"DTC: {dtc_code or '-'}\n"
        f"Suhu mesin: {temp} C\n"
        f"--- Data Sensor Real-Time ---\n"
        f"{sensor_data}"
        f"-----------------------------\n\n"
        "Tugas Anda: Analisis masalah, berikan ringkasan kerusakan (summary), estimasi biaya perbaikan (estimated_cost_text), dan tingkat urgensi (urgency).\n"
        "Output JSON keys: summary, estimated_cost_text (string, e.g. 'Rp 1.200.000 - Rp 2.000.000' or '1.2jt'), urgency (string: 'Rendah', 'Sedang', 'Tinggi')."
    )

    try:
        resp = kolosal_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0
        )
        raw_content = resp.choices[0].message.content
        parsed = _extract_json_from_text(raw_content)

        if not parsed:
            return {"summary": raw_content.strip(), "estimated_cost_idr": None, "estimated_cost_text": None, "urgency": "Sedang", "sources": ["kolosal-raw"]}

        summary = parsed.get("summary") or parsed.get("description") or ""
        cost_text = None
        cost_raw = None

        if "estimated_cost_text" in parsed:
            cost_text = parsed.get("estimated_cost_text")
        elif "estimated_cost_idr" in parsed:
            cost_raw = parsed.get("estimated_cost_idr")
            cost_text = str(cost_raw) if cost_raw is not None else None
        elif "estimated_cost" in parsed:
            cost_text = parsed.get("estimated_cost")
        elif "cost" in parsed:
            cost_text = parsed.get("cost")

        est_int = None
        if cost_raw is not None and isinstance(cost_raw, (int, float)):
            try:
                est_int = int(cost_raw)
            except Exception:
                pass

        urgency = parsed.get("urgency") or parsed.get("level") or "Sedang"

        return {
            "summary": summary,
            "estimated_cost_idr": est_int,
            "estimated_cost_text": cost_text,
            "urgency": urgency,
            "sources": ["kolosal"]
        }

    except Exception as e:
        print(f"Kolosal call failed: {e}")
        return None