from sqlmodel import SQLModel, create_engine, Session
from apps.api.app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

def get_session():
    with Session(engine) as session:
        yield session
