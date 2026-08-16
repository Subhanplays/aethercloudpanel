import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import admin, auth, terminal, vps
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import OSImage
from app.workers.expiration import expiration_loop

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
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
        existing = (await db.execute(select(OSImage))).scalar_one_or_none()
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
    asyncio.create_task(expiration_loop())


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": settings.app_name}
