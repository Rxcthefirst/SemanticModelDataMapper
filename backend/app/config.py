"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "RDFMap Web"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:8080",
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ]

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string or list."""
        if isinstance(v, str):
            # Split by comma if it's a string
            return [origin.strip() for origin in v.split(',')]
        return v

    # Database
    DATABASE_URL: str = "postgresql://rdfmap:rdfmap@db:5432/rdfmap"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File Upload
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    UPLOAD_DIR: str = "/app/uploads"
    DATA_DIR: str = "/app/data"

    # RDFMap Settings
    RDFMAP_USE_SEMANTIC: bool = True
    RDFMAP_SEMANTIC_THRESHOLD: float = 0.7
    RDFMAP_MIN_CONFIDENCE: float = 0.5

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()

