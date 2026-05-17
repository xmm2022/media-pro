from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GD Source-First Playback Gateway"
    openlist_base_url: str = Field("http://localhost:5244")
    openlist_token: str = Field("")
    rapid_copy_base_url: str = Field("http://localhost:9000")
    database_url: str = Field("sqlite:///./gateway.db")
    cookie_secret: str = Field("change-me-please")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_")


settings = Settings()
