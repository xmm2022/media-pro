from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GD Source-First Playback Gateway"
    openlist_base_url: str = Field("http://localhost:5244")
    openlist_token: str = Field("")
    openlist_admin_token: str = Field("")
    openlist_copy_verify_attempts: int = Field(30)
    openlist_copy_verify_interval_seconds: float = Field(1.0)
    rapid_copy_base_url: str = Field("http://localhost:9000")
    database_url: str = Field("sqlite:///./gateway.db")
    cookie_secret: str = Field("change-me-please")
    openlist_probe_path: str = Field("/Movies/sample.mkv")
    catalog_root_path: str = Field("/Movies")
    rapid_copy_donor_cookie: str = Field("")
    rapid_copy_target_cookie: str = Field("")
    rapid_copy_source_path: str = Field("/Movies/sample.mkv")
    rapid_copy_target_path: str = Field("/EmbyCache/sample.mkv")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_")


settings = Settings()
