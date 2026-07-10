import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

TRAINER_API_KEY = os.getenv("TRAINER_API_KEY", "").strip()
TRAINER_SESSION_SECRET = (os.getenv("TRAINER_SESSION_SECRET") or TRAINER_API_KEY or "convai-local-session-secret").strip()


@dataclass(frozen=True)
class AuthPrincipal:
    role: str
    trainer_id: int | None = None
    email: str | None = None


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256$200000${salt}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return hmac.compare_digest(base64.b64encode(candidate).decode("ascii"), digest)
    except Exception:
        return False


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def create_trainer_session_token(*, trainer_id: int, email: str) -> str:
    payload = {
        "trainerId": trainer_id,
        "email": email,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=12)).timestamp()),
    }
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(TRAINER_SESSION_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def parse_trainer_session_token(token: str) -> AuthPrincipal | None:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(TRAINER_SESSION_SECRET.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected), signature_part):
            return None
        payload = json.loads(_b64url_decode(payload_part))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        trainer_id = int(payload["trainerId"])
        email = str(payload.get("email") or "")
        return AuthPrincipal(role="trainer", trainer_id=trainer_id, email=email)
    except Exception:
        return None


def get_invite_token_from_headers(
    authorization: str | None,
    x_invite_token: str | None,
) -> str:
    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()

    return (x_invite_token or bearer_token or "").strip()


def is_valid_trainer_token(
    authorization: str | None,
    x_admin_token: str | None,
) -> bool:
    if not TRAINER_API_KEY:
        return False

    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()

    provided_token = x_admin_token or bearer_token or ""
    return hmac.compare_digest(provided_token, TRAINER_API_KEY)


def require_admin_access(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> AuthPrincipal:
    """Protect admin-only routes with the existing shared admin token/header."""
    if not TRAINER_API_KEY:
        raise HTTPException(status_code=503, detail="Admin access key is not configured")

    if not is_valid_trainer_token(authorization=authorization, x_admin_token=x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return AuthPrincipal(role="admin")


def require_trainer_access(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
) -> AuthPrincipal:
    """Allow either admin token or a signed active trainer session token."""
    if is_valid_trainer_token(authorization=authorization, x_admin_token=x_admin_token):
        return AuthPrincipal(role="admin")

    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()

    trainer_token = (x_trainer_token or bearer_token or "").strip()
    principal = parse_trainer_session_token(trainer_token) if trainer_token else None
    if principal:
        return principal

    raise HTTPException(status_code=401, detail="Unauthorized")
