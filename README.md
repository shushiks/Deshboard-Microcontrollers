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
  "water_temperature": 20.1,
  "ph": null,
  "raindrop": null,
  "latitude": 43.1155,
  "longitude": 131.8855,
  "captured_at": null
}
```

- `received_at` is always created by the server from the computer's UTC clock.
- `captured_at` is optional and is intended for measurements restored from an SD card.
- Coordinates are optional. They must be configured on the ESP32 or supplied by a GPS; a local IP address cannot provide reliable coordinates.
- Missing sensors may be omitted (or sent as JSON `null`); the dashboard displays them as `—`.
- The legacy `alcohol` field is accepted and migrated to `air_quality`.
- `air_quality` is the raw ADC signal from MQ-5 (0–4095), not ppm or a gas percentage.
- Alert thresholds are device configuration and are changed only through `PATCH /api/devices/{device_id}`.

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
