import os
import json
import re
import tempfile
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from services.api_client import call_kolosal

KB_PATH = os.getenv("KB_PATH")
_kb_lock = threading.Lock()

# Definisi waktu kedaluwarsa KB dalam menit
KB_EXPIRY_MINUTES = 20


def _ensure_kb_exists() -> None:
    if not os.path.exists(KB_PATH):
        try:
            with open(KB_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to create KB file: {e}")


def _load_kb() -> List[Dict[str, Any]]:
    _ensure_kb_exists()
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Failed to read KB: {e}")
        return []


def _write_kb_atomic(kb_list: List[Dict[str, Any]]) -> None:
    tmpfd, tmppath = tempfile.mkstemp(prefix="kb_", suffix=".json", dir=".")
    try:
        with os.fdopen(tmpfd, "w", encoding="utf-8") as tf:
            json.dump(kb_list, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
        os.replace(tmppath, KB_PATH)
    except Exception as e:
        print(f"Failed to write KB atomically: {e}")
        try:
            if os.path.exists(tmppath):
                os.remove(tmppath)
        except Exception:
            pass


def _parse_idr_range(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        try:
            return int(text)
        except Exception:
            return None

    s = str(text).lower().strip()
    s = s.replace("rp", "").replace(" ", "").replace(".", "")
    s = s.replace("k", "000").replace("rb", "000")
    s = s.replace("jt", "000000").replace("juta", "000000")
    s = s.replace("m", "000000")
    
    nums = re.findall(r"\d+", s.replace(",", ""))
    
    if not nums:
        return None
    
    if len(nums) == 1:
        try:
            return int(nums[0])
        except Exception:
            return None
            
    try:
        low = int(nums[0])
        high = int(nums[1])
        return (low + high) // 2
    except Exception:
        return None


def _kb_lookup(code: str) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    code = code.upper()
    kb = _load_kb()
    for item in kb:
        if not isinstance(item, dict):
            continue
        if item.get("code", "").upper() == code:
            return item
    return None


def _build_kb_entry(code: str, summary: str, estimated_cost_idr: Optional[int],
                     estimated_cost_text: Optional[str], urgency: str, sources: List[str]) -> Dict[str, Any]:
    return {
        "code": code.upper(),
        "summary": summary,
        "estimated_cost_idr": int(estimated_cost_idr) if estimated_cost_idr is not None else None,
        "estimated_cost_text": estimated_cost_text,
        "urgency": urgency,
        "sources": sources,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }


def _is_kb_expired(kb_entry: Dict[str, Any]) -> bool:
    """Memeriksa apakah entri KB sudah kadaluwarsa (lebih dari KB_EXPIRY_MINUTES)."""
    created_at_str = kb_entry.get("created_at")
    if not created_at_str:
        return True
        
    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", ""))
        time_elapsed = datetime.utcnow() - created_at
        return time_elapsed > timedelta(minutes=KB_EXPIRY_MINUTES)
    except Exception as e:
        print(f"Error parsing KB timestamp: {e}")
        return True 


def analyze_damage(
    dtc_code: Optional[str], 
    temp: int, 
    vehicle_model: Optional[str],
    tps_percent: Optional[float] = None, 
    batt_volt: Optional[float] = None, 
    o2_volt: Optional[float] = None, 
    map_kpa: Optional[int] = None
) -> Dict[str, Any]:
    dtc_code = dtc_code.upper() if dtc_code else None
    kb_entry = None
    
    try:
        if dtc_code:
            kb_entry = _kb_lookup(dtc_code)
            
            if kb_entry and not _is_kb_expired(kb_entry):
                print(f"DEBUG: Menggunakan KB Cache untuk DTC {dtc_code}.")
                return {
                    "summary": str(kb_entry.get("summary", "")),
                    "estimated_cost_idr": int(kb_entry.get("estimated_cost_idr") or 0),
                    "estimated_cost_text": kb_entry.get("estimated_cost_text"),
                    "urgency": kb_entry.get("urgency", "Sedang"),
                    "sources": [f"kb:{dtc_code.upper()}"]
                }
        kb_context = None 
        
        
        ai_result = call_kolosal(
            dtc_code, 
            temp, 
            vehicle_model,
            tps_percent=tps_percent,  
            batt_volt=batt_volt,     
            o2_volt=o2_volt,        
            map_kpa=map_kpa           
        )
        
        if not ai_result:
            if kb_entry:
                 print(f"DEBUG: AI gagal, menggunakan KB lama (expired) untuk DTC {dtc_code}.")
                 return {
                    "summary": f"AI gagal. Menggunakan data KB lama ({kb_entry.get('created_at')}). " + str(kb_entry.get("summary", "")),
                    "estimated_cost_idr": int(kb_entry.get("estimated_cost_idr") or 0),
                    "estimated_cost_text": kb_entry.get("estimated_cost_text"),
                    "urgency": kb_entry.get("urgency", "Sedang"),
                    "sources": [f"kb-expired:{dtc_code.upper()}"]
                 }
            
            return {
                "summary": f"AI gagal. Tidak ada KB untuk {dtc_code or 'DTC Tidak Diketahui'}.",
                "estimated_cost_idr": 0,
                "estimated_cost_text": None,
                "urgency": "Sedang",
                "sources": ["mock"]
            }
        
        est_int = ai_result.get("estimated_cost_idr")
        est_text = ai_result.get("estimated_cost_text")

        if est_text and (est_int is None):
            parsed = _parse_idr_range(est_text)
            if parsed is not None:
                est_int = parsed

        if est_int is None:
            est_int = 0

        
        entry = _build_kb_entry(
            code=dtc_code or "UNKNOWN",
            summary=ai_result.get("summary", ""),
            estimated_cost_idr=est_int,
            estimated_cost_text=est_text,
            urgency=ai_result.get("urgency", "Sedang"),
            sources=ai_result.get("sources", ["kolosal"])
        )

        if dtc_code:
            with _kb_lock:
                kb_list = _load_kb()
                
                existing_index = next(
                    (i for i, it in enumerate(kb_list) if isinstance(it, dict) and it.get("code", "").upper() == entry["code"].upper()), 
                    -1
                )
                
                if existing_index != -1:
                    kb_list[existing_index] = entry
                else:
                    kb_list.append(entry)
                
                try:
                    _write_kb_atomic(kb_list)
                    print(f"DEBUG: KB entry untuk {dtc_code} berhasil diupdate/disimpan.")
                except Exception as e:
                    print(f"Failed to persist KB entry: {e}")

        return {
            "summary": entry["summary"],
            "estimated_cost_idr": int(entry["estimated_cost_idr"] or 0),
            "estimated_cost_text": entry.get("estimated_cost_text"),
            "urgency": entry.get("urgency", "Sedang"),
            "sources": entry.get("sources", ["kolosal"])
        }

    except Exception as e:
        print(f"analyze_damage fatal error: {e}")
        return {
            "summary": f"AI gagal total: {e}",
            "estimated_cost_idr": 0,
            "estimated_cost_text": None,
            "urgency": "Tidak diketahui",
            "sources": ["fatal-error"]
        }