# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import get_settings

settings = get_settings()

engine_kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_existing_schema_columns()

def _ensure_existing_schema_columns():
    inspector = inspect(engine)
    test_columns = {column["name"] for column in inspector.get_columns("tests")}
    with engine.begin() as connection:
        if "is_active" not in test_columns:
            if engine.dialect.name == "postgresql":
                connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
            else:
                connection.execute(text("ALTER TABLE tests ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
