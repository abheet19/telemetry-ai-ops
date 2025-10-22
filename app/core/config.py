from pydantic import BaseSettings

class Settings(BaseSettings):
    app_env:str
    app_name:str

    class Config:
        env_file=".env"

Settings = Settings()
