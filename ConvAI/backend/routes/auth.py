from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import create_trainer_session_token, require_trainer_access, verify_password
from database import TrainerAccount, get_db

router = APIRouter()


class TrainerLoginRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]
    password: Annotated[str, StringConstraints(min_length=1)]


def _serialize_trainer(trainer: TrainerAccount) -> dict:
    return {
        "id": trainer.id,
        "email": trainer.email,
        "status": trainer.status,
        "createdAt": trainer.created_at,
        "updatedAt": trainer.updated_at,
    }


@router.post("/auth/trainer/login")
def trainer_login(body: TrainerLoginRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    trainer = db.query(TrainerAccount).filter(func.lower(TrainerAccount.email) == email).first()
    if not trainer or not verify_password(body.password, trainer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if trainer.status != "active":
        raise HTTPException(status_code=403, detail="Trainer account is inactive")

    token = create_trainer_session_token(trainer_id=trainer.id, email=trainer.email)
    return {"token": token, "trainer": _serialize_trainer(trainer)}


@router.get("/auth/trainer/me")
def trainer_me(
    principal=Depends(require_trainer_access),
    db: Session = Depends(get_db),
):
    if principal.role == "admin":
        return {"role": "admin", "trainer": None}

    trainer = db.query(TrainerAccount).filter(TrainerAccount.id == principal.trainer_id).first()
    if not trainer or trainer.status != "active":
        raise HTTPException(status_code=401, detail="Trainer account is inactive")
    return {"role": "trainer", "trainer": _serialize_trainer(trainer)}
