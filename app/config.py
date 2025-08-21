from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    All variables are prefixed with APP_. See .env.example for defaults.
    """

    ocr_api_url: str = "http://localhost:8000/ocr"
    caption_api_url: str = "http://localhost:8001/caption"
    request_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", env_file_encoding="utf-8")


settings = Settings()

