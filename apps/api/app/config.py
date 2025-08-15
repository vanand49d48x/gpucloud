from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://gpucloud:gpucloud@localhost:5432/gpucloud"
    JWT_SECRET: str = "change-me"
    
    # AWS / infra
    AWS_REGION: str = "us-east-1"
    AWS_SUBNET_ID: str = ""
    AWS_SECURITY_GROUP_ID: str = ""
    AWS_SSH_KEY_NAME: str = ""
    AWS_INSTANCE_PROFILE: str = ""  # Name (not ARN) of instance profile attached to instances
    BASE_AMI_ID: str | None = None  # e.g., Ubuntu 22.04 AMI
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables

settings = Settings()
