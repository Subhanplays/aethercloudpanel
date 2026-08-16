from datetime import datetime, timedelta
import shlex

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ActivityLog, OSImage, Role, User, VPS, VPSStatus
from app.schemas import VPSCreate
from app.services.lxd_service import LXDService, LXDError
from app.services.passwords import generate_secure_password
from app.services.resources import assert_capacity


class VPSService:
    def __init__(self, db: AsyncSession, lxd: LXDService | None = None) -> None:
        self.db = db
        self.lxd = lxd or LXDService()
        self.settings = get_settings()

    async def _next_vps_id(self) -> str:
        result = await self.db.execute(select(func.count(VPS.id)))
        count = result.scalar_one()
        while True:
            candidate = f"{self.settings.vps_prefix}-{self.settings.vps_starting_id + count}"
            exists = await self.db.execute(select(VPS).where(VPS.vps_id == candidate))
            if not exists.scalar_one_or_none():
                return candidate
            count += 1

    async def create(self, payload: VPSCreate, actor: User) -> tuple[VPS, str]:
        owner_id = payload.owner_id if actor.role in {Role.admin, Role.super_admin} and payload.owner_id else actor.id
        owner = await self.db.get(User, owner_id)
        image = await self.db.get(OSImage, payload.os_image_id)
        if not owner or not image or not image.enabled:
            raise HTTPException(status_code=400, detail="Invalid owner or OS image")
        try:
            await assert_capacity(self.db, payload.cpu_cores, payload.ram_mb, payload.storage_gb)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        vps_id = await self._next_vps_id()
        instance_name = f"aether-vps-{vps_id.split('-')[-1]}".lower()
        root_password = generate_secure_password()
        vps = VPS(
            vps_id=vps_id,
            instance_name=instance_name,
            owner_id=owner.id,
            os_image_id=image.id,
            status=VPSStatus.deploying,
            cpu_cores=payload.cpu_cores,
            ram_mb=payload.ram_mb,
            storage_gb=payload.storage_gb,
            expires_at=datetime.utcnow() + timedelta(days=payload.expires_days),
        )
        self.db.add(vps)
        await self.db.flush()
        try:
            await self.lxd.create_vps(instance_name, image.lxd_alias, payload.cpu_cores, payload.ram_mb, payload.storage_gb, instance_name)
            await self.lxd.execute_shell(instance_name, "apt-get update && apt-get install -y openssh-server tmate")
            await self.lxd.execute_shell(instance_name, f"printf '%s\\n' {shlex.quote('root:' + root_password)} | chpasswd")
            vps.ip_address = await self.lxd.get_ip_address(instance_name)
            vps.status = VPSStatus.running
        except (LXDError, TimeoutError) as exc:
            vps.status = VPSStatus.error
            await self._log(actor.id, "vps.create.failed", vps.vps_id, {"error": str(exc)})
            await self.db.commit()
            raise HTTPException(status_code=500, detail=f"LXD deployment failed: {exc}") from exc
        await self._log(actor.id, "vps.create", vps.vps_id, {"owner_id": owner.id})
        await self.db.commit()
        await self.db.refresh(vps)
        return vps, root_password

    async def owned_vps(self, vps_id: str, actor: User) -> VPS:
        result = await self.db.execute(select(VPS).where(VPS.vps_id == vps_id))
        vps = result.scalar_one_or_none()
        if not vps:
            raise HTTPException(status_code=404, detail="VPS not found")
        if vps.owner_id != actor.id and actor.role not in {Role.admin, Role.super_admin}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return vps

    async def start(self, vps: VPS, actor: User) -> VPS:
        await self.lxd.start_vps(vps.instance_name)
        vps.status = VPSStatus.running
        await self._log(actor.id, "vps.start", vps.vps_id, {})
        await self.db.commit()
        return vps

    async def stop(self, vps: VPS, actor: User, force: bool = False) -> VPS:
        await self.lxd.stop_vps(vps.instance_name, force=force)
        vps.status = VPSStatus.stopped
        await self._log(actor.id, "vps.stop", vps.vps_id, {"force": force})
        await self.db.commit()
        return vps

    async def restart(self, vps: VPS, actor: User) -> VPS:
        await self.lxd.restart_vps(vps.instance_name)
        vps.status = VPSStatus.running
        vps.ip_address = await self.lxd.get_ip_address(vps.instance_name)
        await self._log(actor.id, "vps.restart", vps.vps_id, {})
        await self.db.commit()
        return vps

    async def delete(self, vps: VPS, actor: User) -> None:
        await self.lxd.delete_vps(vps.instance_name)
        await self._log(actor.id, "vps.delete", vps.vps_id, {})
        await self.db.delete(vps)
        await self.db.commit()

    async def change_password(self, vps: VPS, actor: User) -> str:
        password = generate_secure_password()
        await self.lxd.execute_shell(vps.instance_name, f"printf '%s\\n' {shlex.quote('root:' + password)} | chpasswd")
        await self._log(actor.id, "vps.password.rotate", vps.vps_id, {})
        await self.db.commit()
        return password

    async def _log(self, actor_id: int | None, action: str, target_id: str, metadata: dict) -> None:
        self.db.add(ActivityLog(actor_id=actor_id, action=action, target_type="vps", target_id=target_id, metadata_json=metadata))
