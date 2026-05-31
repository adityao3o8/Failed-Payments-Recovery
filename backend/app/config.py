from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Use SQLite for local dev without Docker; switch to Postgres for production
    database_url: str = "sqlite:///./recover.db"
    redis_url: str = "redis://localhost:6379/0"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    max_retries: int = 4
    default_retry_enabled: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
