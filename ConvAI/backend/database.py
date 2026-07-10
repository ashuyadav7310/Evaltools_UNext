"""
SQLAlchemy database models and session management.
Tables mirror the original Drizzle ORM schema exactly so the same
PostgreSQL database can be used without any migration.
"""

import os
import secrets
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

TEST_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_test_code() -> str:
    return "".join(secrets.choice(TEST_CODE_ALPHABET) for _ in range(8))


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    participant_context = Column(Text, nullable=False, default="")
    context = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    input_mode = Column(String, nullable=False, default="audio")
    rounds = Column(Integer, nullable=False, default=3)
    rubrics = Column(JSON, nullable=False)  # list[{name, description?}]
    trainer_id = Column(Integer, ForeignKey("trainer_accounts.id"), nullable=True)
    test_code = Column(String, nullable=True, unique=True)
    test_code_status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)


class TrainerAccount(Base):
    __tablename__ = "trainer_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invite_id = Column(Integer, ForeignKey("invites.id"), nullable=True)
    attempt_number = Column(Integer, nullable=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    candidate_name = Column(String, nullable=False)
    candidate_email = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    current_round = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    session_started_at = Column(DateTime(timezone=True), nullable=True)
    session_ended_at = Column(DateTime(timezone=True), nullable=True)
    session_duration_seconds = Column(Float, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("interview_id", "round", name="uq_response_interview_round"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    round = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    transcript = Column(Text, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    ai_speaking_duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False, unique=True)
    candidate_name = Column(String, nullable=False)
    test_title = Column(String, nullable=False)
    total_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, nullable=False)  # list[{criterion, score, maxScore, justification}]
    strengths = Column(JSON, nullable=False)         # list[str]
    weaknesses = Column(JSON, nullable=False)        # list[str]
    improvements = Column(JSON, nullable=False)      # list[str]
    overall_justification = Column(Text, nullable=False)
    time_spent_seconds = Column(Float, nullable=True)
    listening_seconds = Column(Float, nullable=True)
    talking_seconds = Column(Float, nullable=True)
    listening_talking_ratio = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    candidate_name = Column(String, nullable=True)
    max_attempts = Column(Integer, nullable=False, default=1)
    used_attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="issued")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    invite_id = Column(Integer, ForeignKey("invites.id"), nullable=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=True)
    actor_type = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS invites ("
                "id SERIAL PRIMARY KEY, "
                "test_id INTEGER NOT NULL REFERENCES tests(id), "
                "token_hash VARCHAR(255) NOT NULL UNIQUE, "
                "candidate_name VARCHAR(255), "
                "max_attempts INTEGER NOT NULL DEFAULT 1, "
                "used_attempts INTEGER NOT NULL DEFAULT 0, "
                "expires_at TIMESTAMPTZ NULL, "
                "status VARCHAR(32) NOT NULL DEFAULT 'issued', "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS audit_logs ("
                "id SERIAL PRIMARY KEY, "
                "action VARCHAR(64) NOT NULL, "
                "invite_id INTEGER NULL REFERENCES invites(id), "
                "interview_id INTEGER NULL REFERENCES interviews(id), "
                "actor_type VARCHAR(32) NOT NULL, "
                "details JSON NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS trainer_accounts ("
                "id SERIAL PRIMARY KEY, "
                "email VARCHAR(255) NOT NULL UNIQUE, "
                "password_hash VARCHAR(255) NOT NULL, "
                "status VARCHAR(32) NOT NULL DEFAULT 'active', "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS participant_context TEXT"))
        connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS input_mode VARCHAR(20)"))
        connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS trainer_id INTEGER"))
        connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS test_code VARCHAR(32)"))
        connection.execute(text("ALTER TABLE tests ADD COLUMN IF NOT EXISTS test_code_status VARCHAR(32)"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS invite_id INTEGER"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS attempt_number INTEGER"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS candidate_email VARCHAR(255)"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS session_started_at TIMESTAMPTZ"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS session_ended_at TIMESTAMPTZ"))
        connection.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS session_duration_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE responses ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE responses ADD COLUMN IF NOT EXISTS ai_speaking_duration_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS time_spent_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS listening_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS talking_seconds DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS listening_talking_ratio DOUBLE PRECISION"))
        connection.execute(
            text(
                "UPDATE tests SET participant_context = context "
                "WHERE participant_context IS NULL OR btrim(participant_context) = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE tests SET input_mode = 'audio' "
                "WHERE input_mode IS NULL OR btrim(input_mode) = ''"
            )
        )
        connection.execute(
            text(
                "UPDATE tests SET test_code_status = 'active' "
                "WHERE test_code_status IS NULL OR btrim(test_code_status) = ''"
            )
        )
        existing_codes = {
            row[0]
            for row in connection.execute(
                text("SELECT test_code FROM tests WHERE test_code IS NOT NULL AND btrim(test_code) <> ''")
            )
        }
        tests_without_codes = connection.execute(
            text("SELECT id FROM tests WHERE test_code IS NULL OR btrim(test_code) = ''")
        ).fetchall()
        for row in tests_without_codes:
            code = generate_test_code()
            while code in existing_codes:
                code = generate_test_code()
            existing_codes.add(code)
            connection.execute(
                text("UPDATE tests SET test_code = :code WHERE id = :id"),
                {"code": code, "id": row[0]},
            )
        connection.execute(
            text(
                "ALTER TABLE tests ALTER COLUMN participant_context SET DEFAULT ''"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE tests ALTER COLUMN input_mode SET DEFAULT 'audio'"
            )
        )
        connection.execute(text("ALTER TABLE tests ALTER COLUMN test_code SET NOT NULL"))
        connection.execute(text("ALTER TABLE tests ALTER COLUMN test_code_status SET DEFAULT 'active'"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_tests_test_code ON tests(test_code)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_interviews_invite_attempt ON interviews(invite_id, attempt_number) WHERE invite_id IS NOT NULL"))
