from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class GPUInstance(BaseModel):
    id: str
    name: str
    instance_type: str
    gpu_count: int
    status: str
    created_at: datetime
    terminated_at: Optional[datetime] = None

class User(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime
    is_active: bool = True
