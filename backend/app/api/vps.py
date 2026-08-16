from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OSImage, Role, User, VPS
from app.schemas import OSImageRead, PasswordResponse, ResourceSummary, TmateRead, VPSCreate, VPSRead, VPSStats
from app.security.auth import current_user, require_admin
from app.services.lxd_service import LXDService
from app.services.resources import get_resource_summary
from app.services.tmate_service import TmateService
from app.services.vps_service import VPSService

router = APIRouter(prefix="/vps", tags=["vps"])


@router.get("/images", response_model=list[OSImageRead])
async def os_images(db: AsyncSession = Depends(get_db)) -> list[OSImage]:
    result = await db.execute(select(OSImage).where(OSImage.enabled.is_(True)).order_by(OSImage.label))
    return list(result.scalars())


@router.get("/resources", response_model=ResourceSummary)
async def resources(db: AsyncSession = Depends(get_db)) -> ResourceSummary:
    return await get_resource_summary(db)


@router.post("", response_model=VPSRead)
async def create_vps(payload: VPSCreate, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPS:
    vps, _password = await VPSService(db).create(payload, user)
    return vps


@router.get("", response_model=list[VPSRead])
async def list_vps(db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> list[VPS]:
    query = select(VPS).order_by(VPS.created_at.desc())
    if user.role not in {Role.admin, Role.super_admin}:
        query = query.where(VPS.owner_id == user.id)
    result = await db.execute(query)
    return list(result.scalars())


@router.get("/{vps_id}", response_model=VPSRead)
async def get_vps(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPS:
    return await VPSService(db).owned_vps(vps_id, user)


@router.post("/{vps_id}/start", response_model=VPSRead)
async def start_vps(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPS:
    service = VPSService(db)
    return await service.start(await service.owned_vps(vps_id, user), user)


@router.post("/{vps_id}/stop", response_model=VPSRead)
async def stop_vps(vps_id: str, force: bool = False, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPS:
    service = VPSService(db)
    return await service.stop(await service.owned_vps(vps_id, user), user, force=force)


@router.post("/{vps_id}/restart", response_model=VPSRead)
async def restart_vps(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPS:
    service = VPSService(db)
    return await service.restart(await service.owned_vps(vps_id, user), user)


@router.delete("/{vps_id}", status_code=204)
async def delete_vps(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> None:
    service = VPSService(db)
    await service.delete(await service.owned_vps(vps_id, user), user)


@router.get("/{vps_id}/stats", response_model=VPSStats)
async def stats(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> VPSStats:
    vps = await VPSService(db).owned_vps(vps_id, user)
    raw = await LXDService().get_stats(vps.instance_name)
    memory = raw.get("memory", {})
    disk = next(iter(raw.get("disk", {}).values()), {})
    network = next(iter(raw.get("network", {}).values()), {})
    return VPSStats(
        status=await LXDService().get_status(vps.instance_name),
        ram_used_mb=float(memory.get("usage", 0)) / 1024 / 1024,
        ram_limit_mb=vps.ram_mb,
        disk_used_gb=float(disk.get("usage", 0)) / 1024 / 1024 / 1024,
        disk_limit_gb=vps.storage_gb,
        network_rx_mb=float(network.get("counters", {}).get("bytes_received", 0)) / 1024 / 1024,
        network_tx_mb=float(network.get("counters", {}).get("bytes_sent", 0)) / 1024 / 1024,
    )


@router.post("/{vps_id}/password", response_model=PasswordResponse)
async def rotate_password(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> PasswordResponse:
    service = VPSService(db)
    password = await service.change_password(await service.owned_vps(vps_id, user), user)
    return PasswordResponse(password=password)


@router.get("/{vps_id}/tmate", response_model=TmateRead)
async def get_tmate(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> TmateRead:
    vps = await VPSService(db).owned_vps(vps_id, user)
    session = await TmateService(db).get(vps)
    if not session:
        raise HTTPException(status_code=404, detail="No tmate session")
    return TmateRead(ssh_session=session.ssh_session, web_session=session.web_session, status=session.status)


@router.post("/{vps_id}/tmate", response_model=TmateRead)
async def generate_tmate(vps_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> TmateRead:
    vps = await VPSService(db).owned_vps(vps_id, user)
    session = await TmateService(db).generate(vps)
    return TmateRead(ssh_session=session.ssh_session, web_session=session.web_session, status=session.status)
