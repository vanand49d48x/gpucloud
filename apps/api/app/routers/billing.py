from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from apps.api.app.db import get_session
from apps.api.app.models import Credits
from apps.api.app.deps import current_user

router = APIRouter(prefix="/v1/billing", tags=["billing"])

@router.get("/me")
def my_credits(session: Session = Depends(get_session), user=Depends(current_user)):
    c = session.query(Credits).filter(Credits.user_id == user.id).first()
    return {"user_id": user.id, "balance_cents": c.balance_cents if c else 0}
