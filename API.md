# OtoSense Backend API

## Ringkasan
- Base URL: `http://localhost:8000`
- Autentikasi: Tidak ada (MVP)
- Format: JSON
- Dokumentasi interaktif tersedia di `http://localhost:8000/docs` dan OpenAPI JSON di `http://localhost:8000/openapi.json`

## Endpoint

### POST `/api/telemetry`
Mengirim data telemetry kendaraan dan mendapatkan status evaluasi serta (opsional) saran AI.

Body (JSON):
- `vehicle_id` (string)
- `timestamp` (string, ISO 8601)
- `rpm` (int, ≥ 0)
- `speed` (int, ≥ 0)
- `temp` (int)
- `dtc_code` (string|null)
- `vehicle_model` (string|null)

Response 200 (JSON):
- Semua field input
- `status` (array string): `NORMAL`, `OVERHEAT`, `OVERSPEED`, `CRITICAL`
- `ai_advice` (objek, opsional):
  - `summary` (string)
  - `estimated_cost_idr` (int, opsional)
  - `estimated_cost_text` (string, opsional)
  - `urgency` (string, opsional)
  - `sources` (array string, opsional)

Aturan (rule-based):
- `OVERHEAT` jika `temp > 100`
- `OVERSPEED` jika `rpm > 6000`
- `CRITICAL` jika ada anomali di atas atau `dtc_code` tidak null
- `NORMAL` jika tidak ada anomali

Pemanggilan AI:
- AI dipanggil jika `status` mengandung `CRITICAL` atau `dtc_code` ada
- Menggunakan `knowledge_base.json` untuk retrieval lokal; jika `OPENAI_API_KEY` tersedia akan mencoba OpenAI `gpt-4o-mini`, jika gagal akan fallback ke ringkasan lokal

Contoh (PowerShell):
```
$body = @{ vehicle_id="TEST-003"; timestamp="2025-12-03T10:00:00Z"; rpm=2000; speed=50; temp=105; dtc_code="P0300"; vehicle_model="Toyota Avanza" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/telemetry -ContentType "application/json" -Body $body
```

### GET `/api/status/{vehicle_id}`
Mengambil data terakhir kendaraan tertentu.

Response 200 (JSON): Telemetry + `status` + (opsional) `ai_advice`

Response 404:
```
{ "detail": "Vehicle not found" }
```

Contoh:
```
curl http://localhost:8000/api/status/TEST-003
```

### GET `/health`
Health check.

Response 200:
```
{ "status": "ok" }
```

## Konfigurasi
- `.env`:
  - `OPENAI_API_KEY=sk-...`
  - `ALLOW_ORIGINS=http://localhost:8000` (comma-separated untuk banyak origin)

## Skema Model
- Validasi input: `d:\hackathon\Damage Detection\models.py:6–13`
- `AIAdvice` (respons AI): `d:\hackathon\Damage Detection\models.py:16–21`

## Referensi Implementasi
- Evaluasi status: `d:\hackathon\Damage Detection\main.py:45–57`
- Integrasi AI di endpoint: `d:\hackathon\Damage Detection\main.py:60–67`
- CORS via `.env`: `d:\hackathon\Damage Detection\main.py:19–24`
- Knowledge base loading: `d:\hackathon\Damage Detection\services\ai_service.py:11–24`
- Analisis AI (OpenAI + fallback): `d:\hackathon\Damage Detection\services\ai_service.py:57–69, 86–103`

## Kesalahan Umum
- 404 pada `GET /api/status/{vehicle_id}`: Belum ada telemetry untuk `vehicle_id` tersebut. Kirim `POST /api/telemetry` dulu.
- `ai_advice` kosong: Status tidak `CRITICAL` dan `dtc_code` kosong, atau `error_code` tidak ada di `knowledge_base.json`.

## Catatan
- Penyimpanan state in-memory (`vehicle_store`); akan kosong saat server restart. Kirim telemetry ulang untuk seed data.
