from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import User
from app.services.terminal_service import TerminalService
from app.services.vps_service import VPSService

router = APIRouter(tags=["terminal"])


async def websocket_user(websocket: WebSocket, db: AsyncSession) -> User | None:
    token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else None
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return await db.get(User, int(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return None


@router.websocket("/vps/{vps_id}/terminal")
async def terminal(websocket: WebSocket, vps_id: str) -> None:
    await websocket.accept()
    async with SessionLocal() as db:
        user = await websocket_user(websocket, db)
        if not user:
            await websocket.close(code=4401)
            return
        try:
            vps = await VPSService(db).owned_vps(vps_id, user)
            await TerminalService(db).bridge(websocket, vps, user.id)
        except WebSocketDisconnect:
            return
        except Exception as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
