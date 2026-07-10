"""
FastAPI entry-point for the AI Interview Agent backend.

Run with:
    uvicorn main:app --reload --port 8000
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes import tests as tests_router
from routes import interviews as interviews_router
from routes import reports as reports_router
from routes import invites as invites_router
from routes import admin as admin_router
from routes import auth as auth_router


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response("index.html", scope)


def _allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app = FastAPI(title="AI Interview Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
def on_startup():
    """Create database tables on first run (idempotent)."""
    init_db()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/healthz")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

for api_prefix in ("/api", "/api/convai"):
    app.include_router(tests_router.router, prefix=api_prefix)
    app.include_router(interviews_router.router, prefix=api_prefix)
    app.include_router(reports_router.router, prefix=api_prefix)
    app.include_router(invites_router.router, prefix=api_prefix)
    app.include_router(admin_router.router, prefix=api_prefix)
    app.include_router(auth_router.router, prefix=api_prefix)

frontend_dist = Path(__file__).resolve().parents[1] / "artifacts" / "interview-app" / "dist"
if frontend_dist.exists():
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="static")
