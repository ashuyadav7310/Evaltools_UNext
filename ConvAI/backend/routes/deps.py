from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from auth import AuthPrincipal, require_trainer_access
from database import TrainerAccount, get_db


def require_active_trainer_access(
    principal: AuthPrincipal = Depends(require_trainer_access),
    db: Session = Depends(get_db),
) -> AuthPrincipal:
    if principal.role == "admin":
        raise HTTPException(status_code=403, detail="Trainer login is required")

    trainer = db.query(TrainerAccount).filter(TrainerAccount.id == principal.trainer_id).first()
    if not trainer or trainer.status != "active":
        raise HTTPException(status_code=401, detail="Trainer account is inactive")

    return principal
