import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    user = "user"
    admin = "admin"
    super_admin = "super_admin"


class VPSStatus(str, enum.Enum):
    deploying = "deploying"
    running = "running"
    stopped = "stopped"
    expired = "expired"
    suspended = "suspended"
    error = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vps: Mapped[list["VPS"]] = relationship(back_populates="owner")


class OSImage(Base):
    __tablename__ = "os_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120), unique=True)
    lxd_alias: Mapped[str] = mapped_column(String(180), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    cpu_cores: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    storage_gb: Mapped[int] = mapped_column(Integer)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class VPS(Base):
    __tablename__ = "vps"
    __table_args__ = (UniqueConstraint("vps_id"), UniqueConstraint("instance_name"))

    id: Mapped[int] = mapped_column(primary_key=True)
    vps_id: Mapped[str] = mapped_column(String(40), index=True)
    instance_name: Mapped[str] = mapped_column(String(80), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    os_image_id: Mapped[int] = mapped_column(ForeignKey("os_images.id"))
    status: Mapped[VPSStatus] = mapped_column(Enum(VPSStatus), default=VPSStatus.deploying)
    cpu_cores: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    storage_gb: Mapped[int] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped[User] = relationship(back_populates="vps")
    os_image: Mapped[OSImage] = relationship()


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    vps_id: Mapped[int] = mapped_column(ForeignKey("vps.id"), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vps_id: Mapped[int] = mapped_column(ForeignKey("vps.id"), index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TmateSession(Base):
    __tablename__ = "tmate_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    vps_id: Mapped[int] = mapped_column(ForeignKey("vps.id"), index=True)
    ssh_session: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_session: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Branding(Base):
    __tablename__ = "branding"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    site_name: Mapped[str] = mapped_column(String(120), default="AetherCloud")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(20), default="#2f6fed")
    accent_color: Mapped[str] = mapped_column(String(20), default="#14b8a6")
    sidebar_color: Mapped[str] = mapped_column(String(20), default="#111827")
    background: Mapped[dict] = mapped_column(JSON, default=dict)
