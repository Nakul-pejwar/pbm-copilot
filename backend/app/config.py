from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/pbm"
    claude_api_key: str = ""
    claude_model: str = "claude-haiku-4-5"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
