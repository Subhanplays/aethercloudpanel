from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import Role, VPSStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    username: str
    role: Role
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OSImageRead(BaseModel):
    id: int
    label: str
    lxd_alias: str
    enabled: bool

    model_config = {"from_attributes": True}


class VPSCreate(BaseModel):
    os_image_id: int
    cpu_cores: int = Field(ge=1, le=128)
    ram_mb: int = Field(ge=256)
    storage_gb: int = Field(ge=5)
    owner_id: int | None = None
    expires_days: int = Field(default=30, ge=1, le=3650)


class VPSRead(BaseModel):
    id: int
    vps_id: str
    instance_name: str
    owner_id: int
    status: VPSStatus
    cpu_cores: int
    ram_mb: int
    storage_gb: int
    ip_address: str | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VPSStats(BaseModel):
    status: str
    cpu_percent: float = 0
    ram_used_mb: float = 0
    ram_limit_mb: float = 0
    disk_used_gb: float = 0
    disk_limit_gb: float = 0
    network_rx_mb: float = 0
    network_tx_mb: float = 0
    uptime_seconds: int = 0


class PasswordResponse(BaseModel):
    password: str


class TmateRead(BaseModel):
    ssh_session: str | None
    web_session: str | None
    status: str


class ResourceSummary(BaseModel):
    host_cpu_cores: int
    host_ram_mb: int
    host_storage_gb: int
    allocated_cpu_cores: int
    allocated_ram_mb: int
    allocated_storage_gb: int
    available_cpu_cores: int
    available_ram_mb: int
    available_storage_gb: int
