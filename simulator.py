import json

import sys
from datetime import datetime, timezone
import argparse
import requests


BASE_URL = "http://localhost:8000"


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_payload(scenario: int):
    if scenario == 1:
        return {
            "vehicle_id": "TEST-001",
            "timestamp": now_iso(),
            "rpm": 3000,
            "speed": 60,
            "temp": 90,
            "dtc_code": None,
            "vehicle_model": "Toyota Avanza",
        }
    if scenario == 2:
        return {
            "vehicle_id": "TEST-002",
            "timestamp": now_iso(),
            "rpm": 6500,
            "speed": 100,
            "temp": 95,
            "dtc_code": None,
            "vehicle_model": "Toyota Avanza",
        }
    if scenario == 3:
        return {
            "vehicle_id": "TEST-003",
            "timestamp": now_iso(),
            "rpm": 2000,
            "speed": 50,
            "temp": 105,
            "dtc_code": "P0300",
            "vehicle_model": "Toyota Avanza",
        }
    raise ValueError("Skenario tidak valid")


def send(payload):
    url = f"{BASE_URL}/api/telemetry"
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def interactive_choose():
    print("Pilih skenario:")
    print("[1] Normal")
    print("[2] Warning (RPM Tinggi)")
    print("[3] Critical (Overheat + DTC P0300)")
    choice = input("Masukkan pilihan [1/2/3]: ").strip()
    if choice not in {"1", "2", "3"}:
        print("Pilihan tidak valid")
        sys.exit(1)
    return int(choice)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3])
    args = parser.parse_args()
    scenario = args.scenario or interactive_choose()
    payload = build_payload(scenario)
    try:
        result = send(payload)
    except requests.RequestException as e:
        print(f"Gagal mengirim: {e}")
        sys.exit(1)
    print("Response:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ai_advice"):
        advice = result["ai_advice"]
        print("\nDiagnosa AI:")
        print(f"Ringkasan: {advice.get('summary')}")
        print(f"Estimasi Biaya (IDR): {advice.get('estimated_cost_idr')}")
        print(f"Urgensi: {advice.get('urgency')}")


if __name__ == "__main__":
    main()

