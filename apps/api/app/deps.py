from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from apps.api.app.config import settings
from apps.api.app.db import get_session
from apps.api.app.models import User
from apps.api.app.security import parse_jwt

auth_scheme = HTTPBearer(auto_error=False)

def get_current_uid(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    uid = parse_jwt(credentials.credentials, settings.JWT_SECRET)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return uid

def current_user(session: Session = Depends(get_session), uid: str = Depends(get_current_uid)):
    user = session.query(User).filter(User.id == int(uid)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
