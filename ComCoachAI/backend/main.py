import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db
from backend.routes import admin, dashboard, participant, trainer

settings = get_settings()

app = FastAPI(
    title="ComCoach AI API",
    description="AI-powered communication evaluation system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trainer.router, prefix="/api")
app.include_router(participant.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()
    print("Database initialized")


@app.get("/")
def root():
    return {
        "message": "ComCoach AI API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.getenv("COMCOACH_RELOAD", "").lower() in {
        "1",
        "true",
        "yes",
    }
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=reload_enabled,
    )
