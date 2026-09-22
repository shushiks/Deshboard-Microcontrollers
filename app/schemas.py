from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetricsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")]
    device_name: Annotated[str | None, Field(max_length=120)] = None

    air_quality: Annotated[float | None, Field(ge=0, le=4095)] = None
    humidity: Annotated[float | None, Field(ge=0, le=100)] = None
    air_temperature: Annotated[float | None, Field(ge=-80, le=150)] = None
    air_pressure: Annotated[float | None, Field(ge=300, le=1100)] = None
    water_temperature: Annotated[float | None, Field(ge=-80, le=150)] = None
    ph: Annotated[float | None, Field(ge=0, le=14)] = None
    raindrop: Annotated[float | None, Field(ge=0, le=4095)] = None

    latitude: Annotated[float | None, Field(ge=-90, le=90)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180)] = None
    captured_at: datetime | None = None
    sample_id: Annotated[str | None, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")] = None
    # Compatibility with the first ESP32 sketch.
    alcohol: Annotated[float | None, Field(ge=0, le=4095)] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def migrate_alcohol_to_air_quality(self) -> "MetricsInput":
        if self.air_quality is None and self.alcohol is not None:
            self.air_quality = self.alcohol
        return self

    @model_validator(mode="after")
    def validate_reading(self) -> "MetricsInput":
        metric_fields = {
            "air_quality", "alcohol", "humidity", "air_temperature",
            "water_temperature", "air_pressure", "ph", "raindrop",
        }
        if not any(getattr(self, field) is not None for field in metric_fields):
            raise ValueError("At least one sensor metric must be provided")
        if self.captured_at is not None:
            if self.captured_at.tzinfo is None:
                raise ValueError("captured_at must include a timezone")
            if self.captured_at > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError("captured_at cannot be in the future")
        return self


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str | None, Field(min_length=1, max_length=120)] = None
    latitude: Annotated[float | None, Field(ge=-90, le=90)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180)] = None
    temperature_threshold: Annotated[float | None, Field(ge=-50, le=120)] = None

    @model_validator(mode="after")
    def require_change(self) -> "DeviceUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "temperature_threshold" in self.model_fields_set and self.temperature_threshold is None:
            raise ValueError("temperature_threshold cannot be null")
        return self
