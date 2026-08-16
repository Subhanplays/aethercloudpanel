import asyncio
import json
import shlex
from dataclasses import dataclass

from app.config import get_settings


class LXDError(RuntimeError):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class LXDService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def _run(self, args: list[str], timeout: int = 120) -> CommandResult:
        proc = await asyncio.create_subprocess_exec(
            self.settings.lxd_binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        result = CommandResult(
            stdout_bytes.decode(errors="ignore"),
            stderr_bytes.decode(errors="ignore"),
            proc.returncode or 0,
        )
        if result.returncode != 0:
            raise LXDError(result.stderr.strip() or result.stdout.strip())
        return result

    async def create_vps(
        self,
        instance_name: str,
        image_alias: str,
        cpu_cores: int,
        ram_mb: int,
        storage_gb: int,
        hostname: str,
    ) -> None:
        await self._run(["init", image_alias, instance_name, "--quiet"], timeout=900)
        await self._run(["config", "set", instance_name, "limits.cpu", str(cpu_cores)])
        await self._run(["config", "set", instance_name, "limits.memory", f"{ram_mb}MiB"])
        await self._run(["config", "set", instance_name, "user.aethercloud.hostname", hostname])
        await self._run(
            [
                "config",
                "device",
                "override",
                instance_name,
                "root",
                f"size={storage_gb}GiB",
                f"pool={self.settings.lxd_storage_pool}",
            ]
        )
        await self._run(["start", instance_name], timeout=180)
        await self.execute(instance_name, ["hostnamectl", "set-hostname", hostname])

    async def delete_vps(self, instance_name: str) -> None:
        await self._run(["delete", instance_name, "--force"], timeout=300)

    async def start_vps(self, instance_name: str) -> None:
        await self._run(["start", instance_name], timeout=180)

    async def stop_vps(self, instance_name: str, force: bool = False) -> None:
        args = ["stop", instance_name]
        if force:
            args.append("--force")
        await self._run(args, timeout=180)

    async def restart_vps(self, instance_name: str) -> None:
        await self._run(["restart", instance_name], timeout=240)

    async def reinstall_vps(self, instance_name: str, image_alias: str, cpu_cores: int, ram_mb: int, storage_gb: int) -> None:
        await self.delete_vps(instance_name)
        await self.create_vps(instance_name, image_alias, cpu_cores, ram_mb, storage_gb, instance_name)

    async def get_status(self, instance_name: str) -> str:
        result = await self._run(["list", instance_name, "--format", "json"])
        data = json.loads(result.stdout or "[]")
        return data[0]["status"].lower() if data else "missing"

    async def get_ip_address(self, instance_name: str) -> str | None:
        result = await self._run(["list", instance_name, "--format", "json"])
        data = json.loads(result.stdout or "[]")
        if not data:
            return None
        for addresses in data[0].get("stateful", {}).values():
            for address in addresses.get("addresses", []):
                if address.get("family") == "inet":
                    return address.get("address")
        for network in data[0].get("state", {}).get("network", {}).values():
            for address in network.get("addresses", []):
                if address.get("family") == "inet":
                    return address.get("address")
        return None

    async def get_stats(self, instance_name: str) -> dict:
        result = await self._run(["query", f"/1.0/instances/{instance_name}/state"])
        return json.loads(result.stdout)

    async def execute(self, instance_name: str, command: list[str], timeout: int = 120) -> CommandResult:
        if not command:
            raise LXDError("Missing command")
        return await self._run(["exec", instance_name, "--", *command], timeout=timeout)

    async def execute_shell(self, instance_name: str, command: str, timeout: int = 120) -> CommandResult:
        return await self.execute(instance_name, ["bash", "-lc", command], timeout=timeout)

    def terminal_command(self, instance_name: str) -> str:
        binary = shlex.quote(self.settings.lxd_binary)
        instance = shlex.quote(instance_name)
        shell = shlex.quote(self.settings.terminal_shell)
        return f"{binary} exec {instance} -- {shell}"
