from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BoutiqueOS"
    environment: str = "development"
    database_url: str = "sqlite:///./boutiqueos.db"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    hold_ttl_hours: int = 24
    hold_default_ttl_hours: int = 24
    remnant_threshold_m: Decimal = Decimal("0.5")
    media_storage_path: str = "./data/media"
    media_max_image_mb: int = 10
    media_max_video_mb: int = 100
    integration_processing_batch_size: int = 20
    integration_retry_limit: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def hold_ttl_hours_value(self) -> int:
        return self.hold_ttl_hours or self.hold_default_ttl_hours


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
