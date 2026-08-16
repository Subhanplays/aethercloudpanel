import asyncio
from datetime import datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import VPS, VPSStatus
from app.services.lxd_service import LXDService


async def expiration_loop(interval_seconds: int = 300) -> None:
    lxd = LXDService()
    while True:
        async with SessionLocal() as db:
            result = await db.execute(
                select(VPS).where(VPS.expires_at.is_not(None), VPS.expires_at < datetime.utcnow(), VPS.status != VPSStatus.expired)
            )
            for vps in result.scalars():
                try:
                    await lxd.stop_vps(vps.instance_name, force=False)
                except Exception:
                    pass
                vps.status = VPSStatus.expired
            await db.commit()
        await asyncio.sleep(interval_seconds)
