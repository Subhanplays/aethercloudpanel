# AetherCloud

AetherCloud is a single-host VPS hosting panel built around FastAPI, PostgreSQL, WebSockets, and local LXD instances.

The panel host is the LXD host. Each VPS is a separate LXD instance named from its AetherCloud ID, for example `aether-vps-10001`.

## Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Required services:

- PostgreSQL with `DATABASE_URL` such as `postgresql+psycopg://aethercloud:aethercloud@localhost:5432/aethercloud`
- Redis for future queue/session coordination
- LXD initialized on the same host as the backend
- Backend process authorized to run `lxc`

On first startup, AetherCloud creates a default super admin if no admin exists:

- Email: `admin@aethercloud.local`
- Password: `AetherCloud@12345`

Override these before first startup with `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_USERNAME`, and `DEFAULT_ADMIN_PASSWORD`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` when the backend uses a different URL.

## Security Notes

- User terminal access is authorized over the websocket before any session starts.
- Terminal commands run through `lxc exec <instance> -- /bin/bash`, scoped to the authenticated user's VPS.
- There is no generic host command execution API.
- Plaintext VPS passwords are generated and returned once, then discarded.
