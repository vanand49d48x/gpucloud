import datetime as dt
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGO = "HS256"

def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, hp: str) -> bool:
    return pwd.verify(p, hp)

def make_jwt(sub: str, secret: str, minutes: int = 60*24) -> str:
    now = dt.datetime.utcnow()
    exp = now + dt.timedelta(minutes=minutes)
    return jwt.encode({"sub": sub, "iat": now, "exp": exp}, secret, algorithm=ALGO)

def parse_jwt(token: str, secret: str) -> Optional[str]:
    try:
        data = jwt.decode(token, secret, algorithms=[ALGO])
        return data.get("sub")
    except JWTError:
        return None
