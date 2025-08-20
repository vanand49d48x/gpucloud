import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):

    DATABASE_URL: str
    JWT_SECRET: str

    
    
    # AWS / infra
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_VPC_ID: str = ""
    AWS_SUBNET_ID: str = ""
    AWS_SECURITY_GROUP_ID: str = ""
    AWS_SSH_KEY_NAME: str = ""
    AWS_INSTANCE_PROFILE: str = ""  # Name (not ARN) of instance profile attached to instances
    BASE_AMI_ID: Optional[str] = None  # e.g., Ubuntu 22.04 AMI
    
    # Per-pod IAM and logging configuration
    AWS_POD_PERMISSIONS_BOUNDARY: Optional[str] = None  # ARN of permissions boundary for pod roles
    ENABLE_PER_POD_IAM: bool = True  # Enable per-pod IAM roles and instance profiles
    ENABLE_PER_POD_LOGGING: bool = True  # Enable per-pod CloudWatch log groups
    S3_BUCKET: Optional[str] = None  # Optional S3 bucket for pod data storage
    
    # Catalog and pricing
    AWS_CATALOG_REGIONS: list[str] = ["us-east-1"]  # regions you want to offer
    MARKUP_MULTIPLIER: float = 1.5  # 50% markup
    CATALOG_CACHE_TTL_SECONDS: int = 3600
    # Sync interval for status sync manager (seconds)
    SYNC_INTERVAL: int = 30  # Default to 30s, can be overridden by env
    
    class Config:
        env_file = os.getenv("GPUCLOUD_ENV_FILE", ".env")
        extra = "ignore"  # Ignore extra environment variables

settings = Settings()
