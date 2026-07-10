from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import hash_password, require_admin_access
from database import TrainerAccount, get_db

router = APIRouter()


class CreateTrainerRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]
    password: Annotated[str, StringConstraints(min_length=6)]


class UpdateTrainerRequest(BaseModel):
    password: Annotated[str, StringConstraints(min_length=6)] | None = None
    status: Annotated[str, StringConstraints(strip_whitespace=True)] | None = None


def _serialize_trainer(trainer: TrainerAccount) -> dict:
    return {
        "id": trainer.id,
        "email": trainer.email,
        "status": trainer.status,
        "createdAt": trainer.created_at,
        "updatedAt": trainer.updated_at,
    }


@router.get("/admin/trainers")
def list_trainers(
    _: None = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    trainers = db.query(TrainerAccount).order_by(TrainerAccount.created_at.desc()).all()
    return [_serialize_trainer(trainer) for trainer in trainers]


@router.post("/admin/trainers", status_code=201)
def create_trainer(
    body: CreateTrainerRequest,
    _: None = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    email = body.email.lower()
    existing = db.query(TrainerAccount).filter(func.lower(TrainerAccount.email) == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Trainer email already exists")

    trainer = TrainerAccount(email=email, password_hash=hash_password(body.password), status="active")
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    return _serialize_trainer(trainer)


@router.patch("/admin/trainers/{trainer_id}")
def update_trainer(
    trainer_id: int,
    body: UpdateTrainerRequest,
    _: None = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    trainer = db.query(TrainerAccount).filter(TrainerAccount.id == trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    if body.status is not None:
        status = body.status.lower()
        if status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Status must be active or inactive")
        trainer.status = status
    if body.password:
        trainer.password_hash = hash_password(body.password)

    db.commit()
    db.refresh(trainer)
    return _serialize_trainer(trainer)
