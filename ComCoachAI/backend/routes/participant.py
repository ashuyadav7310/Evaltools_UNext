from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import logging
import os
import re
from datetime import datetime, timezone, timedelta

from backend.database import get_db
from backend.models import Participant, Test
from backend.schemas import ParticipantResponse
from backend.services.audio_processing import convert_audio_to_wav, validate_audio_file, compress_audio_for_transcription  #compressor
from backend.services.speech_to_text import transcribe_audio
from backend.services.ai_evaluation import evaluate_communication, validate_transcript_quality
from backend.services.audio_analyzer import analyze_audio_quality
from backend.config import get_settings
from backend.services.storage import s3_enabled, upload_audio_file

router = APIRouter(prefix="/participant", tags=["Participant"])
settings = get_settings()
logger = logging.getLogger(__name__)

settings.upload_dir_path.mkdir(parents=True, exist_ok=True)
IST = timezone(timedelta(hours=5, minutes=30))


def _safe_filename_token(value: str, fallback: str) -> str:
    """Normalize text so it is safe to use in file names on Windows/Linux."""
    if not value:
        return fallback
    token = value.strip().lower()
    token = re.sub(r"\s+", "_", token)
    token = re.sub(r"[^a-zA-Z0-9_-]", "", token)
    return token or fallback


@router.get("/test/{test_code}")
def get_test_for_participant(test_code: str, db: Session = Depends(get_db)):
    """Get test scenario for participant"""
    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if not test.is_active:
        raise HTTPException(status_code=403, detail="This test code is currently inactive")

    return {
        "test_id": test.id,
        "test_title": test.test_title,
        "training_name": test.training_name,
        "scenario": test.scenario,
        "difficulty_level": test.difficulty_level
    }


@router.post("/start")
def start_test(
    test_code: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register participant for test"""
    name = name.strip()
    email = email.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if not test.is_active:
        raise HTTPException(status_code=403, detail="This test code is currently inactive")

    participant = Participant(
        name=name,
        email=email,
        test_id=test.id
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    return {
        "participant_id": participant.id,
        "message": "Registration successful"
    }


@router.post("/submit-audio/{participant_id}")
async def submit_audio(
    participant_id: int,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Process participant audio submission with full audio analysis"""

    stt_audio_path = None  #compressor
    audio_path = None  #compressor

    # Get participant and test
    participant = db.query(Participant).filter(
        Participant.id == participant_id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    test = db.query(Test).filter(Test.id == participant.test_id).first()

    try:
        # ── Step 1: Save uploaded audio ──────────────────────
        file_extension = audio_file.filename.split('.')[-1].lower() if '.' in audio_file.filename else 'wav'
        participant_token = _safe_filename_token(participant.name, "participant")
        test_code_token = _safe_filename_token(test.test_code if test else "test", "test")
        timestamp_token = datetime.now(IST).strftime("%Y%m%d_%H%M%S_%f")
        unique_filename = f"{participant_token}_{test_code_token}_{timestamp_token}.{file_extension}"
        audio_path = str(settings.upload_dir_path / unique_filename)

        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)

        participant.status = "processing"
        db.commit()

        # ── Step 2: Convert to WAV if needed ─────────────────
        wav_path = audio_path.replace(f".{file_extension}", ".wav")
        if file_extension.lower() != "wav":
            try:
                convert_audio_to_wav(audio_path, wav_path)
                os.remove(audio_path)
                audio_path = wav_path
            except Exception as e:
                # If conversion fails, use original file
                logger.warning("Audio conversion warning: %s", e)
                wav_path = audio_path

        # Validate audio
        if not validate_audio_file(audio_path):
            raise HTTPException(status_code=400, detail="Invalid audio file")

        # ── Step 3: DIRECT AUDIO ANALYSIS ────────────────────
        # Analyze the RAW audio for pauses, energy, fluency
        # This captures what STT APIs clean/remove
        logger.info("Analyzing audio: %s", audio_path)
        audio_metrics = analyze_audio_quality(audio_path)
        logger.info(
            "Audio analysis: %s pauses, fluency=%s, speech=%s%%",
            audio_metrics["num_pauses"],
            audio_metrics["fluency_score"],
            audio_metrics["speech_ratio_percent"],
        )

        # ── Step 4: Speech to Text ────────────────────────────
        logger.info("Compressing audio for STT")
        stt_audio_path = compress_audio_for_transcription(audio_path)  #compressor
        logger.info(
            "STT audio ready: %s (%s bytes)",
            os.path.basename(stt_audio_path),
            os.path.getsize(stt_audio_path),
        )

        logger.info("Transcribing audio")
        transcript = transcribe_audio(stt_audio_path)  #compressor
        logger.info("Transcript received (%s words)", len(transcript.split()))


        # ── Step 5: Validate transcript ───────────────────────
        is_valid, error_msg = validate_transcript_quality(transcript)

        if not is_valid:
            # No valid speech - score 0 but still show audio analysis
            scores = {skill: 0 for skill in test.rubric.keys()}
            total_score = 0.0
            strengths = "No valid speech detected in the audio."
            improvements = (
                f"{error_msg}\n\n"
                f"🎙️ Audio Analysis: "
                f"Duration {audio_metrics['duration_seconds']:.1f}s | "
                f"Active speech {audio_metrics['speech_ratio_percent']:.0f}%\n"
                f"{audio_metrics['feedback']}"
            )
        elif audio_metrics and audio_metrics.get('speech_ratio_percent', 0) < 5:
            # Audio exists but is essentially silent
            scores       = {skill: 0 for skill in test.rubric.keys()}
            total_score  = 0.0
            strengths    = "1. No speech detected – Audio was recorded but appears to be silent or too quiet."
            improvements = (
                "1. Record again – Ensure your microphone is working and speak clearly into it. "
                f"Only {audio_metrics['speech_ratio_percent']:.1f}% of your audio contained detectable speech."
            )

        else:
            # ── Step 6: AI Evaluation ─────────────────────────
            logger.info("Evaluating transcript with AI")
            scores, total_score, strengths, improvements = evaluate_communication(
                transcript=transcript,
                scenario=test.scenario,
                rubric=test.rubric,
                rubric_descriptions=test.rubric_descriptions,
                difficulty_level=test.difficulty_level,
                audio_metrics=audio_metrics  # Pass real audio data!
            )
            logger.info("Evaluation complete. Score: %.1f%%", total_score)

        # ── Step 7: Save to database ──────────────────────────
        final_audio_reference = audio_path
        if s3_enabled():
            final_audio_reference = upload_audio_file(audio_path, os.path.basename(audio_path))

        participant.audio_path = final_audio_reference
        participant.transcript = transcript
        participant.scores = scores
        participant.total_score = total_score
        participant.strengths = strengths
        participant.improvements = improvements
        participant.retake_allowed = False
        participant.status = "completed"

        db.commit()
        db.refresh(participant)

        if s3_enabled() and os.path.exists(audio_path):
            os.remove(audio_path)

        # ── Step 8: Return full result ────────────────────────
        return {
            "participant_id": participant.id,
            "transcript": transcript,
            "scores": scores,
            "total_score": round(total_score, 2),
            "strengths": strengths,
            "improvements": improvements,
            # Real audio analysis data
            "audio_analysis": {
                "duration_seconds": audio_metrics["duration_seconds"],
                "total_speech_seconds": audio_metrics["total_speech_seconds"],
                "total_pause_seconds": audio_metrics["total_pause_seconds"],
                "speech_ratio_percent": audio_metrics["speech_ratio_percent"],
                "num_pauses": audio_metrics["num_pauses"],
                "avg_pause_duration": audio_metrics["avg_pause_duration"],
                "pauses_per_minute": audio_metrics["pauses_per_minute"],
                "pauses": audio_metrics["pauses"],
                "fluency_score": audio_metrics["fluency_score"],
                "fluency_feedback": audio_metrics["feedback"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        participant.status = "pending"
        db.commit()
        logger.exception("Participant audio processing failed for participant_id=%s", participant_id)
        raise HTTPException(
            status_code=503 if "OpenAI" in str(e) or "Speech-to-text" in str(e) else 500,
            detail=f"Processing failed: {str(e)}"
        )
    finally:
        if stt_audio_path and stt_audio_path != audio_path and os.path.exists(stt_audio_path):  #compressor
            try:
                os.remove(stt_audio_path)  #compressor
            except OSError:
                logger.warning("Could not remove temporary STT file: %s", stt_audio_path, exc_info=True)

@router.get("/retake-status/{participant_id}")
def get_retake_status(participant_id: int, db: Session = Depends(get_db)):
    """Participant checks if trainer approved retake."""
    p = db.query(Participant).filter(Participant.id == participant_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
    return {"retake_allowed": bool(p.retake_allowed)}


@router.post("/approve-retake/{participant_id}")
def approve_retake(participant_id: int, db: Session = Depends(get_db)):
    """Trainer approves retake for a participant."""
    p = db.query(Participant).filter(Participant.id == participant_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
    p.retake_allowed = True
    db.commit()
    return {"message": f"Retake approved for {p.name}"}

@router.get("/result/{participant_id}", response_model=ParticipantResponse)
def get_participant_result(participant_id: int, db: Session = Depends(get_db)):
    """Get participant result"""
    participant = db.query(Participant).filter(
        Participant.id == participant_id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    return participant
