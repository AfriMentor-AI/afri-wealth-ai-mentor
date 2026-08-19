from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/users/{user_id}/daily-action", response_model=schemas.DailyActionResponse)
def get_daily_action_for_user(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the most recent daily action for a given user.
    """
    daily_action = (
        db.query(models.DailyAction)
        .filter(models.DailyAction.user_id == user_id)
        .order_by(models.DailyAction.created_at.desc())
        .first()
    )
    if not daily_action:
        raise HTTPException(status_code=404, detail="Daily action not found for this user.")
    return daily_action
