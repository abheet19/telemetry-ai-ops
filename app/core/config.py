import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute absolute path to .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")

# Load .env manually (important for pytest + Docker)
load_dotenv(DOTENV_PATH)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    Provides a fallback default for test/Docker environments.
    """
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ✅ Provide a fallback so tests/Docker won't fail if .env isn't loaded
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "mock_key")


settings = Settings()