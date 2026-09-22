import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "telemetry.db"))

DEFAULT_TEMPERATURE_THRESHOLD = 30.0
ONLINE_TIMEOUT_SECONDS = 90
# Temperature is sampled every five minutes; keep its alert until the next
# expected sample (with room for one missed cycle), while heartbeat tracks online.
TEMPERATURE_STALE_SECONDS = 11 * 60
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
ESP_API_KEY = os.getenv("ESP_API_KEY")
WRITE_RATE_LIMIT_PER_MINUTE = int(os.getenv("WRITE_RATE_LIMIT_PER_MINUTE", "120"))
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", "16384"))
GEOCODING_URL = os.getenv("GEOCODING_URL", "https://nominatim.openstreetmap.org/reverse")
GEOCODING_USER_AGENT = os.getenv("GEOCODING_USER_AGENT", "ESP-Fleet-Monitor/1.0 (educational project)")
