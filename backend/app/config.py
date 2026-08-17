from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "AetherCloud"
    database_url: str = Field(
        default="postgresql+psycopg://aethercloud:aethercloud@localhost:5432/aethercloud"
    )
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = Field(default="change-me-before-production")
    access_token_minutes: int = 60 * 8
    vps_prefix: str = "AETH"
    vps_starting_id: int = 10001
    default_admin_email: str = "admin@aethercloud.local"
    default_admin_username: str = "admin"
    default_admin_password: str = "AetherCloud@12345"
    lxd_binary: str = "lxc"
    lxd_storage_pool: str = "default"
    lxd_network: str = "lxdbr0"
    terminal_shell: str = "/bin/bash"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
