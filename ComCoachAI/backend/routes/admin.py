from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from backend.config import get_settings
from backend.database import get_db
from backend.models import Trainer, Test, Participant, TrainerStatus  #v2upgrades
from backend.utils.helpers import to_ist_str  #v2upgrades

router = APIRouter(prefix="/admin", tags=["Admin"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminTrainerCreate(BaseModel):
    email: EmailStr
    password: str


def verify_admin_token(x_admin_token: str = Header(default="")):
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/overview", dependencies=[Depends(verify_admin_token)])
def get_admin_overview(db: Session = Depends(get_db)):
    trainer_count = db.query(Trainer).count()
    test_count = db.query(Test).count()
    participant_count = db.query(Participant).count()
    completed_count = db.query(Participant).filter(Participant.total_score.isnot(None)).count()

    return {
        "trainers": trainer_count,
        "tests": test_count,
        "participants": participant_count,
        "completed_submissions": completed_count
    }


@router.post("/trainers", dependencies=[Depends(verify_admin_token)])
def create_trainer(payload: AdminTrainerCreate, db: Session = Depends(get_db)):
    existing = db.query(Trainer).filter(Trainer.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Trainer email already exists")

    trainer = Trainer(
        name=str(payload.email).split("@")[0],  #v2upgrades
        email=str(payload.email).strip().lower(),
        password_hash=pwd_context.hash(payload.password)
    )
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    status_row = TrainerStatus(trainer_id=trainer.id, is_active=True)  #v2upgrades
    db.add(status_row)  #v2upgrades
    db.commit()  #v2upgrades

    return {
        "message": "Trainer created",
        "trainer_id": trainer.id,
        "name": trainer.name,
        "email": trainer.email
    }


@router.get("/trainers", dependencies=[Depends(verify_admin_token)])
def get_trainers(db: Session = Depends(get_db)):
    trainers = db.query(Trainer).all()
    status_map = {s.trainer_id: s.is_active for s in db.query(TrainerStatus).all()}  #v2upgrades
    return [
        {
            "id": trainer.id,
            "name": trainer.name,
            "email": trainer.email,
            "created_at": to_ist_str(trainer.created_at),  #v2upgrades
            "tests_count": len(trainer.tests),
            "is_active": status_map.get(trainer.id, True)  #v2upgrades
        }
        for trainer in trainers
    ]


@router.put("/trainers/{trainer_id}/deactivate", dependencies=[Depends(verify_admin_token)])  #v2upgrades
def deactivate_trainer(trainer_id: int, db: Session = Depends(get_db)):  #v2upgrades
    trainer = db.get(Trainer, trainer_id)
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    status_row = db.query(TrainerStatus).filter(TrainerStatus.trainer_id == trainer_id).first()  #v2upgrades
    if not status_row:  #v2upgrades
        status_row = TrainerStatus(trainer_id=trainer_id, is_active=False)  #v2upgrades
        db.add(status_row)  #v2upgrades
    else:  #v2upgrades
        status_row.is_active = False  #v2upgrades
    db.commit()  #v2upgrades
    return {"message": "Trainer marked inactive"}  #v2upgrades


@router.put("/trainers/{trainer_id}/activate", dependencies=[Depends(verify_admin_token)])  #v2upgrades
def activate_trainer(trainer_id: int, db: Session = Depends(get_db)):  #v2upgrades
    trainer = db.get(Trainer, trainer_id)  #v2upgrades
    if not trainer:  #v2upgrades
        raise HTTPException(status_code=404, detail="Trainer not found")  #v2upgrades
    status_row = db.query(TrainerStatus).filter(TrainerStatus.trainer_id == trainer_id).first()  #v2upgrades
    if not status_row:  #v2upgrades
        status_row = TrainerStatus(trainer_id=trainer_id, is_active=True)  #v2upgrades
        db.add(status_row)  #v2upgrades
    else:  #v2upgrades
        status_row.is_active = True  #v2upgrades
    db.commit()  #v2upgrades
    return {"message": "Trainer activated"}  #v2upgrades


@router.get("/tests", dependencies=[Depends(verify_admin_token)])
def get_tests(db: Session = Depends(get_db)):
    tests = db.query(Test).all()
    return [
        {
            "id": test.id,
            "test_code": test.test_code,
            "test_title": test.test_title,  #v2upgrades
            "difficulty_level": test.difficulty_level,
            "trainer_id": test.trainer_id,
            "participants_count": len(test.participants),
            "is_active": bool(test.is_active),
            "created_at": to_ist_str(test.created_at)  #v2upgrades
        }
        for test in tests
    ]


@router.get("/participants", dependencies=[Depends(verify_admin_token)])  #v2upgrades
def get_participants(db: Session = Depends(get_db)):  #v2upgrades
    participants = db.query(Participant).all()  #v2upgrades
    return [  #v2upgrades
        {
            "id": participant.id,
            "name": participant.name,
            "email": participant.email,
            "status": participant.status,
            "total_score": participant.total_score,
            "test_code": participant.test.test_code if participant.test else None,
            "test_title": participant.test.test_title if participant.test else None,
            "trainer_id": participant.test.trainer_id if participant.test else None,
            "completed_at": to_ist_str(participant.completed_at)  #v2upgrades
        }
        for participant in participants
    ]


@router.delete("/tests/{test_id}", dependencies=[Depends(verify_admin_token)])
def delete_test(test_id: int, db: Session = Depends(get_db)):
    test = db.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    db.query(Participant).filter(Participant.test_id == test_id).delete(synchronize_session=False)  #v2upgrades
    db.delete(test)  #v2upgrades
    db.commit()  #v2upgrades
    return {"message": "Test deleted"}  #v2upgrades
