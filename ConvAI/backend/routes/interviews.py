import base64
import io
import logging
import os
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
import httpx
from openai import APIConnectionError, AuthenticationError, OpenAI, OpenAIError, RateLimitError
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from auth import (
    AuthPrincipal,
    get_invite_token_from_headers,
    hash_invite_token,
    is_valid_trainer_token,
    parse_trainer_session_token,
)
from database import AuditLog, Interview, Invite, Report, Response, Test, get_db, now_utc
from routes.deps import require_active_trainer_access
from agents.agent_factory import (
    generate_next_question as generate_question_from_factory,
    generate_candidate_answer as generate_candidate_answer_from_factory,
)
from agents.evaluator import evaluate_candidate, evaluate_interviewer

router = APIRouter()
logger = logging.getLogger(__name__)

_openai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    http_client=httpx.Client(trust_env=False),
)

STT_MODEL = os.getenv("STT_MODEL", "gpt-4o-mini-transcribe")
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
INTERVIEWER_EVALUATION_CATEGORY = "interviewer_evaluation"


def _ai_failure_detail(operation: str, exc: Exception) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return f"{operation} failed because OPENAI_API_KEY is not configured"
    if isinstance(exc, APIConnectionError):
        return f"{operation} failed because the backend could not reach OpenAI. Check outbound internet/proxy settings."
    if isinstance(exc, AuthenticationError):
        return f"{operation} failed because the OpenAI API key was rejected"
    status_code = getattr(exc, "status_code", None)
    if status_code in {401, 403}:
        return f"{operation} failed because the OpenAI API key was rejected"
    if status_code == 429 or isinstance(exc, RateLimitError):
        return f"{operation} failed because the OpenAI quota or rate limit was reached"
    return f"{operation} failed while contacting the AI provider"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateInterviewRequest(BaseModel):
    testId: int
    candidateName: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    candidateEmail: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]] = None


class NextQuestionRequest(BaseModel):
    candidateResponse: Optional[str] = None
    lastQuestion: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]] = None
    responseRound: Optional[int] = Field(default=None, ge=1)


class SubmitResponseRequest(BaseModel):
    round: int = Field(ge=1)
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    transcript: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    responseDurationSeconds: Optional[float] = Field(default=None, ge=0)
    aiSpeakingDurationSeconds: Optional[float] = Field(default=None, ge=0)


class TranscribeRequest(BaseModel):
    audio: str  # base64 encoded audio
    mimeType: Optional[str] = None


class TextToSpeechRequest(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class ProcessTurnRequest(BaseModel):
    audio: str  # base64 encoded audio
    mimeType: Optional[str] = None
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    round: int = Field(ge=1)
    responseDurationSeconds: Optional[float] = Field(default=None, ge=0)
    aiSpeakingDurationSeconds: Optional[float] = Field(default=None, ge=0)


class ProcessTextTurnRequest(BaseModel):
    transcript: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    round: int = Field(ge=1)
    responseDurationSeconds: Optional[float] = Field(default=None, ge=0)
    aiSpeakingDurationSeconds: Optional[float] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _serialize_test(test: Test) -> dict:
    return {
        "id": test.id,
        "title": test.title,
        "participantContext": test.participant_context,
        "context": test.context,
        "category": test.category,
        "inputMode": test.input_mode,
        "rounds": test.rounds,
        "rubrics": test.rubrics,
        "createdAt": test.created_at,
        "updatedAt": test.updated_at,
    }


def _serialize_interview(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "inviteId": interview.invite_id,
        "attemptNumber": interview.attempt_number,
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


def _serialize_response(response: Response) -> dict:
    return {
        "id": response.id,
        "interviewId": response.interview_id,
        "round": response.round,
        "question": response.question,
        "transcript": response.transcript,
        "durationSeconds": response.duration_seconds,
        "aiSpeakingDurationSeconds": response.ai_speaking_duration_seconds,
        "createdAt": response.created_at,
    }


def _decode_audio_payload(audio_b64: str) -> bytes:
    try:
        return base64.b64decode(audio_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid audio payload") from exc


def _normalize_category(category: Optional[str]) -> str:
    return (category or "").strip().lower().replace(" ", "_")


def _is_interviewer_evaluation_category(category: Optional[str]) -> bool:
    return _normalize_category(category) == INTERVIEWER_EVALUATION_CATEGORY


def _seconds_between(start: Optional[datetime], end: Optional[datetime]) -> float:
    if not start or not end:
        return 0.0
    return max((end - start).total_seconds(), 0.0)


def _estimate_response_duration_seconds(transcript: str) -> float:
    words = len((transcript or "").split())
    if words <= 0:
        return 0.0
    return max(round(words / 2.5, 2), 1.0)


def _coerce_response_duration_seconds(transcript: str, provided: Optional[float]) -> float:
    if provided is not None:
        return max(float(provided), 0.0)
    return _estimate_response_duration_seconds(transcript)


def _calculate_session_metrics(interview: Interview, responses: list[Response]) -> dict:
    session_started_at = interview.session_started_at or interview.created_at or now_utc()
    session_ended_at = interview.session_ended_at or now_utc()
    time_spent_seconds = _seconds_between(session_started_at, session_ended_at)
    return {
        "sessionStartedAt": session_started_at,
        "sessionEndedAt": session_ended_at,
        "timeSpentSeconds": round(time_spent_seconds, 2),
    }


def _transcribe_audio_bytes(audio_bytes: bytes, mime_type: str) -> str:
    extension = mime_type.split("/")[-1].split(";")[0] or "webm"
    filename = f"audio.{extension}"
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    try:
        transcription = _openai.audio.transcriptions.create(
            file=(filename, audio_file, mime_type),
            model=STT_MODEL,
            response_format="json",
        )
        return transcription.text
    except OpenAIError as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=502, detail=_ai_failure_detail("Transcription", exc)) from exc
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed") from exc


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


def _require_interview_access(
    *,
    interview_id: int,
    db: Session,
    authorization: str | None,
    x_admin_token: str | None,
    x_trainer_token: str | None,
    x_invite_token: str | None,
) -> tuple[Interview, Invite | None, str]:
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if is_valid_trainer_token(authorization=authorization, x_admin_token=x_admin_token):
        return interview, None, "trainer"

    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization[7:].strip()
    trainer_principal = parse_trainer_session_token((x_trainer_token or bearer_token or "").strip())
    if trainer_principal:
        test = db.query(Test).filter(Test.id == interview.test_id).first()
        if test and test.trainer_id == trainer_principal.trainer_id:
            return interview, None, "trainer"
        raise HTTPException(status_code=403, detail="Interview is not owned by this trainer")

    invite_token = get_invite_token_from_headers(
        authorization=authorization,
        x_invite_token=x_invite_token,
    )
    if not invite_token:
        raise HTTPException(status_code=401, detail="Invite token required")
    if not interview.invite_id:
        test = db.query(Test).filter(Test.id == interview.test_id).first()
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")
        if test.test_code_status != "active":
            raise HTTPException(status_code=403, detail="Test code is inactive")
        if (test.test_code or "").upper() != invite_token.strip().upper():
            raise HTTPException(status_code=403, detail="Invalid test code")
        return interview, None, "candidate"

    invite = db.query(Invite).filter(Invite.id == interview.invite_id).first()
    if not invite:
        raise HTTPException(status_code=403, detail="Invite not found for interview")
    if invite.token_hash != hash_invite_token(invite_token):
        raise HTTPException(status_code=403, detail="Invalid invite token")
    if invite.expires_at and invite.expires_at <= now_utc():
        if invite.status != "expired":
            invite.status = "expired"
            db.commit()
        raise HTTPException(status_code=410, detail="Invite expired")

    return interview, invite, "candidate"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/interviews")
def list_interviews(
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    query = db.query(Interview).join(Test, Test.id == Interview.test_id).order_by(Interview.created_at)
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    interviews = query.all()
    return [_serialize_interview(interview) for interview in interviews]


@router.post("/interviews", status_code=201)
def create_interview(
    body: CreateInterviewRequest,
    principal: AuthPrincipal = Depends(require_active_trainer_access),
    db: Session = Depends(get_db),
):
    query = db.query(Test).filter(Test.id == body.testId)
    if principal.role == "trainer":
        query = query.filter(Test.trainer_id == principal.trainer_id)
    test = query.first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    interview = Interview(
        test_id=body.testId,
        candidate_name=body.candidateName,
        candidate_email=(body.candidateEmail or "").strip().lower() or None,
        status="pending",
        current_round=1,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return _serialize_interview(interview)


@router.get("/interviews/{interview_id}")
def get_interview(
    interview_id: int,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    responses = (
        db.query(Response)
        .filter(Response.interview_id == interview.id)
        .order_by(Response.round)
        .all()
    )

    payload = _serialize_interview(interview)
    payload["test"] = _serialize_test(test) if test else None
    payload["responses"] = [_serialize_response(response) for response in responses]
    return payload


@router.post("/interviews/{interview_id}/next-question")
def next_question(
    interview_id: int,
    body: NextQuestionRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if interview.status == "completed":
        return {"question": "", "round": interview.current_round, "isComplete": True}

    prev_responses = (
        db.query(Response)
        .filter(Response.interview_id == interview.id)
        .order_by(Response.round)
        .all()
    )

    conversation_history = [
        {"question": r.question, "answer": r.transcript} for r in prev_responses
    ]

    target_round = interview.current_round
    if (
        body.candidateResponse
        and body.lastQuestion
        and body.responseRound is not None
        and body.responseRound == interview.current_round
    ):
        conversation_history.append({"question": body.lastQuestion, "answer": body.candidateResponse})
        target_round = interview.current_round + 1

    session_state_changed = False
    if interview.session_started_at is None:
        interview.session_started_at = now_utc()
        session_state_changed = True

    if interview.status == "pending":
        interview.status = "in_progress"
        session_state_changed = True

    if session_state_changed:
        db.commit()

    if _is_interviewer_evaluation_category(test.category):
        instruction = (
            "Ask your opening interview question to the AI candidate."
            if target_round == 1
            else "Ask your next interview question to continue the evaluation."
        )
        return {
            "question": instruction,
            "round": target_round,
            "isComplete": False,
        }

    try:
        question = generate_question_from_factory(
            category=test.category,
            test_title=test.title,
            test_context=test.context,
            rubrics=test.rubrics,
            total_rounds=test.rounds,
            current_round=target_round,
            conversation_history=conversation_history,
            candidate_response=body.candidateResponse,
            candidate_name=interview.candidate_name,
        )
    except OpenAIError as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=502, detail=_ai_failure_detail("Question generation", exc)) from exc
    except Exception as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=500, detail="Question generation failed") from exc

    return {
        "question": question,
        "round": target_round,
        "isComplete": False,
    }


@router.post("/interviews/{interview_id}/responses", status_code=201)
def submit_response(
    interview_id: int,
    body: SubmitResponseRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
    if interview.status == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")
    if body.round != interview.current_round:
        raise HTTPException(
            status_code=409,
            detail=f"Expected round {interview.current_round}, received round {body.round}",
        )

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    existing_response = (
        db.query(Response)
        .filter(Response.interview_id == interview.id, Response.round == body.round)
        .first()
    )
    if existing_response:
        raise HTTPException(status_code=409, detail="Response for this round already exists")

    response = Response(
        interview_id=interview.id,
        round=body.round,
        question=body.question,
        transcript=body.transcript,
        duration_seconds=_coerce_response_duration_seconds(body.transcript, body.responseDurationSeconds),
        ai_speaking_duration_seconds=body.aiSpeakingDurationSeconds,
    )
    db.add(response)
    _log_audit_event(
        db,
        action="response_submitted",
        actor_type="candidate" if interview.invite_id else "trainer",
        invite_id=interview.invite_id,
        interview_id=interview.id,
        details={"round": body.round, "mode": "manual_submit"},
    )
    interview.current_round = body.round + 1
    if interview.session_started_at is None:
        interview.session_started_at = now_utc()
    db.commit()
    db.refresh(response)
    return _serialize_response(response)


@router.post("/interviews/{interview_id}/transcribe")
def transcribe_audio(
    interview_id: int,
    body: TranscribeRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
    if interview.status == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")

    audio_bytes = _decode_audio_payload(body.audio)
    mime_type = (body.mimeType or "audio/webm").lower()
    transcript = _transcribe_audio_bytes(audio_bytes, mime_type)
    return {"transcript": transcript}


@router.post("/interviews/{interview_id}/process-turn")
def process_turn(
    interview_id: int,
    body: ProcessTurnRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
    if interview.status == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if body.round != interview.current_round:
        raise HTTPException(
            status_code=409,
            detail=f"Expected round {interview.current_round}, received round {body.round}",
        )

    existing_response = (
        db.query(Response)
        .filter(Response.interview_id == interview.id, Response.round == body.round)
        .first()
    )
    if existing_response:
        raise HTTPException(status_code=409, detail="Response for this round already exists")

    audio_bytes = _decode_audio_payload(body.audio)
    mime_type = (body.mimeType or "audio/webm").lower()
    transcript = _transcribe_audio_bytes(audio_bytes, mime_type)
    response_duration_seconds = _coerce_response_duration_seconds(transcript, body.responseDurationSeconds)

    if _is_interviewer_evaluation_category(test.category):
        prev_responses = (
            db.query(Response)
            .filter(Response.interview_id == interview.id)
            .order_by(Response.round)
            .all()
        )
        conversation_history = [
            {"question": r.question, "answer": r.transcript} for r in prev_responses
        ]

        try:
            candidate_answer = generate_candidate_answer_from_factory(
                category=test.category,
                role_context=test.context,
                candidate_profile=test.participant_context,
                interviewer_question=transcript,
                conversation_history=conversation_history,
                current_round=body.round,
                session_seed=str(interview.id),
            )
        except OpenAIError as exc:
            logger.exception("Candidate answer generation failed")
            raise HTTPException(status_code=502, detail=_ai_failure_detail("Candidate answer generation", exc)) from exc
        except Exception as exc:
            logger.exception("Candidate answer generation failed")
            raise HTTPException(status_code=500, detail="Candidate answer generation failed") from exc

        response = Response(
            interview_id=interview.id,
            round=body.round,
            question=transcript,
            transcript=candidate_answer,
            duration_seconds=response_duration_seconds,
            ai_speaking_duration_seconds=body.aiSpeakingDurationSeconds,
        )
        db.add(response)
        _log_audit_event(
            db,
            action="response_submitted",
            actor_type="candidate" if interview.invite_id else "trainer",
            invite_id=interview.invite_id,
            interview_id=interview.id,
            details={"round": body.round, "mode": "audio_interviewer_eval"},
        )
        interview.current_round = body.round + 1
        if interview.status == "pending":
            interview.status = "in_progress"
        if interview.session_started_at is None:
            interview.session_started_at = now_utc()
        db.commit()

        return {
            "transcript": candidate_answer,
            "interviewerQuestion": transcript,
            "question": "Ask your next interview question to continue the evaluation.",
            "round": interview.current_round,
            "isComplete": False,
        }

    response = Response(
        interview_id=interview.id,
        round=body.round,
        question=body.question,
        transcript=transcript,
        duration_seconds=response_duration_seconds,
        ai_speaking_duration_seconds=body.aiSpeakingDurationSeconds,
    )
    db.add(response)
    _log_audit_event(
        db,
        action="response_submitted",
        actor_type="candidate" if interview.invite_id else "trainer",
        invite_id=interview.invite_id,
        interview_id=interview.id,
        details={"round": body.round, "mode": "audio"},
    )
    interview.current_round = body.round + 1
    if interview.status == "pending":
        interview.status = "in_progress"
    if interview.session_started_at is None:
        interview.session_started_at = now_utc()
    db.commit()

    prev_responses = (
        db.query(Response)
        .filter(Response.interview_id == interview.id)
        .order_by(Response.round)
        .all()
    )
    conversation_history = [
        {"question": r.question, "answer": r.transcript} for r in prev_responses
    ]

    try:
        question = generate_question_from_factory(
            category=test.category,
            test_title=test.title,
            test_context=test.context,
            rubrics=test.rubrics,
            total_rounds=test.rounds,
            current_round=interview.current_round,
            conversation_history=conversation_history,
            candidate_response=transcript,
            candidate_name=interview.candidate_name,
        )
    except OpenAIError as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=502, detail=_ai_failure_detail("Question generation", exc)) from exc
    except Exception as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=500, detail="Question generation failed") from exc

    return {
        "transcript": transcript,
        "question": question,
        "round": interview.current_round,
        "isComplete": False,
    }


@router.post("/interviews/{interview_id}/process-text-turn")
def process_text_turn(
    interview_id: int,
    body: ProcessTextTurnRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
    if interview.status == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if body.round != interview.current_round:
        raise HTTPException(
            status_code=409,
            detail=f"Expected round {interview.current_round}, received round {body.round}",
        )

    existing_response = (
        db.query(Response)
        .filter(Response.interview_id == interview.id, Response.round == body.round)
        .first()
    )
    if existing_response:
        raise HTTPException(status_code=409, detail="Response for this round already exists")

    transcript = body.transcript
    response_duration_seconds = _coerce_response_duration_seconds(transcript, body.responseDurationSeconds)

    if _is_interviewer_evaluation_category(test.category):
        prev_responses = (
            db.query(Response)
            .filter(Response.interview_id == interview.id)
            .order_by(Response.round)
            .all()
        )
        conversation_history = [
            {"question": r.question, "answer": r.transcript} for r in prev_responses
        ]

        try:
            candidate_answer = generate_candidate_answer_from_factory(
                category=test.category,
                role_context=test.context,
                candidate_profile=test.participant_context,
                interviewer_question=transcript,
                conversation_history=conversation_history,
                current_round=body.round,
                session_seed=str(interview.id),
            )
        except OpenAIError as exc:
            logger.exception("Candidate answer generation failed")
            raise HTTPException(status_code=502, detail=_ai_failure_detail("Candidate answer generation", exc)) from exc
        except Exception as exc:
            logger.exception("Candidate answer generation failed")
            raise HTTPException(status_code=500, detail="Candidate answer generation failed") from exc

        response = Response(
            interview_id=interview.id,
            round=body.round,
            question=transcript,
            transcript=candidate_answer,
            duration_seconds=response_duration_seconds,
            ai_speaking_duration_seconds=body.aiSpeakingDurationSeconds,
        )
        db.add(response)
        _log_audit_event(
            db,
            action="response_submitted",
            actor_type="candidate" if interview.invite_id else "trainer",
            invite_id=interview.invite_id,
            interview_id=interview.id,
            details={"round": body.round, "mode": "text_interviewer_eval"},
        )
        interview.current_round = body.round + 1
        if interview.status == "pending":
            interview.status = "in_progress"
        if interview.session_started_at is None:
            interview.session_started_at = now_utc()
        db.commit()

        return {
            "transcript": candidate_answer,
            "interviewerQuestion": transcript,
            "question": "",
            "round": interview.current_round,
            "isComplete": False,
        }

    response = Response(
        interview_id=interview.id,
        round=body.round,
        question=body.question,
        transcript=transcript,
        duration_seconds=response_duration_seconds,
        ai_speaking_duration_seconds=body.aiSpeakingDurationSeconds,
    )
    db.add(response)
    _log_audit_event(
        db,
        action="response_submitted",
        actor_type="candidate" if interview.invite_id else "trainer",
        invite_id=interview.invite_id,
        interview_id=interview.id,
        details={"round": body.round, "mode": "text"},
    )
    interview.current_round = body.round + 1
    if interview.status == "pending":
        interview.status = "in_progress"
    if interview.session_started_at is None:
        interview.session_started_at = now_utc()
    db.commit()

    prev_responses = (
        db.query(Response)
        .filter(Response.interview_id == interview.id)
        .order_by(Response.round)
        .all()
    )
    conversation_history = [
        {"question": r.question, "answer": r.transcript} for r in prev_responses
    ]

    try:
        question = generate_question_from_factory(
            category=test.category,
            test_title=test.title,
            test_context=test.context,
            rubrics=test.rubrics,
            total_rounds=test.rounds,
            current_round=interview.current_round,
            conversation_history=conversation_history,
            candidate_response=transcript,
            candidate_name=interview.candidate_name,
        )
    except OpenAIError as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=502, detail=_ai_failure_detail("Question generation", exc)) from exc
    except Exception as exc:
        logger.exception("Question generation failed")
        raise HTTPException(status_code=500, detail="Question generation failed") from exc

    return {
        "transcript": transcript,
        "question": question,
        "round": interview.current_round,
        "isComplete": False,
    }


@router.post("/interviews/{interview_id}/tts")
def text_to_speech(
    interview_id: int,
    body: TextToSpeechRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    interview, _, _ = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
    if interview.status == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")

    try:
        response = _openai.audio.speech.create(
            model=TTS_MODEL,
            voice="alloy",
            input=body.text,
            response_format="wav",
        )
    except OpenAIError as exc:
        logger.exception("Text-to-speech failed")
        raise HTTPException(status_code=502, detail=_ai_failure_detail("Text-to-speech", exc)) from exc
    except Exception as exc:
        logger.exception("Text-to-speech failed")
        raise HTTPException(status_code=500, detail="Text-to-speech failed") from exc

    audio_b64 = base64.b64encode(response.content).decode("utf-8")
    return {"audio": audio_b64, "format": "wav"}


def _finalize_interview_session(
    interview_id: int,
    db: Session,
    *,
    authorization: str | None,
    x_admin_token: str | None,
    x_trainer_token: str | None,
    x_invite_token: str | None,
):
    interview, invite, actor_type = _require_interview_access(
        interview_id=interview_id,
        db=db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )

    test = db.query(Test).filter(Test.id == interview.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    responses = (
        db.query(Response)
        .filter(Response.interview_id == interview.id)
        .order_by(Response.round)
        .all()
    )

    if interview.status == "completed":
        return _serialize_interview(interview)

    if interview.session_started_at is None:
        interview.session_started_at = now_utc()
    interview.session_ended_at = now_utc()

    metrics = _calculate_session_metrics(interview, responses)
    interview.session_started_at = metrics["sessionStartedAt"]
    interview.session_ended_at = metrics["sessionEndedAt"]
    interview.session_duration_seconds = metrics["timeSpentSeconds"]

    evaluation = None
    if responses:
        try:
            if _is_interviewer_evaluation_category(test.category):
                evaluation = evaluate_interviewer(
                    test_title=test.title,
                    test_context=test.context,
                    rubrics=test.rubrics,
                    responses=[
                        {"round": r.round, "question": r.question, "transcript": r.transcript}
                        for r in responses
                    ],
                    interviewer_name=interview.candidate_name,
                    time_spent_seconds=metrics["timeSpentSeconds"],
                )
            else:
                evaluation = evaluate_candidate(
                    test_title=test.title,
                    test_context=test.context,
                    rubrics=test.rubrics,
                    responses=[
                        {"round": r.round, "question": r.question, "transcript": r.transcript}
                        for r in responses
                    ],
                    candidate_name=interview.candidate_name,
                    time_spent_seconds=metrics["timeSpentSeconds"],
                )
        except OpenAIError as exc:
            logger.exception("Evaluation failed")
            raise HTTPException(status_code=502, detail=_ai_failure_detail("Evaluation", exc)) from exc
        except Exception as exc:
            logger.exception("Evaluation failed")
            raise HTTPException(status_code=500, detail="Evaluation failed") from exc

        # Upsert report
        existing = db.query(Report).filter(Report.interview_id == interview.id).first()
        if existing:
            existing.total_score = evaluation["totalScore"]
            existing.max_score = evaluation["maxScore"]
            existing.score_breakdown = evaluation["scoreBreakdown"]
            existing.strengths = evaluation["strengths"]
            existing.weaknesses = evaluation["weaknesses"]
            existing.improvements = evaluation["improvements"]
            existing.overall_justification = evaluation["overallJustification"]
            existing.time_spent_seconds = evaluation["timeSpentSeconds"]
            existing.listening_seconds = None
            existing.talking_seconds = None
            existing.listening_talking_ratio = None
        else:
            report = Report(
                interview_id=interview.id,
                candidate_name=interview.candidate_name,
                test_title=test.title,
                total_score=evaluation["totalScore"],
                max_score=evaluation["maxScore"],
                score_breakdown=evaluation["scoreBreakdown"],
                strengths=evaluation["strengths"],
                weaknesses=evaluation["weaknesses"],
                improvements=evaluation["improvements"],
                overall_justification=evaluation["overallJustification"],
                time_spent_seconds=evaluation["timeSpentSeconds"],
            )
            db.add(report)

    interview.status = "completed"
    interview.completed_at = metrics["sessionEndedAt"]

    if invite:
        invite.status = "completed" if invite.used_attempts >= invite.max_attempts else "started"

    _log_audit_event(
        db,
        action="interview_completed",
        actor_type=actor_type,
        invite_id=invite.id if invite else interview.invite_id,
        interview_id=interview.id,
    )

    db.commit()
    db.refresh(interview)

    return _serialize_interview(interview)


@router.post("/interviews/{interview_id}/end-session")
def end_session(
    interview_id: int,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _finalize_interview_session(
        interview_id,
        db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )


@router.post("/interviews/{interview_id}/complete")
def complete_interview(
    interview_id: int,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_trainer_token: str | None = Header(default=None),
    x_invite_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return _finalize_interview_session(
        interview_id,
        db,
        authorization=authorization,
        x_admin_token=x_admin_token,
        x_trainer_token=x_trainer_token,
        x_invite_token=x_invite_token,
    )
