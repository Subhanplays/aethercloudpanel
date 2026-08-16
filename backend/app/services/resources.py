import shutil

import psutil
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VPS, VPSStatus
from app.schemas import ResourceSummary


async def get_resource_summary(db: AsyncSession) -> ResourceSummary:
    host_cpu = psutil.cpu_count(logical=True) or 1
    host_ram_mb = int(psutil.virtual_memory().total / 1024 / 1024)
    host_storage_gb = int(shutil.disk_usage("/").total / 1024 / 1024 / 1024)

    active_statuses = [VPSStatus.deploying, VPSStatus.running, VPSStatus.stopped, VPSStatus.suspended]
    result = await db.execute(
        select(
            func.coalesce(func.sum(VPS.cpu_cores), 0),
            func.coalesce(func.sum(VPS.ram_mb), 0),
            func.coalesce(func.sum(VPS.storage_gb), 0),
        ).where(VPS.status.in_(active_statuses))
    )
    allocated_cpu, allocated_ram, allocated_storage = result.one()

    return ResourceSummary(
        host_cpu_cores=host_cpu,
        host_ram_mb=host_ram_mb,
        host_storage_gb=host_storage_gb,
        allocated_cpu_cores=int(allocated_cpu),
        allocated_ram_mb=int(allocated_ram),
        allocated_storage_gb=int(allocated_storage),
        available_cpu_cores=max(host_cpu - int(allocated_cpu), 0),
        available_ram_mb=max(host_ram_mb - int(allocated_ram), 0),
        available_storage_gb=max(host_storage_gb - int(allocated_storage), 0),
    )


async def assert_capacity(db: AsyncSession, cpu_cores: int, ram_mb: int, storage_gb: int) -> None:
    summary = await get_resource_summary(db)
    if (
        cpu_cores > summary.available_cpu_cores
        or ram_mb > summary.available_ram_mb
        or storage_gb > summary.available_storage_gb
    ):
        raise ValueError("Insufficient host resources.")
