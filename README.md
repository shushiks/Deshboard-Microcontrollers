# ESP Fleet Monitor

FastAPI/Jinja platform for receiving and visualizing telemetry from multiple ESP32 devices.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>.

## ESP32 payload

Every controller posts to the same endpoint. `device_id` identifies the sender and must be unique.

```http
POST /api/metrics
Content-Type: application/json
X-API-Key: your-secret
```

```json
{
  "device_id": "esp-greenhouse-01",
  "device_name": "Теплица 01",
  "air_quality": 1340,
  "humidity": 61.4,
  "air_temperature": 24.8,
  "air_pressure": 1008.4,
  "water_temperature": 20.1,
  "ph": null,
  "raindrop": null,
  "latitude": 43.1155,
  "longitude": 131.8855,
  "captured_at": "2026-09-22T03:25:00Z",
  "sample_id": "9a4b124f47db91ee"
}
```

- `received_at` is always created by the server from the computer's UTC clock.
- `captured_at` is the ESP's UTC measurement time when its clock has synchronized. The dashboard uses it for history; without it, server receipt time is used.
- `sample_id` prevents duplicate rows if an SD-backed reading is retried after a lost HTTP response.
- BMP280 supplies air temperature and atmospheric pressure in hPa, **not humidity**. DHT11 supplies humidity.
- Coordinates are optional. They must be configured on the ESP32 or supplied by a GPS; a local IP address cannot provide reliable coordinates.
- Missing sensors may be omitted (or sent as JSON `null`); the dashboard displays them as `—`.
- The legacy `alcohol` field is accepted and migrated to `air_quality`.
- `air_quality` is the raw ADC signal from MQ-5 (0–4095), not ppm or a gas percentage.
- Alert thresholds are device configuration and are changed only through `PATCH /api/devices/{device_id}`.

## Optional microSD buffer on ESP32

The firmware uses SPI: SCK→GPIO18, MISO→GPIO19, MOSI→GPIO23, CS→GPIO13, GND→GND. Confirm the exact module's required VCC and logic voltage before connecting power: the ESP32 pins are 3.3 V, while some SD breakouts require a 5 V supply and include a regulator/level shifter.

Each ready sensor reading is sent immediately; readings ready in the same `loop()` pass share one request. If Wi-Fi or HTTP fails, the JSON is written as a separate file in `/queue` on the SD card. After connectivity returns, saved files are replayed and each file is deleted only after a 2xx response. The server de-duplicates retries via `sample_id`. If the SD module is absent, the ESP keeps only the latest unsent values in RAM; a reboot can then lose them. A cold boot without network time cannot assign a reliable original timestamp to offline measurements.

## API

- `POST /api/metrics` — save one reading.
- `POST /api/devices/{device_id}/heartbeat` — mark a controller as online without saving a sensor reading.
- `GET /api/devices` — devices with latest readings and alert state.
- `GET /api/devices/{device_id}/history?hours=24` — saved history.
- `PATCH /api/devices/{device_id}` — update name, coordinates or temperature threshold.
- `GET /health` — health check.

SQLite data is stored in `data/telemetry.db`.

## Docker Compose

```bash
cp .env.example .env
# Replace ESP_API_KEY in .env with a strong random secret.
docker compose up --build -d
```

The database is persisted in the `telemetry_data` volume. Production startup fails when `ESP_API_KEY` is missing. ESP32 requests must include the same key:

```cpp
http.addHeader("X-API-Key", "your-secret");
```

## Heartbeat

Send a lightweight heartbeat every 30 seconds independently of sensor measurements:

```cpp
const unsigned long HEARTBEAT_INTERVAL = 30000;
unsigned long previousHeartbeatMillis = 0;

void sendHeartbeat() {
  HTTPClient http;
  http.begin("http://SERVER_IP:8000/api/devices/esp-greenhouse-01/heartbeat");
  http.addHeader("X-API-Key", "your-secret");
  http.POST("");
  http.end();
}
```

The dashboard marks the device offline after 90 seconds without a heartbeat. Sensor metrics may be sent on any separate schedule.
