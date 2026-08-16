import asyncio
import os
import signal
import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TerminalSession, VPS, VPSStatus
from app.services.lxd_service import LXDService


@dataclass
class LiveTerminal:
    session_id: str
    process: asyncio.subprocess.Process


class TerminalService:
    def __init__(self, db: AsyncSession, lxd: LXDService | None = None) -> None:
        self.db = db
        self.lxd = lxd or LXDService()
        self.sessions: dict[str, LiveTerminal] = {}

    async def create_session(self, vps: VPS, user_id: int) -> LiveTerminal:
        if vps.status != VPSStatus.running:
            raise HTTPException(status_code=409, detail="VPS must be running")
        session_id = uuid.uuid4().hex
        command = self.lxd.terminal_command(vps.instance_name)
        process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        live = LiveTerminal(session_id=session_id, process=process)
        self.sessions[session_id] = live
        self.db.add(TerminalSession(id=session_id, user_id=user_id, vps_id=vps.id))
        await self.db.commit()
        return live

    async def send_input(self, session_id: str, data: str) -> None:
        live = self.sessions[session_id]
        if live.process.stdin:
            live.process.stdin.write(data.encode())
            await live.process.stdin.drain()

    async def resize(self, session_id: str, rows: int, cols: int) -> None:
        live = self.sessions.get(session_id)
        if live:
            live.process.send_signal(signal.SIGWINCH)

    async def close_session(self, session_id: str) -> None:
        live = self.sessions.pop(session_id, None)
        if live and live.process.returncode is None:
            live.process.terminate()
            try:
                await asyncio.wait_for(live.process.wait(), timeout=3)
            except asyncio.TimeoutError:
                live.process.kill()
        db_session = await self.db.get(TerminalSession, session_id)
        if db_session:
            db_session.active = False
            db_session.disconnected_at = datetime.utcnow()
            await self.db.commit()

    async def bridge(self, websocket: WebSocket, vps: VPS, user_id: int) -> None:
        live = await self.create_session(vps, user_id)
        await websocket.send_json({"type": "ready", "sessionId": live.session_id})

        async def pump_output() -> None:
            assert live.process.stdout is not None
            while True:
                chunk = await live.process.stdout.read(4096)
                if not chunk:
                    break
                await websocket.send_text(chunk.decode(errors="ignore"))

        output_task = asyncio.create_task(pump_output())
        try:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "input":
                    await self.send_input(live.session_id, message.get("data", ""))
                elif message.get("type") == "resize":
                    await self.resize(live.session_id, int(message.get("rows", 24)), int(message.get("cols", 80)))
        finally:
            output_task.cancel()
            await self.close_session(live.session_id)
