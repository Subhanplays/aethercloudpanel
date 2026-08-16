import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TmateSession, VPS
from app.services.lxd_service import LXDService


class TmateService:
    def __init__(self, db: AsyncSession, lxd: LXDService | None = None) -> None:
        self.db = db
        self.lxd = lxd or LXDService()

    async def generate(self, vps: VPS) -> TmateSession:
        await self.lxd.execute_shell(vps.instance_name, "command -v tmate >/dev/null || (apt-get update && apt-get install -y tmate)")
        await self.lxd.execute_shell(vps.instance_name, "pkill -f 'tmate -S /tmp/aethercloud-tmate.sock' || true")
        await self.lxd.execute_shell(vps.instance_name, "tmate -S /tmp/aethercloud-tmate.sock new-session -d")
        await self.lxd.execute_shell(vps.instance_name, "tmate -S /tmp/aethercloud-tmate.sock wait tmate-ready", timeout=60)
        result = await self.lxd.execute_shell(vps.instance_name, "tmate -S /tmp/aethercloud-tmate.sock display -p '#{tmate_ssh}\\n#{tmate_web}'")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        ssh_session = next((line for line in lines if line.startswith("ssh ")), None)
        web_session = next((line for line in lines if re.match(r"https?://", line)), None)
        session = await self._latest(vps.id) or TmateSession(vps_id=vps.id)
        session.ssh_session = ssh_session
        session.web_session = web_session
        session.status = "connected" if ssh_session or web_session else "unknown"
        session.created_at = datetime.utcnow()
        session.last_checked_at = datetime.utcnow()
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get(self, vps: VPS) -> TmateSession | None:
        session = await self._latest(vps.id)
        if not session:
            return None
        try:
            await self.lxd.execute_shell(vps.instance_name, "tmate -S /tmp/aethercloud-tmate.sock display -p '#{tmate_ssh}'", timeout=10)
            session.status = "connected"
        except Exception:
            session.status = "expired"
        session.last_checked_at = datetime.utcnow()
        await self.db.commit()
        return session

    async def terminate(self, vps: VPS) -> None:
        await self.lxd.execute_shell(vps.instance_name, "tmate -S /tmp/aethercloud-tmate.sock kill-session || true")
        session = await self._latest(vps.id)
        if session:
            session.status = "terminated"
            session.last_checked_at = datetime.utcnow()
            await self.db.commit()

    async def _latest(self, vps_pk: int) -> TmateSession | None:
        result = await self.db.execute(
            select(TmateSession).where(TmateSession.vps_id == vps_pk).order_by(TmateSession.created_at.desc())
        )
        return result.scalars().first()
