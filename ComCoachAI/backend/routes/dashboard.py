#backend/routes/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List
import os

from backend.database import get_db
from backend.models import Test, Participant
from backend.schemas import DashboardStats, ParticipantResponse
from backend.services.report_generator import generate_excel_report
from backend.config import get_settings
from backend.services.storage import s3_enabled, upload_report_file

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings = get_settings()

# Ensure report directory exists
settings.report_dir_path.mkdir(parents=True, exist_ok=True)

@router.get("/stats/{test_code}", response_model=DashboardStats)
def get_test_statistics(test_code: str, db: Session = Depends(get_db)):
    """Get comprehensive statistics for a test"""
    
    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Get ALL participants
    all_participants = db.query(Participant).filter(Participant.test_id == test.id).all()
    
    # Filter only COMPLETED participants (those with scores)
    participants = [p for p in all_participants if p.total_score is not None and p.scores is not None]
    
    if not participants:
        return DashboardStats(
            total_participants=0,
            average_score=0.0,
            weak_areas=[],
            participants=[]
        )
    
    # Calculate average score (safe now because we filtered)
    total_participants = len(participants)
    average_score = sum(p.total_score for p in participants) / total_participants
    
    # Calculate weak areas (skills with lowest average)
    skill_averages = {}
    for skill in test.rubric.keys():
        scores = [p.scores.get(skill, 0) for p in participants if p.scores and skill in p.scores]
        if scores:
            skill_averages[skill] = sum(scores) / len(scores)
    
    # Sort by score (ascending) to get weak areas
    weak_areas = [
        {"skill": skill, "average": round(avg, 2)}
        for skill, avg in sorted(skill_averages.items(), key=lambda x: x[1])[:3]
    ]
    
    return DashboardStats(
        total_participants=total_participants,
        average_score=round(average_score, 2),
        weak_areas=weak_areas,
        participants=participants
    )

@router.get("/participants/{test_code}", response_model=List[ParticipantResponse])
def get_test_participants(test_code: str, db: Session = Depends(get_db)):
    """Get all participants for a test"""
    
    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    participants = db.query(Participant).filter(Participant.test_id == test.id).all()
    return participants
    
@router.get("/download-report/{test_code}")
def download_test_report(test_code: str, db: Session = Depends(get_db)):
    """Generate and download Excel report for a test"""
    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    participants = db.query(Participant).filter(
        Participant.test_id == test.id,
        Participant.total_score.isnot(None)  # Only completed participants
    ).all()
    
    if not participants:
        raise HTTPException(status_code=404, detail="No completed participants found")
    
    try:
        report_path = generate_excel_report(test, participants)
        
        if not os.path.exists(report_path):
            raise HTTPException(status_code=500, detail="Report generation failed")

        if s3_enabled():
            _, presigned_url = upload_report_file(report_path, os.path.basename(report_path))
            os.remove(report_path)
            return RedirectResponse(url=presigned_url, status_code=307)
        
        return FileResponse(
            path=report_path,
            filename=f"{test.test_title}_{test_code}_report.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
