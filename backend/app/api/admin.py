from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Branding, OSImage, TerminalSession, User, VPS, VPSStatus
from app.schemas import OSImageRead, ResourceSummary, UserRead, VPSRead
from app.security.auth import require_admin
from app.services.resources import assert_capacity, get_resource_summary

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    users = (await db.execute(select(User))).scalars().all()
    vps = (await db.execute(select(VPS))).scalars().all()
    resources = await get_resource_summary(db)
    return {
        "users": len(users),
        "vps": len(vps),
        "running": len([item for item in vps if item.status == VPSStatus.running]),
        "stopped": len([item for item in vps if item.status == VPSStatus.stopped]),
        "expired": len([item for item in vps if item.status == VPSStatus.expired]),
        "resources": resources.model_dump(),
    }


@router.get("/users", response_model=list[UserRead])
async def users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars())


@router.get("/vps", response_model=list[VPSRead])
async def all_vps(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[VPS]:
    result = await db.execute(select(VPS).order_by(VPS.created_at.desc()))
    return list(result.scalars())


@router.post("/vps/{vps_id}/renew", response_model=VPSRead)
async def renew_vps(vps_id: str, days: int = 30, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> VPS:
    vps = (await db.execute(select(VPS).where(VPS.vps_id == vps_id))).scalar_one_or_none()
    if not vps:
        raise HTTPException(status_code=404, detail="VPS not found")
    base = vps.expires_at if vps.expires_at and vps.expires_at > datetime.utcnow() else datetime.utcnow()
    vps.expires_at = base + timedelta(days=days)
    if vps.status == VPSStatus.expired:
        vps.status = VPSStatus.stopped
    await db.commit()
    await db.refresh(vps)
    return vps


@router.post("/vps/{vps_id}/resources", response_model=VPSRead)
async def change_resources(
    vps_id: str,
    cpu_cores: int,
    ram_mb: int,
    storage_gb: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> VPS:
    vps = (await db.execute(select(VPS).where(VPS.vps_id == vps_id))).scalar_one_or_none()
    if not vps:
        raise HTTPException(status_code=404, detail="VPS not found")
    await assert_capacity(db, max(cpu_cores - vps.cpu_cores, 0), max(ram_mb - vps.ram_mb, 0), max(storage_gb - vps.storage_gb, 0))
    vps.cpu_cores = cpu_cores
    vps.ram_mb = ram_mb
    vps.storage_gb = storage_gb
    await db.commit()
    await db.refresh(vps)
    return vps


@router.get("/terminal-sessions")
async def terminal_sessions(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    rows = (await db.execute(select(TerminalSession).where(TerminalSession.active.is_(True)))).scalars().all()
    return [{"id": row.id, "user_id": row.user_id, "vps_id": row.vps_id, "connected_at": row.connected_at} for row in rows]


@router.get("/os-images", response_model=list[OSImageRead])
async def list_os_images(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[OSImage]:
    result = await db.execute(select(OSImage).order_by(OSImage.label))
    return list(result.scalars())


@router.post("/os-images", response_model=OSImageRead)
async def add_os_image(label: str, lxd_alias: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> OSImage:
    image = OSImage(label=label, lxd_alias=lxd_alias)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


@router.get("/branding", response_model=None)
async def get_branding(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    branding = await db.get(Branding, 1)
    if not branding:
        branding = Branding(id=1)
        db.add(branding)
        await db.commit()
        await db.refresh(branding)
    return {
        "site_name": branding.site_name,
        "logo_url": branding.logo_url,
        "favicon_url": branding.favicon_url,
        "primary_color": branding.primary_color,
        "accent_color": branding.accent_color,
        "sidebar_color": branding.sidebar_color,
        "background": branding.background,
    }
