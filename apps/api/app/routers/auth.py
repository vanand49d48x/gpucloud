from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from apps.api.app.db import get_session
from apps.api.app.models import User, Credits
from apps.api.app.security import hash_password, verify_password, make_jwt
from apps.api.app.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])

class SignupIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/signup", response_model=TokenOut)
def signup(body: SignupIn, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user); session.commit(); session.refresh(user)
    # give new user 0 credits row
    credits = Credits(user_id=user.id, balance_cents=0)
    session.add(credits); session.commit()
    token = make_jwt(str(user.id), settings.JWT_SECRET)
    return TokenOut(access_token=token)

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    token = make_jwt(str(user.id), settings.JWT_SECRET)
    return TokenOut(access_token=token)
