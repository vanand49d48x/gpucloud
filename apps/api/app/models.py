from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class PodStatus(str, Enum):
    pending="pending"; starting="starting"; running="running"
    stopping="stopping"; stopped="stopped"; error="error"

class Provider(str, Enum):
    aws="aws"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Credits(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    balance_cents: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Pod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    status: PodStatus = Field(default=PodStatus.pending)
    provider: Provider = Field(default=Provider.aws)
    instance_id: Optional[str] = None
    instance_type: Optional[str] = None  # Store the AWS instance type
    public_ip: Optional[str] = None
    gpu_type: Optional[str] = None
    vram_gb: Optional[int] = None
    hourly_rate_cents: int
    volume_s3_prefix: Optional[str] = None
    storage_expansion_history: Optional[str] = None  # JSON string of storage expansion events
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Usage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pod_id: int = Field(index=True, foreign_key="pod.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    gpu_seconds: int = 0
    bill_cents: int = 0
