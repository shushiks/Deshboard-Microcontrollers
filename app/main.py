from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, ENVIRONMENT, ESP_API_KEY
from .repository import get_history, initialize_database, list_devices, record_heartbeat, save_metrics, update_device
from .schemas import DeviceUpdate, MetricsInput
from .security import SecurityHeadersMiddleware, require_api_key, write_limiter


@asynccontextmanager
async def lifespan(_: FastAPI):
    if ENVIRONMENT == "production" and not ESP_API_KEY:
        raise RuntimeError("ESP_API_KEY must be set in production")
    initialize_database()
    yield


app = FastAPI(
    title="Microclimate Monitor",
    description="Multi-device ESP32 telemetry platform",
    version="2.1.0",
    lifespan=lifespan,
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if ENVIRONMENT == "production" else "/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/metrics", status_code=201, dependencies=[Depends(require_api_key)])
def receive_metrics(payload: MetricsInput) -> dict[str, object]:
    write_limiter.check(f"metrics:{payload.device_id}")
    saved = save_metrics(payload)
    return {"ok": True, **saved}


@app.get("/api/devices")
def devices() -> list[dict[str, object]]:
    return list_devices()


@app.post("/api/devices/{device_id}/heartbeat", dependencies=[Depends(require_api_key)])
def heartbeat(
    device_id: str = ApiPath(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$"),
) -> dict[str, object]:
    write_limiter.check(f"heartbeat:{device_id}")
    return record_heartbeat(device_id)


@app.get("/api/devices/{device_id}/history")
def device_history(
    device_id: str = ApiPath(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$"),
    hours: int = Query(default=24, ge=1, le=24 * 90),
    limit: int = Query(default=500, ge=1, le=5000),
    day: date | None = Query(default=None),
    timezone_offset: int = Query(default=0, ge=-840, le=840),
) -> dict[str, object]:
    start = end = None
    if day is not None:
        local_timezone = timezone(timedelta(minutes=-timezone_offset))
        local_start = datetime.combine(day, time.min, tzinfo=local_timezone)
        start = local_start.astimezone(timezone.utc)
        end = (local_start + timedelta(days=1)).astimezone(timezone.utc)
    try:
        readings = get_history(device_id, hours, limit, start=start, end=end)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found") from None
    return {"device_id": device_id, "hours": hours, "day": day, "readings": readings}


@app.patch("/api/devices/{device_id}", dependencies=[Depends(require_api_key)])
def patch_device(
    update: DeviceUpdate,
    request: Request,
    device_id: str = ApiPath(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$"),
) -> dict[str, object]:
    write_limiter.check(f"patch:{request.client.host if request.client else 'unknown'}")
    try:
        return update_device(device_id, update)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found") from None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
