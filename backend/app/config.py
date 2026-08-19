from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/pbm"
    claude_api_key: str = ""
    claude_model: str = "claude-haiku-4-5"
    superset_url: str = "http://superset:8088"
    superset_public_url: str = "http://localhost:8088"
    superset_username: str = "admin"
    superset_password: str = "admin"
    superset_origin: str = "http://localhost:8088"
    api_public_url: str = "http://localhost:8000"
    api_token: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
