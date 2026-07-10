# backend/routes/trainer.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import secrets
from passlib.context import CryptContext

from backend.database import get_db
from backend.models import Trainer, Test, TrainerStatus, Participant  #v2upgrades
from backend.schemas import TrainerCreate, TrainerLogin, TrainerResponse, TestCreate, TestResponse, TestCodeUpdate  #v2upgrades

router = APIRouter(prefix="/trainer", tags=["Trainer"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generate_test_code() -> str:
    """Generate unique 8-character test code"""
    return secrets.token_urlsafe(6)[:8]

def _has_participant_activity(db: Session, test_id: int) -> bool:  #v2 upgrades
    return db.query(Participant).filter(Participant.test_id == test_id).first() is not None  #v2 upgrades


def _has_completed_attempts(db: Session, test_id: int) -> bool:  #v2 upgrades
    return db.query(Participant).filter(Participant.test_id == test_id, Participant.status == "completed").first() is not None  #v2 upgrades


def _serialize_trainer_test(db: Session, test: Test) -> dict:  #v2 upgrades
    has_participants = _has_participant_activity(db, test.id)  #v2 upgrades
    has_completed = _has_completed_attempts(db, test.id)  #v2 upgrades
    return {  #v2 upgrades
        "id": test.id,  #v2 upgrades
        "test_code": test.test_code,  #v2 upgrades
        "training_name": test.training_name,  #v2 upgrades
        "test_title": test.test_title,  #v2 upgrades
        "scenario": test.scenario,  #v2 upgrades
        "rubric": test.rubric,  #v2 upgrades
        "rubric_descriptions": test.rubric_descriptions,  #v2 upgrades
        "difficulty_level": test.difficulty_level,  #v2 upgrades
        "created_at": test.created_at,  #v2 upgrades
        "has_participants": has_participants,  #v2 upgrades
        "has_completed_attempts": has_completed,  #v2 upgrades
        "can_edit": not has_participants,  #v2 upgrades
        "can_delete": False,  #v2 upgrades
        "is_active": bool(test.is_active),  #v2 upgrades
    }  #v2 upgrades

@router.post("/register", response_model=TrainerResponse)
def register_trainer(trainer: TrainerCreate, db: Session = Depends(get_db)):
    """Register new trainer"""
    # Check if email exists
    existing = db.query(Trainer).filter(Trainer.email == trainer.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create trainer
    new_trainer = Trainer(
        name=trainer.name,
        email=trainer.email,
        password_hash=hash_password(trainer.password)
    )
    db.add(new_trainer)
    db.commit()
    db.refresh(new_trainer)
    
    return new_trainer

@router.post("/login")
def login_trainer(credentials: TrainerLogin, db: Session = Depends(get_db)):
    """Login trainer"""
    trainer = db.query(Trainer).filter(Trainer.email == credentials.email).first()
    trainer_status = db.query(TrainerStatus).filter(TrainerStatus.trainer_id == trainer.id).first() if trainer else None  #v2upgrades    

    if not trainer or not verify_password(credentials.password, trainer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if trainer_status and not trainer_status.is_active:  #v2upgrades
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trainer account is inactive")  #v2upgrades

    return {
        "message": "Login successful",
        "trainer_id": trainer.id,
        "name": trainer.name,
        "role": "trainer.role"  #v2upgrades
    }

@router.post("/create-test", response_model=TestResponse)
def create_test(test: TestCreate, trainer_id: int, db: Session = Depends(get_db)):
    """Create new communication test"""
    # Verify trainer exists
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    
    # Generate unique test code
    test_code = generate_test_code()
    while db.query(Test).filter(Test.test_code == test_code).first():
        test_code = generate_test_code()
    
    # Create test
    new_test = Test(
        test_code=test_code,
        training_name=test.test_title,  #v2upgrades
        scenario=test.scenario,
        rubric=test.rubric,
        rubric_descriptions=test.rubric_descriptions, #v2upgrades
        difficulty_level=test.difficulty_level,
        trainer_id=trainer_id
    )
    db.add(new_test)
    db.commit()
    db.refresh(new_test)
    
    return new_test

from fastapi import Body

@router.put("/update-test/{test_id}")
def update_test(test_id: int,test_data: dict = Body(...),
    trainer_id: int = None,  #v2 upgrades
    db: Session = Depends(get_db)
):
    test = db.get(Test, test_id)  #v2upgrades
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if trainer_id is None:  #v2 upgrades
        raise HTTPException(status_code=400, detail="trainer_id is required")  #v2 upgrades
    if test.trainer_id != trainer_id:  #v2 upgrades
        raise HTTPException(status_code=403, detail="Not allowed to modify this test")  #v2 upgrades
    if _has_participant_activity(db, test_id):  #v2 upgrades
        raise HTTPException(status_code=400, detail="Cannot modify test after a participant has started it")  #v2 upgrades
    
    # Update fields if they exist in the request
    test.training_name = test_data.get("test_title", test_data.get("training_name", test.training_name))  #v2 upgrades
    test.scenario = test_data.get("scenario", test.scenario)  #v2 upgrades
    test.rubric = test_data.get("rubric", test.rubric)  #v2 upgrades
    test.rubric_descriptions = test_data.get("rubric_descriptions", test.rubric_descriptions)  #v2 upgrades
    test.difficulty_level = test_data.get("difficulty_level", test.difficulty_level)  #v2 upgrades

    db.commit()  #v2 upgrades
    db.refresh(test)  #v2 upgrades
    return {"message": "Updated", "test": _serialize_trainer_test(db, test)}  #v2 upgrades


@router.put("/update-test-code/{test_id}")  #v2upgrades
def update_test_code(test_id: int, payload: TestCodeUpdate, trainer_id: int, db: Session = Depends(get_db)):  #v2upgrades
    test = db.get(Test, test_id)  #v2upgrades
    if not test:  #v2upgrades
        raise HTTPException(status_code=404, detail="Test not found")  #v2upgrades
    if test.trainer_id != trainer_id:  #v2upgrades
        raise HTTPException(status_code=403, detail="Not allowed to modify this test")  #v2upgrades
    if db.query(Test).filter(Test.test_code == payload.new_test_code, Test.id != test_id).first():  #v2upgrades
        raise HTTPException(status_code=400, detail="Test code already in use")  #v2upgrades
    if _has_participant_activity(db, test_id):  #v2 upgrades
        raise HTTPException(status_code=400, detail="Cannot modify test code after participants start using it")  #v2upgrades
    test.test_code = payload.new_test_code.strip()  #v2upgrades
    db.commit()  #v2upgrades
    return {"message": "Test code updated", "test_code": test.test_code}  #v2upgrades


@router.put("/tests/{test_id}/status")
def update_test_status(test_id: int, payload: dict = Body(...), trainer_id: int = None, db: Session = Depends(get_db)):
    test = db.get(Test, test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if trainer_id is None:
        raise HTTPException(status_code=400, detail="trainer_id is required")
    if test.trainer_id != trainer_id:
        raise HTTPException(status_code=403, detail="Not allowed to modify this test")
    if "is_active" not in payload:
        raise HTTPException(status_code=400, detail="is_active is required")

    test.is_active = bool(payload["is_active"])
    db.commit()
    db.refresh(test)
    return {"message": "Test status updated", "test": _serialize_trainer_test(db, test)}

@router.get("/tests/{trainer_id}", response_model=List[TestResponse])
def get_trainer_tests(trainer_id: int, db: Session = Depends(get_db)):
    """Get all tests created by trainer"""
    tests = db.query(Test).filter(Test.trainer_id == trainer_id).all()  #v2 upgrades
    return [_serialize_trainer_test(db, test) for test in tests]  #v2 upgrades

@router.get("/test/{test_code}", response_model=TestResponse)
def get_test_by_code(test_code: str, db: Session = Depends(get_db)):
    """Get test details by code"""
    test = db.query(Test).filter(Test.test_code == test_code).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test

@router.delete("/delete-test/{test_id}")
def delete_test(test_id: int, db: Session = Depends(get_db)):
    test = db.get(Test, test_id)  #v2 upgrades
    if not test:  #v2 upgrades
        raise HTTPException(status_code=404, detail="Test not found")  #v2 upgrades
    raise HTTPException(status_code=403, detail="Only admin can delete tests")  #v2 upgrades
