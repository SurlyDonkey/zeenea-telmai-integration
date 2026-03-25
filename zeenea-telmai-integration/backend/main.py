from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from routers import assets_router, quality_router, sync_router
from routers.sync import scheduler, _scheduled_full_sync
from store import get_zeenea_client, get_telmai_client, get_current_settings, update_settings
from models import SettingsUpdate, ConnectionTestResult
from database import create_db_and_tables, get_session, engine
from auth import verify_api_key

from sqlmodel import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    scheduler.add_job(
        _scheduled_full_sync,
        trigger="interval",
        hours=4,
        id="full_sync",
        replace_existing=True,
    )
    scheduler.start()

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Zeenea–Telmai Integration API",
    description="Bidirectional integration between Zeenea data catalog and Telmai data quality platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets_router)
app.include_router(quality_router)
app.include_router(sync_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/settings", dependencies=[Depends(verify_api_key)])
async def get_settings():
    settings = get_current_settings()
    masked = {}
    for k, v in settings.items():
        if any(s in k for s in ("key", "token", "password")):
            masked[k] = ("*" * 8 + v[-4:]) if v and len(v) > 4 else ("****" if v else "")
        else:
            masked[k] = v
    return masked


@app.post("/api/settings", dependencies=[Depends(verify_api_key)])
async def save_settings(body: SettingsUpdate):
    fields = [
        "zeenea_url", "zeenea_api_key",
        "telmai_endpoint", "telmai_tenant", "telmai_username",
        "telmai_password", "telmai_client_id", "telmai_auth_endpoint",
    ]
    updates = {f: getattr(body, f) for f in fields if getattr(body, f) is not None}
    update_settings(updates)
    return {"detail": "Settings updated successfully"}


@app.post("/api/settings/test/zeenea", response_model=ConnectionTestResult, dependencies=[Depends(verify_api_key)])
async def test_zeenea():
    client = get_zeenea_client()
    ok, message, count = await client.test_connection()
    return ConnectionTestResult(service="zeenea", success=ok, message=message, dataset_count=count)


@app.post("/api/settings/test/telmai", response_model=ConnectionTestResult, dependencies=[Depends(verify_api_key)])
async def test_telmai():
    client = get_telmai_client()
    ok, message, count = await client.test_connection()
    return ConnectionTestResult(service="telmai", success=ok, message=message, dataset_count=count)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
