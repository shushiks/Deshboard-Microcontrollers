from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import DATABASE_PATH, DEFAULT_TEMPERATURE_THRESHOLD, ONLINE_TIMEOUT_SECONDS, TEMPERATURE_STALE_SECONDS
from .geocoding import reverse_geocode
from .schemas import DeviceUpdate, MetricsInput


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                temperature_threshold REAL NOT NULL DEFAULT 30.0,
                address TEXT,
                locality TEXT,
                geocode_attempted_at TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
                air_quality REAL,
                humidity REAL,
                air_temperature REAL,
                air_pressure REAL,
                water_temperature REAL,
                ph REAL,
                raindrop REAL,
                captured_at TEXT,
                sample_id TEXT,
                received_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_device_time
                ON readings(device_id, received_at DESC);
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(devices)")}
        for name, definition in (
            ("address", "TEXT"),
            ("locality", "TEXT"),
            ("geocode_attempted_at", "TEXT"),
        ):
            if name not in columns:
                connection.execute(f"ALTER TABLE devices ADD COLUMN {name} {definition}")
        reading_columns = {row[1] for row in connection.execute("PRAGMA table_info(readings)")}
        for name, definition in (("air_pressure", "REAL"), ("sample_id", "TEXT")):
            if name not in reading_columns:
                connection.execute(f"ALTER TABLE readings ADD COLUMN {name} {definition}")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_readings_sample_id ON readings(device_id, sample_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_readings_device_measured ON readings(device_id, COALESCE(captured_at, received_at) DESC)")


def save_metrics(payload: MetricsInput) -> dict[str, Any]:
    received_at = datetime.now(timezone.utc)
    received_iso = received_at.isoformat()
    captured_iso = payload.captured_at.isoformat() if payload.captured_at else None

    should_geocode = False
    final_latitude = final_longitude = None
    with _connection() as connection:
        current = connection.execute(
            "SELECT * FROM devices WHERE device_id = ?", (payload.device_id,)
        ).fetchone()

        name = payload.device_name or (current["name"] if current else payload.device_id)
        latitude = payload.latitude if payload.latitude is not None else (current["latitude"] if current else None)
        longitude = payload.longitude if payload.longitude is not None else (current["longitude"] if current else None)
        final_latitude, final_longitude = latitude, longitude
        coordinates_changed = current is None or latitude != current["latitude"] or longitude != current["longitude"]
        last_attempt = (
            datetime.fromisoformat(current["geocode_attempted_at"])
            if current and current["geocode_attempted_at"]
            else None
        )
        retry_allowed = last_attempt is None or received_at - last_attempt >= timedelta(days=1)
        address_missing = current is None or current["address"] is None
        should_geocode = (
            latitude is not None
            and longitude is not None
            and (coordinates_changed or (address_missing and retry_allowed))
        )
        threshold = current["temperature_threshold"] if current else DEFAULT_TEMPERATURE_THRESHOLD

        connection.execute(
            """
            INSERT INTO devices (
                device_id, name, latitude, longitude, temperature_threshold, address, locality,
                geocode_attempted_at, created_at, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                name = excluded.name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                temperature_threshold = excluded.temperature_threshold,
                address = CASE WHEN devices.latitude IS excluded.latitude AND devices.longitude IS excluded.longitude THEN devices.address ELSE NULL END,
                locality = CASE WHEN devices.latitude IS excluded.latitude AND devices.longitude IS excluded.longitude THEN devices.locality ELSE NULL END,
                last_seen = excluded.last_seen
            """,
            (payload.device_id, name, latitude, longitude, threshold, None, None, None, received_iso, received_iso),
        )

        cursor = connection.execute(
            """
            INSERT INTO readings (
                device_id, air_quality, humidity, air_temperature, air_pressure, water_temperature,
                ph, raindrop, captured_at, sample_id, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, sample_id) DO NOTHING
            """,
            (
                payload.device_id,
                payload.air_quality,
                payload.humidity,
                payload.air_temperature,
                payload.air_pressure,
                payload.water_temperature,
                payload.ph,
                payload.raindrop,
                captured_iso,
                payload.sample_id,
                received_iso,
            ),
        )
        reading_id = cursor.lastrowid if cursor.rowcount else connection.execute(
            "SELECT id FROM readings WHERE device_id = ? AND sample_id = ?",
            (payload.device_id, payload.sample_id),
        ).fetchone()["id"]

    if should_geocode and final_latitude is not None and final_longitude is not None:
        with _connection() as connection:
            cached = connection.execute(
                """
                SELECT address, locality FROM devices
                WHERE latitude = ? AND longitude = ? AND address IS NOT NULL
                LIMIT 1
                """,
                (final_latitude, final_longitude),
            ).fetchone()
        place = dict(cached) if cached else reverse_geocode(final_latitude, final_longitude)
        with _connection() as connection:
            connection.execute(
                "UPDATE devices SET address = ?, locality = ?, geocode_attempted_at = ? WHERE device_id = ?",
                (
                    place["address"] if place else None,
                    place["locality"] if place else None,
                    received_iso,
                    payload.device_id,
                ),
            )

    return {
        "id": reading_id,
        "device_id": payload.device_id,
        "sample_id": payload.sample_id,
        "received_at": received_iso,
        "captured_at": captured_iso,
    }


def list_devices() -> list[dict[str, Any]]:
    averaged_metrics = (
        "air_temperature", "air_pressure", "water_temperature", "humidity",
        "air_quality", "ph", "raindrop",
    )
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT d.*,
                   (SELECT air_quality FROM readings WHERE device_id = d.device_id AND air_quality IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_quality,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND air_quality IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_quality_at,
                   (SELECT humidity FROM readings WHERE device_id = d.device_id AND humidity IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS humidity,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND humidity IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS humidity_at,
                   (SELECT air_temperature FROM readings WHERE device_id = d.device_id AND air_temperature IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_temperature,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND air_temperature IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_temperature_at,
                   (SELECT air_pressure FROM readings WHERE device_id = d.device_id AND air_pressure IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_pressure,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND air_pressure IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS air_pressure_at,
                   (SELECT water_temperature FROM readings WHERE device_id = d.device_id AND water_temperature IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS water_temperature,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND water_temperature IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS water_temperature_at,
                   (SELECT ph FROM readings WHERE device_id = d.device_id AND ph IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS ph,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND ph IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS ph_at,
                   (SELECT raindrop FROM readings WHERE device_id = d.device_id AND raindrop IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS raindrop,
                   (SELECT COALESCE(captured_at, received_at) FROM readings WHERE device_id = d.device_id AND raindrop IS NOT NULL ORDER BY COALESCE(captured_at, received_at) DESC, id DESC LIMIT 1) AS raindrop_at,
                   r.captured_at, r.received_at
            FROM devices d
            LEFT JOIN readings r ON r.id = (
                SELECT id FROM readings
                WHERE device_id = d.device_id
                ORDER BY received_at DESC, id DESC LIMIT 1
            )
            ORDER BY d.name COLLATE NOCASE
            """
        ).fetchall()
        # Each metric has its own cadence; fetch its five most recent non-null
        # readings rather than averaging the last five rows of mixed sensors.
        rolling_averages: dict[str, dict[str, float | None]] = {}
        rolling_counts: dict[str, dict[str, int]] = {}
        for row in rows:
            device_id = row["device_id"]
            rolling_averages[device_id] = {}
            rolling_counts[device_id] = {}
            for metric in averaged_metrics:
                values = connection.execute(
                    f"""SELECT {metric} FROM readings
                        WHERE device_id = ? AND {metric} IS NOT NULL
                        ORDER BY COALESCE(captured_at, received_at) DESC, id DESC
                        LIMIT 5""",
                    (device_id,),
                ).fetchall()
                rolling_counts[device_id][metric] = len(values)
                rolling_averages[device_id][metric] = (
                    sum(value[0] for value in values) / len(values) if values else None
                )

    now = datetime.now(timezone.utc)
    devices: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.pop("geocode_attempted_at", None)
        item["rolling_averages"] = rolling_averages[item["device_id"]]
        item["rolling_counts"] = rolling_counts[item["device_id"]]
        last_seen = datetime.fromisoformat(item["last_seen"])
        item["online"] = (now - last_seen).total_seconds() < ONLINE_TIMEOUT_SECONDS
        temperatures = [item.get("air_temperature"), item.get("water_temperature")]
        item["temperature_alert"] = item["online"] and any(
            item.get(f"{metric}_at") is not None
            and (now - datetime.fromisoformat(item[f"{metric}_at"])).total_seconds() < TEMPERATURE_STALE_SECONDS
            and item[metric] > item["temperature_threshold"]
            for metric in ("air_temperature", "water_temperature")
            if item[metric] is not None
        )
        devices.append(item)
    return devices


def record_heartbeat(device_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO devices (
                device_id, name, latitude, longitude, temperature_threshold,
                created_at, last_seen
            ) VALUES (?, ?, NULL, NULL, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (device_id, device_id, DEFAULT_TEMPERATURE_THRESHOLD, now, now),
        )
    return {"ok": True, "device_id": device_id, "last_seen": now}


def get_history(
    device_id: str,
    hours: int,
    limit: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    since = (start or (datetime.now(timezone.utc) - timedelta(hours=hours))).isoformat()
    until = (end or datetime.now(timezone.utc)).isoformat()
    with _connection() as connection:
        exists = connection.execute(
            "SELECT 1 FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if not exists:
            raise KeyError(device_id)

        rows = connection.execute(
            """
            SELECT air_quality, humidity, air_temperature, air_pressure,
                   water_temperature, ph, raindrop, captured_at, received_at,
                   COALESCE(captured_at, received_at) AS measured_at
            FROM readings
            WHERE device_id = ? AND COALESCE(captured_at, received_at) >= ? AND COALESCE(captured_at, received_at) < ?
            ORDER BY COALESCE(captured_at, received_at) DESC, id DESC
            LIMIT ?
            """,
            (device_id, since, until, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def update_device(device_id: str, update: DeviceUpdate) -> dict[str, Any]:
    changes = update.model_dump(exclude_unset=True)
    if not changes:
        changes = {}

    with _connection() as connection:
        row = connection.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,)).fetchone()
        if not row:
            raise KeyError(device_id)

        merged = dict(row)
        merged.update(changes)
        coordinates_changed = (
            merged["latitude"] != row["latitude"] or merged["longitude"] != row["longitude"]
        )
        connection.execute(
            """
            UPDATE devices
            SET name = ?, latitude = ?, longitude = ?, temperature_threshold = ?,
                address = CASE WHEN ? THEN NULL ELSE address END,
                locality = CASE WHEN ? THEN NULL ELSE locality END,
                geocode_attempted_at = CASE WHEN ? THEN NULL ELSE geocode_attempted_at END
            WHERE device_id = ?
            """,
            (
                merged["name"],
                merged["latitude"],
                merged["longitude"],
                merged["temperature_threshold"],
                coordinates_changed,
                coordinates_changed,
                coordinates_changed,
                device_id,
            ),
        )
        if coordinates_changed:
            merged["address"] = None
            merged["locality"] = None
            merged["geocode_attempted_at"] = None
    merged.pop("geocode_attempted_at", None)
    return merged
