from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AIPAL LAB Analysis API"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "info"
    cors_origins: str = "http://localhost:3000"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 120
    api_key: str = ""  # A(대시보드) 인증용. 비어 있으면 개발 환경에서만 인증 생략
    calc_engine_url: str = "http://localhost:8100"
    calc_mode: str = "http"  # http(실제 엔진) | mock(개발/테스트 전용)
    calc_timeout_seconds: float = 30
    calc_dataset_id: str = "commercial_area_v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()