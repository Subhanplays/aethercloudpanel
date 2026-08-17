import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import admin, auth, terminal, vps
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import OSImage, Role, User
from app.security.auth import hash_password
from app.workers.expiration import expiration_loop

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(vps.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(terminal.router, prefix="/api")


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        existing = (await db.execute(select(OSImage))).first()
        if not existing:
            db.add_all(
                [
                    OSImage(label="Ubuntu 24.04", lxd_alias="images:ubuntu/24.04"),
                    OSImage(label="Ubuntu 22.04", lxd_alias="images:ubuntu/22.04"),
                    OSImage(label="Debian 12", lxd_alias="images:debian/12"),
                    OSImage(label="Debian 11", lxd_alias="images:debian/11"),
                ]
            )
            await db.commit()
        existing_admin = (
            await db.execute(select(User).where(User.email == settings.default_admin_email))
        ).scalar_one_or_none()
        if existing_admin is None:
            db.add(
                User(
                    email=settings.default_admin_email,
                    username=settings.default_admin_username,
                    password_hash=hash_password(settings.default_admin_password),
                    role=Role.super_admin,
                    is_active=True,
                    is_verified=True,
                )
            )
        else:
            existing_admin.username = settings.default_admin_username
            existing_admin.password_hash = hash_password(settings.default_admin_password)
            existing_admin.role = Role.super_admin
            existing_admin.is_active = True
            existing_admin.is_verified = True
        await db.commit()
    asyncio.create_task(expiration_loop())


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": settings.app_name}
