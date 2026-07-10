from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from auth import AuthPrincipal, hash_invite_token
from database import AuditLog, Interview, Invite, Test, get_db, now_utc
from routes.deps import require_active_trainer_access

router = APIRouter()


class CreateInviteRequest(BaseModel):
    testId: int
    candidateName: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    maxAttempts: int = Field(default=100, ge=1, le=500)
    expiresAt: Optional[datetime] = None


class StartInviteRequest(BaseModel):
    candidateName: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    candidateEmail: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]] = None


def _normalize_expiry(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=now_utc().tzinfo)
    return value


def _serialize_test_for_candidate(test: Test) -> dict:
    return {
        "id": test.id,
        "title": test.title,
        "participantContext": test.participant_context,
        "category": test.category,
        "inputMode": test.input_mode,
        "rounds": test.rounds,
    }


def _serialize_invite(invite: Invite) -> dict:
    return {
        "id": invite.id,
        "testId": invite.test_id,
        "candidateName": invite.candidate_name,
        "maxAttempts": invite.max_attempts,
        "usedAttempts": invite.used_attempts,
        "expiresAt": invite.expires_at,
        "status": invite.status,
        "createdAt": invite.created_at,
        "updatedAt": invite.updated_at,
    }


def _serialize_interview(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "testId": interview.test_id,
        "candidateName": interview.candidate_name,
        "candidateEmail": interview.candidate_email,
        "status": interview.status,
        "currentRound": interview.current_round,
        "createdAt": interview.created_at,
        "sessionStartedAt": interview.session_started_at,
        "sessionEndedAt": interview.session_ended_at,
        "sessionDurationSeconds": interview.session_duration_seconds,
        "completedAt": interview.completed_at,
    }


def _trainer_test_query(db: Session, principal: AuthPrincipal):
    query = db.query(Test)
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    return query


def _frontend_join_url(request: Request, token: str) -> str:
    forwarded_prefix = request.headers.get("x-forwarded-prefix", "").strip()
    prefix = f"/{forwarded_prefix.strip('/')}" if forwarded_prefix else ""
    return f"{str(request.base_url).rstrip('/')}{prefix}/join/{token}"


def _log_audit_event(
    db: Session,
    *,
    action: str,
    actor_type: str,
    invite_id: int | None = None,
    interview_id: int | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            actor_type=actor_type,
            invite_id=invite_id,
            interview_id=interview_id,
            details=details,
        )
    )


def _get_access_and_test(db: Session, invite_token: str) -> tuple[Invite | None, Test]:
    code = invite_token.strip().upper()
    test = db.query(Test).filter(Test.test_code == code).first()
    if test:
        return None, test

    token_hash = hash_invite_token(invite_token)
    invite = db.query(Invite).filter(Invite.token_hash == token_hash).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Test code not found")

    test = db.query(Test).filter(Test.id == invite.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if invite.expires_at and invite.expires_at <= now_utc():
        if invite.status != "expired":
            invite.status = "expired"
            db.commit()
        raise HTTPException(status_code=410, detail="Invite expired")

    return invite, test


def _serialize_code_access(test: Test) -> dict:
    return {
        "id": 0,
        "testId": test.id,
        "candidateName": None,
        "maxAttempts": 0,
        "usedAttempts": 0,
        "expiresAt": None,
        "status": "issued",
        "createdAt": test.created_at,
        "updatedAt": test.updated_at,
    }


@router.post("/invites", status_code=201)
def create_invite(
    body: CreateInviteRequest,
    request: Request,
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    test = _trainer_test_query(db, principal).filter(Test.id == body.testId).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if test.test_code_status != "active":
        raise HTTPException(status_code=409, detail="Test code is inactive")

    _log_audit_event(
        db,
        action="test_code_copied",
        actor_type="trainer",
        details={"testId": body.testId},
    )

    db.commit()

    payload = _serialize_code_access(test)
    payload["inviteToken"] = test.test_code
    payload["joinUrl"] = _frontend_join_url(request, test.test_code)
    return payload


@router.get("/invites")
def list_invites(
    test_id: int | None = Query(default=None, alias="testId"),
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    query = db.query(Invite).join(Test, Test.id == Invite.test_id).order_by(Invite.created_at.desc())
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    if test_id is not None:
        query = query.filter(Invite.test_id == test_id)
    invites = query.all()
    return [_serialize_invite(invite) for invite in invites]


@router.get("/join/{invite_token}")
def validate_invite(invite_token: str, db: Session = Depends(get_db)):
    invite, test = _get_access_and_test(db, invite_token)
    if test.test_code_status != "active":
        raise HTTPException(status_code=403, detail="Test code is inactive")

    active_attempt = None
    if invite:
        active_attempt = (
            db.query(Interview)
            .filter(Interview.invite_id == invite.id, Interview.status != "completed")
            .order_by(Interview.created_at.desc())
            .first()
        )

    can_start_new = True if invite is None else invite.status != "expired" and invite.used_attempts < invite.max_attempts
    return {
        "invite": _serialize_invite(invite) if invite else _serialize_code_access(test),
        "test": _serialize_test_for_candidate(test),
        "activeInterview": _serialize_interview(active_attempt) if active_attempt else None,
        "canStartNew": can_start_new,
        "remainingAttempts": max(invite.max_attempts - invite.used_attempts, 0) if invite else 1,
    }


@router.post("/join/{invite_token}/start", status_code=201)
def start_from_invite(
    invite_token: str,
    body: StartInviteRequest,
    db: Session = Depends(get_db),
):
    invite, test = _get_access_and_test(db, invite_token)
    if test.test_code_status != "active":
        raise HTTPException(status_code=403, detail="Test code is inactive")

    candidate_email = (body.candidateEmail or "").strip().lower() or None
    active_query = db.query(Interview).filter(Interview.status != "completed").order_by(Interview.created_at.desc())
    if invite:
        active_query = active_query.filter(Interview.invite_id == invite.id)
    else:
        active_query = active_query.filter(Interview.invite_id.is_(None), Interview.test_id == test.id)
        if candidate_email:
            active_query = active_query.filter(Interview.candidate_email == candidate_email)
        else:
            active_query = active_query.filter(Interview.candidate_email.is_(None))
    active_attempt = active_query.first()
    if active_attempt:
        _log_audit_event(
            db,
            action="invite_resume",
            actor_type="candidate",
            invite_id=invite.id if invite else None,
            interview_id=active_attempt.id,
        )
        db.commit()
        return {"interview": _serialize_interview(active_attempt), "resumed": True}

    if invite and invite.used_attempts >= invite.max_attempts:
        raise HTTPException(status_code=409, detail="No attempts remaining for this invite")

    invite_candidate_name = invite.candidate_name if invite and invite.candidate_name else ""
    candidate_name = (body.candidateName or "").strip() or invite_candidate_name.strip()
    if not candidate_name:
        candidate_name = "Candidate"

    attempt_number = invite.used_attempts + 1 if invite else None
    interview = Interview(
        invite_id=invite.id if invite else None,
        attempt_number=attempt_number,
        test_id=test.id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        status="pending",
        current_round=1,
    )
    db.add(interview)

    if invite:
        invite.used_attempts = attempt_number
        invite.status = "started"

    _log_audit_event(
        db,
        action="invite_started",
        actor_type="candidate",
        invite_id=invite.id if invite else None,
        details={"attemptNumber": attempt_number},
    )

    db.commit()
    db.refresh(interview)
    return {"interview": _serialize_interview(interview), "resumed": False}
