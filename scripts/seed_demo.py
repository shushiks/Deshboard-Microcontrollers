"""Create deterministic demo telemetry without touching real devices."""

import math
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import DATABASE_PATH  # noqa: E402
from app.repository import initialize_database  # noqa: E402


DEVICE_ID = "esp-demo-01"


def main() -> None:
    initialize_database()
    random.seed(2026)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=30)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("DELETE FROM devices WHERE device_id = ?", (DEVICE_ID,))
        connection.execute(
            """
            INSERT INTO devices (
                device_id, name, latitude, longitude, temperature_threshold, created_at, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (DEVICE_ID, "Демо-резервуар", 43.1155, 131.8855, 30.0, start.isoformat(), now.isoformat()),
        )

        for index in range(30 * 8 + 1):
            moment = start + timedelta(hours=index * 3)
            daily = math.sin(index * math.pi / 4 - 1.2)
            slow = math.sin(index * math.pi / 28)

            # Sensors deliberately report at different rates. Rounded values also
            # create legitimate repeated measurements for UI testing.
            air_temperature = round(24.5 + 4.8 * daily + 1.5 * slow, 1)
            water_temperature = round(21.0 + 1.7 * slow, 1) if index % 4 == 0 else None
            humidity = round(62 - 10 * daily + random.uniform(-2, 2), 1) if index % 2 == 0 else None
            air_quality = round(1450 + 260 * slow + random.uniform(-45, 45))
            ph = round(7.1 + 0.25 * math.sin(index / 13), 2) if index % 8 == 0 else None
            raindrop = (280 if 80 <= index <= 92 or 174 <= index <= 180 else 1023) if index % 3 == 0 else None

            connection.execute(
                """
                INSERT INTO readings (
                    device_id, air_quality, humidity, air_temperature, water_temperature,
                    ph, raindrop, captured_at, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    DEVICE_ID, air_quality, humidity, air_temperature, water_temperature,
                    ph, raindrop, moment.isoformat(), moment.isoformat(),
                ),
            )

    print(f"Created {DEVICE_ID}: 241 readings from {start.isoformat()} to {now.isoformat()}")


if __name__ == "__main__":
    main()
