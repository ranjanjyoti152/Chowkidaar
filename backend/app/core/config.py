"""
Chowkidaar NVR - Configuration Module
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Chowkidaar"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "change-this-secret-key"
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/chowkidaar"
    database_sync_url: str = "postgresql://postgres:password@localhost:5432/chowkidaar"
    
    # JWT
    jwt_secret_key: str = "jwt-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_vlm_model: str = "llava"
    ollama_chat_model: str = "llama3.2"
    
    # YOLO
    yolo_model_path: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.5
    yolo_classes: str = "person,car,truck,fire,smoke,dog,cat"
    
    # Streaming
    stream_buffer_size: int = 10
    stream_reconnect_delay: int = 5
    max_concurrent_streams: int = 10
    
    # Storage
    events_storage_path: str = "./storage/events"
    frames_storage_path: str = "./storage/frames"
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Redis
    redis_url: Optional[str] = None
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def yolo_classes_list(self) -> List[str]:
        return [cls.strip() for cls in self.yolo_classes.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
